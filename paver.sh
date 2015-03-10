#!/usr/bin/env bash
# Copyright (c) 2010-2013 Adi Roiban.
# See LICENSE for details.
#
# Helper script for bootstraping the build system on Unix/Msys.
# It will write the default values into 'DEFAULT_VALUES' file.
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
# * clean - remove everything, except cache
# * detect_os - create DEFAULT_VALUES and exit
# * get_python - download Python distribution in cache
# * get_agent - download Rexx/Putty distribution in cache
#

# Script initialization.
set -o nounset
set -o errexit
set -o pipefail

# Initialize default value.
COMMAND=${1-''}
DEBUG=${DEBUG-0}

# Load repo specific configuration.
source paver.conf

# Set default locale.
# We use C (alias for POSIX) for having a basic default value and
# to make sure we explictly convert all unicode values.
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
CLEAN_PYTHON_BINARY_DIST_CACHE=""

# Put default values and create them as global variables.
OS='not-detected-yet'
ARCH='x86'
CC='gcc'
CXX='g++'


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
    rm -rf /tmp/pip*

    if [ "$CLEAN_PYTHON_BINARY_DIST_CACHE" = "yes" ]; then
        echo "Cleaning python binary ..."
        rm -rf cache/python*
    fi
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

    #Make sure $@ is called in quotes as otherwise it will not work.
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

    if [ "${OS}" = "windows" ] ; then
        PYTHON_BIN="/lib/python.exe"
        PYTHON_LIB="/lib/Lib/"
    else
        PYTHON_BIN="/bin/python"
        PYTHON_LIB="/lib/${PYTHON_VERSION}/"
    fi

    BUILD_FOLDER="build-${OS}-${ARCH}"
    PYTHON_BIN="${BUILD_FOLDER}${PYTHON_BIN}"
    PYTHON_LIB="${BUILD_FOLDER}${PYTHON_LIB}"

    LOCAL_PYTHON_BINARY_DIST="$PYTHON_VERSION-$OS-$ARCH"

    export PYTHONPATH=${BUILD_FOLDER}
}


write_default_values() {
    echo ${BUILD_FOLDER} ${PYTHON_VERSION} ${OS} ${ARCH} ${CC} ${CXX} \
        > DEFAULT_VALUES
}


#
# Install brink package.
#
install_brink() {
    if [ "$BRINK_VERSION" = "skip" ]; then
        echo "Skipping brink installation."
        return
    fi

    echo "Installing version: chevah-brink==$BRINK_VERSION of brink..."

    pip install "chevah-brink==$BRINK_VERSION"
}


#
# Wrapper for python pip command.
# * $1 - command name
# * $2 - package_name and optional version.
#
pip() {
    set +e
    ${PYTHON_BIN} -m \
        pip.__init__ $1 $2 \
            --index-url=$PIP_INDEX/simple \
            --download-cache=${CACHE_FOLDER} \
            --find-links=file://${CACHE_FOLDER} \
            --upgrade

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
    local remote_url=$2

    echo "Getting $dist_name from $remote_url..."

    tar_gz_file=${dist_name}.tar.gz
    tar_file=${dist_name}.tar

    mkdir -p ${CACHE_FOLDER}
    pushd ${CACHE_FOLDER}

        # Get and extract archive.
        rm -rf $dist_name
        rm -f $tar_gz_file
        rm -f $tar_file
        # Use 1M dot to reduce console pollution.
        execute wget --progress=dot -e dotbytes=1M $remote_url/${tar_gz_file}
        execute gunzip $tar_gz_file
        execute tar -xf $tar_file
        rm -f $tar_gz_file
        rm -f $tar_file

    popd
}


