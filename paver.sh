#!/usr/bin/env bash
# Copyright (c) 2010-2013 Adi Roiban.
# See LICENSE for details.
#
# Helper script for bootstrapping the build system on Unix/Msys.
# It will write the default values in the 'DEFAULT_VALUES' file.
#
# To use this script you will need to publish binary archive files for the
# following components:
#
# * Python main distribution
# * pip
# * setuptools
#
# It will delegate the argument to the paver script, with the exception of
# these commands:
#
# * clean - remove everything, except cache
# * purge - remove (empty) the cache
# * detect_os - detect operating system, create the DEFAULT_VALUES file and exit
# * get_python - download Python distribution in cache
# * get_agent - download Rexx/Putty distribution in cache

# Script initialization.
set -o nounset
set -o errexit
set -o pipefail

# Initialize default value.
COMMAND=${1-''}
DEBUG=${DEBUG-0}

# Set default locale.
# We use C (alias for POSIX) for having a basic default value and
# to make sure we explicitly convert all unicode values.
export LANG='C'
export LANGUAGE='C'
export LC_ALL='C'
export LC_CTYPE='C'
export LC_COLLATE='C'
export LC_MESSAGES='C'
export PATH=$PATH:'/sbin:/usr/sbin:/usr/local/bin'

#
# Global variables.
#
# Used to return non-scalar value from functions.
RESULT=''
WAS_PYTHON_JUST_INSTALLED=0
DIST_FOLDER='dist'

# Path global variables.
BUILD_FOLDER=""
CACHE_FOLDER="cache"
PYTHON_BIN=""
PYTHON_LIB=""
LOCAL_PYTHON_BINARY_DIST=""

# Put default values and create them as global variables.
OS='not-detected-yet'
ARCH='x86'

# Initialize default values from paver.conf
PYTHON_CONFIGURATION='NOT-YET-DEFINED'
PYTHON_VERSION='not.defined.yet'
PYTHON_PLATFORM='unknown-os-and-arch'
PYTHON_NAME='python2.7'
BINARY_DIST_URI='https://binary.chevah.com/production'
PIP_INDEX='http://pypi.chevah.com'
PAVER_VERSION='1.2.1'

# Load repo specific configuration.
source paver.conf


clean_build() {
    # Shortcut for clear since otherwise it will depend on python
    echo "Removing ${BUILD_FOLDER}..."
    delete_folder ${BUILD_FOLDER}
    echo "Removing dist..."
    delete_folder ${DIST_FOLDER}
    echo "Removing publish..."
    delete_folder 'publish'
    echo "Cleaning project temporary files..."
    rm -f DEFAULT_VALUES
    echo "Cleaning pyc files ..."
    if [ $OS = "rhel4" ]; then
        # RHEL 4 don't support + option in -exec
        # We use -print0 and xargs to no fork for each file.
        # find will fail if no file is found.
        touch ./dummy_file_for_RHEL4.pyc
        find ./ -name '*.pyc' -print0 | xargs -0 rm
    else
        # AIX's find complains if there are no matching files when using +.
        [ $(uname) == AIX ] && touch ./dummy_file_for_AIX.pyc
        # Faster than '-exec rm {} \;' and supported in most OS'es,
        # details at http://www.in-ulm.de/~mascheck/various/find/#xargs
        find ./ -name '*.pyc' -exec rm {} +
    fi
    # In some case pip hangs with a build folder in temp and
    # will not continue until it is manually removed.
    # On the OSX build server tmp is in $TMPDIR
    if [ ! -z "${TMPDIR-}" ]; then
        # check if TMPDIR is set before trying to clean it.
        rm -rf ${TMPDIR}/pip*
    else
        rm -rf /tmp/pip*
    fi
}


#
# Removes the download/pip cache entries. Must be called before
# building/generating the distribution.
#
purge_cache() {
    clean_build

    echo "Cleaning download cache ..."
    rm -rf cache/*
}


#
# Delete the folder as quickly as possible.
#
delete_folder() {
    local target="$1"
    # On Windows, we use internal command prompt for maximum speed.
    # See: http://stackoverflow.com/a/6208144/539264
    if [ $OS = "windows" -a -d $target ]; then
        cmd //c "del /f/s/q $target > nul"
        cmd //c "rmdir /s/q $target"
    else
        rm -rf $target
    fi
}


#
# Wrapper for executing a command and exiting on failure.
#
execute() {
    if [ $DEBUG -ne 0 ]; then
        echo "Executing:" $@
    fi

    # Make sure $@ is called in quotes as otherwise it will not work.
    set +e
    "$@"
    exit_code=$?
    set -e
    if [ $exit_code -ne 0 ]; then
        echo "Fail:" $@
        exit 1
    fi
}

#
# Update global variables with current paths.
#
update_path_variables() {
    resolve_python_version

    if [ "${OS}" = "windows" ] ; then
        PYTHON_BIN="/lib/python.exe"
        PYTHON_LIB="/lib/Lib/"
    else
        PYTHON_BIN="/bin/python"
        PYTHON_LIB="/lib/${PYTHON_NAME}/"
    fi

    BUILD_FOLDER="build-${OS}-${ARCH}"
    PYTHON_BIN="${BUILD_FOLDER}${PYTHON_BIN}"
    PYTHON_LIB="${BUILD_FOLDER}${PYTHON_LIB}"

    LOCAL_PYTHON_BINARY_DIST="$PYTHON_NAME-$OS-$ARCH"

    export PYTHONPATH=${BUILD_FOLDER}
}

#
# Called to update the Python version env var based on the platform
# advertised by the current environment.
#
resolve_python_version() {
    local version_configuration=$PYTHON_CONFIGURATION
    local candidate
    local candidate_platform
    local candidate_version

    PYTHON_PLATFORM="$OS-$ARCH"

    # This is a stupid way to iterate, up to 16 times while being OS neutral.
    # We only support a maximum of 16 different versions.
    for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16; do
        candidate=`echo ${version_configuration} | cut -d: -f$i`
        if [ "$candidate" = "" ]; then
            break
        fi
        candidate_platform=`echo $candidate | cut -d@ -f1`
        candidate_version=`echo $candidate | cut -d@ -f2`

        if [ "$candidate_platform" == "default" ]; then
            # Set the default version in case no specific platform is
            # configured.
            PYTHON_VERSION=$candidate_version
        fi

        case $PYTHON_PLATFORM in
            $candidate_platform*)
                # We have a match for a specific platform, so we return
                # as we don't want to look further.
                PYTHON_VERSION=$candidate_version
                return 0
                ;;
        esac

    done
}

write_default_values() {
    echo ${BUILD_FOLDER} ${PYTHON_NAME} ${OS} ${ARCH} > DEFAULT_VALUES
}


#
# Install base package.
#
install_base_deps() {
    local base_packages
    base_packages="paver==$PAVER_VERSION"
    if [ "$BRINK_VERSION" = "skip" ]; then
        echo "Skipping brink installation."
    else
        base_packages="$base_packages chevah-brink==$BRINK_VERSION"
    fi

    echo "Installing $base_packages."

    pip_install "$base_packages"
}


#
# Wrapper for python `pip install` command.
# * $1 - package_name and optional version.
#
pip_install() {
    set +e
    # There is a bug in pip/setuptools when using custom build folders.
    # See https://github.com/pypa/pip/issues/3564
    rm -rf ${BUILD_FOLDER}/pip-build
    ${PYTHON_BIN} -m \
        pip.__init__ install $1 \
            --trusted-host pypi.chevah.com \
            --index-url=$PIP_INDEX/simple \
            --build=${BUILD_FOLDER}/pip-build \
            --cache-dir=${CACHE_FOLDER} \
            --use-wheel

    exit_code=$?
    set -e
    if [ $exit_code -ne 0 ]; then
        echo "Failed to install brink."
        exit 1
    fi
}


#
# Download and extract a binary distribution.
#
get_binary_dist() {
    local dist_name=$1
    local remote_base_url=$2

    echo "Getting $dist_name from $remote_base_url..."

    tar_gz_file=${dist_name}.tar.gz
    tar_file=${dist_name}.tar

    mkdir -p ${CACHE_FOLDER}
    pushd ${CACHE_FOLDER}

        # Get and extract archive.
        rm -rf $dist_name
        rm -f $tar_gz_file
        rm -f $tar_file
        # Use 1M dot to reduce console pollution.
        execute wget --progress=dot -e dotbytes=1M \
            $remote_base_url/${tar_gz_file}
        execute gunzip $tar_gz_file
        execute tar -xf $tar_file
        rm -f $tar_gz_file
        rm -f $tar_file

    popd
}

#
# Check if we have a versioned Python distribution.
#
test_version_exists() {
    local remote_base_url=$1
    local wget_test
    local target_file=python-${PYTHON_VERSION}-${OS}-${ARCH}.tar.gz

    wget --spider $remote_base_url/${OS}/${ARCH}/$target_file
    wget_test=$?
    return $wget_test
}

#
# Download and extract in cache the python distributable.
#
get_python_dist() {
    local remote_base_url=$1
    local python_distributable=python-${PYTHON_VERSION}-${OS}-${ARCH}
    local wget_test

    set +o errexit
    test_version_exists $remote_base_url
    wget_test=$?
    set -o errexit

    if [ $wget_test -eq 0 ]; then
        # We have the requested python version.
        get_binary_dist $python_distributable $remote_base_url/${OS}/${ARCH}
    else
        # Fall back to the non-versioned distribution.
        echo "!!!Getting FALLBACK version!!!"
        get_binary_dist $PYTHON_NAME-$OS-$ARCH $remote_base_url
    fi
}


# copy_python can be called in a recursive way, and this is here to prevent
# accidental infinite loops.
COPY_PYTHON_RECURSIONS=0
#
# Copy python to build folder from binary distribution.
#
copy_python() {

    local python_distributable="${CACHE_FOLDER}/${LOCAL_PYTHON_BINARY_DIST}"
    local python_installed_version

    COPY_PYTHON_RECURSIONS=`expr $COPY_PYTHON_RECURSIONS + 1`

    if [ $COPY_PYTHON_RECURSIONS -gt 2 ]; then
        echo "Too many calls to copy_python. ($COPY_PYTHON_RECURSIONS)"
        exit 1
    fi

    # Check that python dist was installed
    if [ ! -s ${PYTHON_BIN} ]; then
        # Install python-dist since everything else depends on it.
        echo "Bootstrapping ${LOCAL_PYTHON_BINARY_DIST} environment" \
            "to ${BUILD_FOLDER}..."
        mkdir -p ${BUILD_FOLDER}

        # If we don't have a cached python distributable,
        # get one together with default build system.
        if [ ! -d ${python_distributable} ]; then
            echo "No ${LOCAL_PYTHON_BINARY_DIST} environment." \
                "Start downloading it..."
            get_python_dist "$BINARY_DIST_URI/python"
        fi
        echo "Copying Python distribution files... "
        cp -R ${python_distributable}/* ${BUILD_FOLDER}

        install_base_deps
        WAS_PYTHON_JUST_INSTALLED=1
    else
        # We have a Python, but we are not sure if is the right version.
        local version_file=${BUILD_FOLDER}/lib/PYTHON_PACKAGE_VERSION
        if [ -f $version_file ]; then
            python_installed_version=`cat $version_file`
            if [ "$PYTHON_VERSION" != "$python_installed_version" ]; then
                # We have a different python installed.
                # Remove it and try to install it again.
                echo "Updating Python from" \
                    $python_installed_version to $PYTHON_VERSION
                rm -rf ${BUILD_FOLDER}
                rm -rf ${python_distributable}
                copy_python
            fi
        else
            # The installed python has no version.
            set +o errexit
            test_version_exists "$BINARY_DIST_URI/python"
            local test_version=$?
            set -o errexit
            if [ $test_version -eq 0 ]; then
                echo "Updating Python from UNVERSIONED to $PYTHON_VERSION"
                # We have a different python installed.
                # Remove it and try to install it again.
                rm -rf ${BUILD_FOLDER}
                rm -rf ${python_distributable}
                copy_python
            else
                echo "Leaving UNVERSIONED Python."
            fi
        fi
    fi

}


#
# Install dependencies after python was just installed.
#
install_dependencies(){

    if [ $WAS_PYTHON_JUST_INSTALLED -ne 1 ]; then
        return
    fi

    set +e
    ${PYTHON_BIN} -c 'from paver.tasks import main; main()' deps
    exit_code=$?
    set -e
    if [ $exit_code -ne 0 ]; then
        echo 'Failed to run the initial "paver deps" command.'
        exit 1
    fi
}


#
# Check that we have a pavement.py in the current dir.
# otherwise it means we are out of the source folder and paver can not be
# used there.
#
check_source_folder() {

    if [ ! -e pavement.py ]; then
        echo 'No pavement.py file found in current folder.'
        echo 'Make sure you are running paver from a source folder.'
        exit 1
    fi
}


#
# Check version of current OS to see if it is supported.
# If it's too old, exit with a nice informative message.
# If it's supported, return through eval the version numbers to be used for
# naming the package, for example '5' for RHEL 5.x, '1204' for Ubuntu 12.04',
# '53' for AIX 5.3.x.x , '10' for Solaris 10 or '1010' for OS X 10.10.1.
#
check_os_version() {
    # First parameter should be the human-readable name for the current OS.
    # For example: "Red Hat Enterprise Linux" for RHEL, "OS X" for Darwin etc.
    # Second and third parameters must be strings composed of integers
    # delimited with dots, representing, in order, the oldest version
    # supported for the current OS and the current detected version.
    # The fourth parameter is used to return through eval the relevant numbers
    # for naming the Python package for the current OS, as detailed above.
    local name_fancy="$1"
    local version_good="$2"
    local version_raw="$3"
    local version_chevah="$4"
    local version_constructed=''
    local flag_supported='good_enough'
    local version_raw_array
    local version_good_array

    # Using '.' as a delimiter, populate the version_raw_* arrays.
    IFS=. read -a version_raw_array <<< "$version_raw"
    IFS=. read -a version_good_array <<< "$version_good"

    # Iterate through all the integers from the good version to compare them
    # one by one with the corresponding integers from the supported version.
    for (( i=0 ; i < ${#version_good_array[@]}; i++ )); do
        version_constructed="${version_constructed}${version_raw_array[$i]}"
        if [ ${version_raw_array[$i]} -gt ${version_good_array[$i]} -a \
            "$flag_supported" = 'good_enough' ]; then
            flag_supported='true'
        elif [  ${version_raw_array[$i]} -lt ${version_good_array[$i]} -a \
            "$flag_supported" = 'good_enough' ]; then
            flag_supported='false'
        fi
    done

    if [ "$flag_supported" = 'false' ]; then
        echo "The current version of ${name_fancy} is too old: ${version_raw}"
        echo "Oldest supported version of ${name_fancy} is: ${version_good}"
        exit 13
    fi

    # The sane way to return fancy values with a bash function is to use eval.
    eval $version_chevah="'$version_constructed'"
}


#
# Update OS and ARCH variables with the current values.
#
detect_os() {

    OS=$(uname -s | tr "[A-Z]" "[a-z]")

    if [ "${OS%mingw*}" = "" ]; then

        OS='windows'
        ARCH='x86'

    elif [ "${OS}" = "sunos" ]; then

        ARCH=$(isainfo -n)
        os_version_raw=$(uname -r | cut -d'.' -f2)
        check_os_version Solaris 10 "$os_version_raw" os_version_chevah

        OS="solaris${os_version_chevah}"

        # Solaris 10u8 (from 10/09) updated the libc version, so for older
        # releases we build on 10u3, and use that up to 10u7 (from 5/09).
        if [ "${OS}" = "solaris10" ]; then
            # We extract the update number from the first line.
            update=$(head -1 /etc/release | cut -d'_' -f2 | sed 's/[^0-9]*//g')
            if [ "$update" -lt 8 ]; then
                OS="solaris10u3"
            fi
        fi

    elif [ "${OS}" = "aix" ]; then

        ARCH="ppc$(getconf HARDWARE_BITMODE)"
        os_version_raw=$(oslevel)
        check_os_version AIX 5.3 "$os_version_raw" os_version_chevah

        OS="aix${os_version_chevah}"

    elif [ "${OS}" = "hp-ux" ]; then

        ARCH=$(uname -m)
        os_version_raw=$(uname -r | cut -d'.' -f2-)
        check_os_version HP-UX 11.31 "$os_version_raw" os_version_chevah

        OS="hpux${os_version_chevah}"

    elif [ "${OS}" = "linux" ]; then

        ARCH=$(uname -m)

        if [ -f /etc/redhat-release ]; then
            # Avoid getting confused by Red Hat derivatives such as Fedora.
            if egrep -q 'Red\ Hat|CentOS|Scientific' /etc/redhat-release; then
                os_version_raw=$(\
                    cat /etc/redhat-release | sed s/.*release// | cut -d' ' -f2)
                check_os_version "Red Hat Enterprise Linux" 4 \
                    "$os_version_raw" os_version_chevah
                OS="rhel${os_version_chevah}"
            fi
        elif [ -f /etc/SuSE-release ]; then
            # Avoid getting confused by SUSE derivatives such as OpenSUSE.
            if [ $(head -n1 /etc/SuSE-release | cut -d' ' -f1) = 'SUSE' ]; then
                os_version_raw=$(\
                    grep VERSION /etc/SuSE-release | cut -d' ' -f3)
                check_os_version "SUSE Linux Enterprise Server" 10 \
                    "$os_version_raw" os_version_chevah
                OS="sles${os_version_chevah}"
            fi
        elif [ -f /etc/arch-release ]; then
            # ArchLinux is a rolling distro, no version info available.
            OS="archlinux"
        elif [ -f /etc/rpi-issue ]; then
            # Raspbian is a special case, a Debian unofficial derivative.
            if egrep -q ^'NAME="Raspbian GNU/Linux' /etc/os-release; then
                os_version_raw=$(\
                    grep ^'VERSION_ID=' /etc/os-release | cut -d'"' -f2)
                check_os_version "Raspbian GNU/Linux" 7 \
                    "$os_version_raw" os_version_chevah
                # For now, we only generate a Raspbian version 7.x package,
                # and we should use that in newer Raspbian versions too.
                OS="raspbian7"
            fi
        elif [ $(command -v lsb_release) ]; then
            lsb_release_id=$(lsb_release -is)
            os_version_raw=$(lsb_release -rs)
            if [ $lsb_release_id = Ubuntu ]; then
                check_os_version "Ubuntu Long-term Support" 10.04 \
                    "$os_version_raw" os_version_chevah
                # Only Long-term Support versions are officially endorsed, thus
                # $os_version_chevah should end in 04, and the first two digits
                # should represent an even year.
                if [ ${os_version_chevah%%04} != ${os_version_chevah} -a \
                    $(( ${os_version_chevah%%04} % 2 )) -eq 0 ]; then
                    OS="ubuntu${os_version_chevah}"
                fi
            fi
        fi
    elif [ "${OS}" = "darwin" ]; then
        ARCH=$(uname -m)

        os_version_raw=$(sw_vers -productVersion)
        check_os_version "Mac OS X" 10.8 "$os_version_raw" os_version_chevah

        if [ ${os_version_chevah:0:2} -eq 10 -a \
            ${os_version_chevah:2:2} -ge 12  ]; then
            # For newer, macOS versions, we use '1012'.
            OS="macos1012"
        else
            # For older, OS X versions, we use '108'.
            OS="osx108"
        fi


    elif [ "${OS}" = "freebsd" ]; then
        ARCH=$(uname -m)

        os_version_raw=$(uname -r | cut -d'.' -f1)
        check_os_version "FreeBSD" 10 "$os_version_raw" os_version_chevah

        # For now, no matter the actual FreeBSD version returned, we use '10'.
        OS="freebsd10"

    elif [ "${OS}" = "openbsd" ]; then
        ARCH=$(uname -m)

        os_version_raw=$(uname -r)
        check_os_version "OpenBSD" 5.9 "$os_version_raw" os_version_chevah
        OS="openbsd${os_version_chevah}"

    else
        echo 'Unsupported operating system:' $OS
        exit 14
    fi

    # Fix arch names.
    if [ "$ARCH" = "i686" -o "$ARCH" = "i386" ]; then
        ARCH='x86'
    elif [ "$ARCH" = "x86_64" -o "$ARCH" = "amd64" ]; then
        ARCH='x64'
    elif [ "$ARCH" = "sparcv9" ]; then
        ARCH='sparc64'
    elif [ "$ARCH" = "ppc64" ]; then
        # Python has not been fully tested on AIX when compiled as a 64 bit
        # binary, and has math rounding error problems (at least with XL C).
        ARCH='ppc'
    elif [ "$ARCH" = "aarch64" ]; then
        ARCH='arm64'
    fi
}

detect_os
update_path_variables

if [ "$COMMAND" = "clean" ] ; then
    clean_build
    exit 0
fi

if [ "$COMMAND" = "purge" ] ; then
    purge_cache
    exit 0
fi

if [ "$COMMAND" = "detect_os" ] ; then
    write_default_values
    exit 0
fi

if [ "$COMMAND" = "get_python" ] ; then
    OS=$2
    ARCH=$3
    resolve_python_version
    get_python_dist "$BINARY_DIST_URI/python"
    exit 0
fi

if [ "$COMMAND" = "get_agent" ] ; then
    get_binary_dist $2 "$BINARY_DIST_URI/agent"
    exit 0
fi

check_source_folder
write_default_values
copy_python
install_dependencies

# Always update brink when running buildbot tasks.
for paver_task in "deps" "test_os_dependent" "test_os_independent"; do
    if [ "$COMMAND" == "$paver_task" ] ; then
        install_base_deps
    fi
done

case $COMMAND in
    test_ci|test_py3)
        PYTHON3_CHECK='-3'
        ;;
    *)
        PYTHON3_CHECK=''
        ;;
esac

# Now that we have Python and Paver, let's call Paver from Python :)
set +e
${PYTHON_BIN} $PYTHON3_CHECK -c 'from paver.tasks import main; main()' "$@"
exit_code=$?
set -e
exit $exit_code