#
# Copy python to build folder from binary distribution.
#
copy_python() {

    local python_distributable="${CACHE_FOLDER}/${PYTHON_VERSION}-${OS}-${ARCH}"
    local pip_package="pip-$PIP_VERSION"
    local setuptools_package="setuptools-$SETUPTOOLS_VERSION"

    # Check that python dist was installed
    if [ ! -s ${PYTHON_BIN} ]; then
        # Install python-dist since everything else depends on it.
        echo "Bootstraping ${PYTHON_VERSION} environment to ${BUILD_FOLDER}..."
        mkdir -p ${BUILD_FOLDER}

        # If we don't have a cached python distributable,
        # get one together with default build system.
        if [ ! -d ${python_distributable} ]; then
            echo "No ${PYTHON_VERSION} environment. Start downloading it..."
            get_binary_dist \
                ${PYTHON_VERSION}-${OS}-${ARCH} "$BINARY_DIST_URI/python"
        fi
        echo "Copying bootstraping files... "
        cp -R ${python_distributable}/* ${BUILD_FOLDER}

        # Backwards compatibility with python 2.5 build.
        if [[ "$PYTHON_VERSION" = "python2.5" ]]; then
            # Copy include files.
            if [ -d ${BUILD_FOLDER}/lib/config/include ]; then
                cp -r ${BUILD_FOLDER}/lib/config/include ${BUILD_FOLDER}
            fi

            # Copy pywintypes25.dll as it is required by paver on windows.
            if [ "$OS" = "windows" ]; then
                cp -R ${BUILD_FOLDER}/lib/pywintypes25.dll . || true
            fi
        fi

        if [ ! -d ${CACHE_FOLDER}/$pip_package ]; then
            echo "No ${pip_package}. Start downloading it..."
            get_binary_dist "$pip_package" "$PIP_INDEX/packages"
        fi
        cp -RL "${CACHE_FOLDER}/$pip_package/pip" ${PYTHON_LIB}/site-packages/

        if [ ! -d ${CACHE_FOLDER}/$setuptools_package ]; then
            echo "No ${setuptools_package}. Start downloading it..."
            get_binary_dist "$setuptools_package" "$PIP_INDEX/packages"
        fi
        cp -RL "${CACHE_FOLDER}/$setuptools_package/setuptools" \
            ${PYTHON_LIB}/site-packages/
        cp -RL "${CACHE_FOLDER}/$setuptools_package//setuptools.egg-info" \
            ${PYTHON_LIB}/site-packages/
        cp "${CACHE_FOLDER}/$setuptools_package/pkg_resources.py" \
            ${PYTHON_LIB}/site-packages/
        cp "${CACHE_FOLDER}/$setuptools_package/easy_install.py" \
            ${PYTHON_LIB}/site-package

        # Once we have pip, we can use it.
        pip install "paver==$PAVER_VERSION"

        WAS_PYTHON_JUST_INSTALLED=1
    fi

}


#
# Install dependencies after python was just installed.
#
install_dependencies(){

    if [ $WAS_PYTHON_JUST_INSTALLED -ne 1 ]; then
        return
    fi

    install_brink

    set +e
    ${PYTHON_BIN} -c 'from paver.tasks import main; main()' deps
    exit_code=$?
    set -e
    if [ $exit_code -ne 0 ]; then
        echo 'Failed to run the inital "paver deps" command.'
        exit 1
    fi
}


#
# Chech that we have a pavement.py in the current dir.
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

        # By default, we use Sun's Studio compiler. Comment these two for GCC.
        CC="cc"
        CXX="CC"

        ARCH=$(isainfo -n)
        os_version_raw=$(uname -r | cut -d'.' -f2)
        check_os_version Solaris 10 "$os_version_raw" os_version_chevah

        OS="solaris${os_version_chevah}"

    elif [ "${OS}" = "aix" ]; then

        # By default, we use IBM's XL C compiler. Comment these two for GCC.
        # Beware that GCC 4.2 from IBM's RPMs will fail with GMP and Python!
        CC="xlc_r"
        CXX="xlC_r"

        ARCH="ppc$(getconf HARDWARE_BITMODE)"
        os_version_raw=$(oslevel)
        check_os_version AIX 5.3 "$os_version_raw" os_version_chevah

        OS="aix${os_version_chevah}"

    elif [ "${OS}" = "hp-ux" ]; then

        # libffi and GMP do not compile with the HP compiler, so we use GCC.

        ARCH=$(uname -m)
        os_version_raw=$(uname -r | cut -d'.' -f2-)
        check_os_version HP-UX 11.31 "$os_version_raw" os_version_chevah

        OS="hpux${os_version_chevah}"

    elif [ "${OS}" = "linux" ]; then

        ARCH=$(uname -m)

        if [ -f /etc/redhat-release ]; then
            # Avoid getting confused by Red Hat derivatives such as Fedora.
            egrep 'Red\ Hat|CentOS|Scientific' /etc/redhat-release > /dev/null
            if [ $? -eq 0 ]; then
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
                check_os_version "SUSE Linux Enterprise Server" 11 \
                    "$os_version_raw" os_version_chevah
                OS="sles${os_version_chevah}"
            fi
        elif [ $(command -v lsb_release) ]; then
            lsb_release_id=$(lsb_release -is)
            os_version_raw=$(lsb_release -rs)
            if [ $lsb_release_id = Ubuntu ]; then
                check_os_version "Ubuntu Long-term Support" 10.04 \
                    "$os_version_raw" os_version_chevah
                # Only Long-term Support versions are oficially endorsed, thus
                # $os_version_chevah should end in 04 and the first two digits
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
        check_os_version "Mac OS X" 10.4 "$os_version_raw" os_version_chevah

        # For now, no matter the actual OS X version returned, we use '108'.
        OS="osx108"

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
        # application and has math rounding error problems (at least with XL C).
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

if [ "$COMMAND" = "detect_os" ] ; then
    write_default_values
    exit 0
fi

if [ "$COMMAND" = "get_python" ] ; then
    get_binary_dist $2 "$BINARY_DIST_URI/python"
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
        install_brink
    fi
done

# Now that we have Python and Paver, let's call Paver from Python :)
set +e
${PYTHON_BIN} -c 'from paver.tasks import main; main()' "$@"
exit_code=$?
set -e
exit $exit_code
