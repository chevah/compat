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
ARCH='not-detected-yet'

# Initialize default values from paver.conf
PYTHON_CONFIGURATION='NOT-YET-DEFINED'
PYTHON_VERSION='not.defined.yet'
PYTHON_PLATFORM='unknown-os-and-arch'
PYTHON_NAME='python2.7'
BINARY_DIST_URI='https://binary.chevah.com/production'
PIP_INDEX='http://pypi.chevah.com'
BASE_REQUIREMENTS=''

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

    # AIX's find complains if there are no matching files when using +.
    [ $(uname) == AIX ] && touch ./dummy_file_for_AIX.pyc
    # Faster than '-exec rm {} \;' and supported in most OS'es,
    # details at http://www.in-ulm.de/~mascheck/various/find/#xargs
    find ./ -name '*.pyc' -exec rm {} +

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
    if [ $OS = "win" -a -d $target ]; then
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
        (>&2 echo "Failed:" $@)
        exit 1
    fi
}

#
# Update global variables with current paths.
#
update_path_variables() {
    resolve_python_version

    if [ "${OS}" = "win" ] ; then
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
    local version_configuration_array
    local candidate
    local candidate_platform
    local candidate_version

    PYTHON_PLATFORM="$OS-$ARCH"

    # Using ':' as a delimiter, populate a dedicated array.
    IFS=: read -a version_configuration_array <<< "$version_configuration"
    # Iterate through all the elements of the array to find the best candidate.
    for (( i=0 ; i < ${#version_configuration_array[@]}; i++ )); do
        candidate="${version_configuration_array[$i]}"
        candidate_platform=$(echo "$candidate" | cut -d "@" -f 1)
        candidate_version=$(echo "$candidate" | cut -d "@" -f 2)
        if [ "$candidate_platform" = "default" ]; then
            # On first pass, we set the default version.
            PYTHON_VERSION=$candidate_version
        elif [ "${PYTHON_PLATFORM%$candidate_platform*}" = "" ]; then
            # If matching a specific platform, we overwrite the default version.
            PYTHON_VERSION=$candidate_version
        fi
    done
}

write_default_values() {
    echo ${BUILD_FOLDER} ${PYTHON_NAME} ${OS} ${ARCH} > DEFAULT_VALUES
}


#
# Install base package.
#
install_base_deps() {
    echo "Installing base requirements: $BASE_REQUIREMENTS."
    pip_install "$BASE_REQUIREMENTS"
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
        pip install $1 \
            --trusted-host pypi.chevah.com \
            --index-url=$PIP_INDEX/simple \
            --build=${BUILD_FOLDER}/pip-build \
            --cache-dir=${CACHE_FOLDER}

    exit_code=$?
    set -e
    if [ $exit_code -ne 0 ]; then
        (>&2 echo "Failed to install brink.")
        exit 2
    fi
}

#
# Check for wget or curl and set needed download commands accordingly.
#
set_download_commands() {
    set +o errexit
    command -v wget > /dev/null
    if [ $? -eq 0 ]; then
        # Using WGET for downloading Python package.
        wget --version > /dev/null 2>&1
        if [ $? -ne 0 ]; then
            # This is not GNU Wget, could be the more frugal wget from Busybox.
            DOWNLOAD_CMD="wget"
        else
            # Use 1MB dots to reduce output and avoid polluting Buildbot pages.
            DOWNLOAD_CMD="wget --progress=dot --execute dot_bytes=1m"
        fi
        ONLINETEST_CMD="wget --spider --quiet"
        set -o errexit
        return
    fi
    command -v curl > /dev/null
    if [ $? -eq 0 ]; then
        # Using CURL for downloading Python package.
        DOWNLOAD_CMD="curl --remote-name"
        ONLINETEST_CMD="curl --fail --silent --head --output /dev/null"
        set -o errexit
        return
    fi
    (>&2 echo "Missing wget and curl! One is needed for online operations.")
    exit 3
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
        execute $DOWNLOAD_CMD $remote_base_url/${tar_gz_file}
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
    local target_file=python-${PYTHON_VERSION}-${OS}-${ARCH}.tar.gz

    $ONLINETEST_CMD $remote_base_url/${OS}/${ARCH}/$target_file
    return $?
}

#
# Download and extract in cache the python distributable.
#
get_python_dist() {
    local remote_base_url=$1
    local download_mode=$2
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
        (>&2 echo "Requested version was not found on the remote server.")
        exit 4
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
        (>&2 echo "Too many calls to copy_python: $COPY_PYTHON_RECURSIONS")
        exit 5
    fi

    # Check that python dist was installed
    if [ ! -s ${PYTHON_BIN} ]; then
        # We don't have a Python binary, so we install it since everything
        # else depends on it.
        echo "Bootstrapping ${LOCAL_PYTHON_BINARY_DIST} environment" \
            "to ${BUILD_FOLDER}..."
        mkdir -p ${BUILD_FOLDER}

        if [ -d ${python_distributable} ]; then
            # We have a cached distributable.
            # Check if is at the right version.
            local cache_ver_file
            cache_ver_file=${python_distributable}/lib/PYTHON_PACKAGE_VERSION
            cache_version='UNVERSIONED'
            if [ -f $cache_ver_file ]; then
                cache_version=`cat $cache_ver_file`
            fi
            if [ "$PYTHON_VERSION" != "$cache_version" ]; then
                # We have a different version in the cache.
                # Just remove it and hope that the next step will download
                # the right one.
                rm -rf ${python_distributable}
            fi
        fi

        if [ ! -d ${python_distributable} ]; then
            # We don't have a cached python distributable.
            echo "No ${LOCAL_PYTHON_BINARY_DIST} environment." \
                "Start downloading it..."
            get_python_dist "$BINARY_DIST_URI/python" "strict"
        fi

        echo "Copying Python distribution files... "
        cp -R ${python_distributable}/* ${BUILD_FOLDER}

        install_base_deps
        WAS_PYTHON_JUST_INSTALLED=1
    else
        # We have a Python, but we are not sure if is the right version.
        local version_file=${BUILD_FOLDER}/lib/PYTHON_PACKAGE_VERSION

        if [ -f $version_file ]; then
            # We have a versioned distribution.
            python_installed_version=`cat $version_file`
            if [ "$PYTHON_VERSION" != "$python_installed_version" ]; then
                # We have a different python installed.

                # Check if we have the to-be-updated version and fail if
                # it does not exists.
                set +o errexit
                test_version_exists "$BINARY_DIST_URI/python"
                local test_version=$?
                set -o errexit
                if [ $test_version -ne 0 ]; then
                    (>&2 echo "The build is now at $python_installed_version.")
                    (>&2 echo "Failed to find the required $PYTHON_VERSION.")
                    (>&2 echo "Check your configuration or the remote server.")
                    exit 6
                fi

                # Remove it and try to install it again.
                echo "Updating Python from" \
                    $python_installed_version to $PYTHON_VERSION
                rm -rf ${BUILD_FOLDER}/*
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
                rm -rf ${BUILD_FOLDER}/*
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
        (>&2 echo 'Failed to run the initial "./paver.sh deps" command.')
        exit 7
    fi
}


#
# Check that we have a pavement.py in the current dir.
# otherwise it means we are out of the source folder and paver can not be
# used there.
#
check_source_folder() {

    if [ ! -e pavement.py ]; then
        (>&2 echo 'No "pavement.py" file found in current folder.')
        (>&2 echo 'Make sure you are running "paver.sh" from a source folder.')
        exit 8
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

    if [[ $version_raw =~ [^[:digit:]\.] ]]; then
        (>&2 echo "OS version should only have numbers and periods, but:")
        (>&2 echo "    \$version_raw=$version_raw")
        exit 12
    fi

    # Using '.' as a delimiter, populate the version_* arrays.
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
        (>&2 echo "Current version of ${name_fancy} is too old: ${version_raw}")
        (>&2 echo "Oldest supported ${name_fancy} version is: ${version_good}")
        if [ "$OS" = "Linux" ]; then
            # For old and/or unsupported Linux distros there's a second chance!
            check_linux_glibc
        else
            exit 13
        fi
    fi

    # The sane way to return fancy values with a bash function is to use eval.
    eval $version_chevah="'$version_constructed'"
}

#
# For old unsupported Linux distros (some with no /etc/os-release) and for other
# unsupported Linux distros (eg. Arch), we check if the system is glibc-based.
# If so, we use a generic code path that builds everything statically,
# including OpenSSL, thus only requiring glibc 2.x.
#
check_linux_glibc() {
    local glibc_version
    local glibc_version_array

    echo "Unsupported Linux distribution detected!"
    echo "To get you going, we'll try to treat it as generic Linux..."

    set +o errexit

    command -v ldd > /dev/null
    if [ $? -ne 0 ]; then
        (>&2 echo "No ldd binary found, can't check for glibc!")
        exit 18
    fi

    ldd --version | egrep "GNU\ libc|GLIBC" > /dev/null
    if [ $? -ne 0 ]; then
        (>&2 echo "No glibc reported by ldd... Unsupported Linux libc?")
        exit 19
    fi

    # Parsing tested with glibc 2.11.x and 2.29, eglibc 2.13 and 2.19.
    glibc_version=$(ldd --version | head -n 1 | rev | cut -d\  -f1 | rev)

    if [[ $glibc_version =~ [^[:digit:]\.] ]]; then
        (>&2 echo "Glibc version should only have numbers and periods, but:")
        (>&2 echo "    \$glibc_version=$glibc_version")
        exit 20
    fi

    IFS=. read -a glibc_version_array <<< "$glibc_version"

    if [ ${glibc_version_array[0]} -ne 2 ]; then
        (>&2 echo "Only glibc 2 is supported! Detected version: $glibc_version")
        exit 21
    fi

    # We pass here because:
    #   1. In python-package building should work with older glibc version.
    #   2. Our generic "lnx" runtime might work with a slightly older glibc 2.
    if [ ${glibc_version_array[1]} -lt 11 ]; then
        (>&2 echo "Beware glibc versions older than 2.11 were NOT tested!")
        (>&2 echo "Detected glibc version: $glibc_version")
    fi

    set -o errexit

    # glibc 2 detected, we set $OS for a generic build.
    OS="lnx"
}

#
# For glibc-based Linux distros, after checking if current version is
# supported with check_os_version(), $OS might already be set to "lnx"
# if current version is too old, through check_linux_glibc().
#
set_os_if_not_generic() {
    local distro_name="$1"
    local distro_version="$2"

    if [ "$OS" != "lnx" ]; then
        OS="${distro_name}${distro_version}"
    fi
}

#
# Detect OS and ARCH for the current system.
# In some cases we normalize or even override ARCH at the end of this function.
#
detect_os() {

    OS=$(uname -s)

    case "$OS" in
        MINGW*|MSYS*)
            ARCH=$(uname -m)
            OS="win"
            ;;
        Linux)
            ARCH=$(uname -m)
            if [ ! -f /etc/os-release ]; then
                # No /etc/os-release file present, so we don't support this
                # distro, but check for glibc, the generic build should work.
                check_linux_glibc
            else
                source /etc/os-release
                linux_distro="$ID"
                distro_fancy_name="$NAME"
                # Some rolling-release distros (eg. Arch Linux) have
                # no VERSION_ID here, so don't count on it unconditionally.
                case "$linux_distro" in
                    rhel|centos)
                        os_version_raw="$VERSION_ID"
                        check_os_version "Red Hat Enterprise Linux" 7 \
                            "$os_version_raw" os_version_chevah
                        set_os_if_not_generic "rhel" $os_version_chevah
                        if [ "$os_version_chevah" -eq 7 ]; then
                            if openssl version | grep -F -q "1.0.1"; then
                                # 7.0-7.3 has OpenSSL 1.0.1, use generic build.
                                check_linux_glibc
                            fi
                        fi
                        ;;
                    amzn)
                        os_version_raw="$VERSION_ID"
                        check_os_version "$distro_fancy_name" 2 \
                            "$os_version_raw" os_version_chevah
                        set_os_if_not_generic "amzn" $os_version_chevah
                        ;;
                    ubuntu|ubuntu-core)
                        os_version_raw="$VERSION_ID"
                        # 12.04/14.04 have OpenSSL 1.0.1, use generic Linux.
                        check_os_version "$distro_fancy_name" 16.04 \
                            "$os_version_raw" os_version_chevah
                        # Only LTS versions are supported. If it doesn't end in
                        # 04 or first two digits are uneven, use generic build.
                        if [ ${os_version_chevah%%04} == ${os_version_chevah} \
                            -o $(( ${os_version_chevah:0:2} % 2 )) -ne 0 ]; then
                            check_linux_glibc
                        fi
                        set_os_if_not_generic "ubuntu" $os_version_chevah
                        ;;
                    alpine)
                        os_version_raw="$VERSION_ID"
                        check_os_version "$distro_fancy_name" 3.6 \
                            "$os_version_raw" os_version_chevah
                        set_os_if_not_generic "alpine" $os_version_chevah
                        ;;
                    *)
                        # Unsupported modern distros such as SLES, Debian, etc.
                        check_linux_glibc
                        ;;
                esac
            fi
            ;;
        Darwin)
            ARCH=$(uname -m)
            os_version_raw=$(sw_vers -productVersion)
            # Tested on 10.13, but this works on 10.12 too. Older versions need
            # "-Wl,-no_weak_imports" in LDFLAGS to avoid runtime issues. More
            # details at https://github.com/Homebrew/homebrew-core/issues/3727.
            check_os_version "macOS" 10.12 "$os_version_raw" os_version_chevah
            # Build a generic package to cover all supported versions.
            OS="macos"
            ;;
        FreeBSD)
            ARCH=$(uname -m)
            os_version_raw=$(uname -r | cut -d'.' -f1)
            check_os_version "FreeBSD" 11 "$os_version_raw" os_version_chevah
            OS="fbsd${os_version_chevah}"
            ;;
        OpenBSD)
            ARCH=$(uname -m)
            os_version_raw=$(uname -r)
            check_os_version "OpenBSD" 6.5 "$os_version_raw" os_version_chevah
            OS="obsd${os_version_chevah}"
            ;;
        SunOS)
            ARCH=$(isainfo -n)
            os_version_raw=$(uname -r | cut -d'.' -f2)
            check_os_version Solaris 10 "$os_version_raw" os_version_chevah
            OS="sol${os_version_chevah}"
            case "$OS" in
                sol10)
                    # Solaris 10u8 (from 10/09) updated libc version, so for
                    # older releases up to 10u7 (from 5/09) we build on 10u3.
                    # The "sol10u3" code path also shows the way to link to
                    # OpenSSL 0.9.7 libs bundled in /usr/sfw/ with Solaris 10.
                    # Update number is taken from first line of /etc/release.
                    un=$(head -1 /etc/release | cut -d_ -f2 | sed s/[^0-9]*//g)
                    if [ "$un" -lt 8 ]; then
                        OS="sol10u3"
                    fi
                    ;;
                sol11)
                    # Solaris 11 releases prior to 11.4 bundled OpenSSL libs
                    # missing support for Elliptic-curve crypto. From here on:
                    #   * Solaris 11.4 (or newer) with OpenSSL 1.0.2 is "sol11",
                    #   * Solaris 11.2/11.3 with OpenSSL 1.0.1 is "sol112",
                    #   * Solaris 11.0/11.1 with OpenSSL 1.0.0 is not supported.
                    minor_version=$(uname -v | cut -d'.' -f2)
                    if [ "$minor_version" -lt 4 ]; then
                        OS="sol112"
                    fi
                    ;;
            esac
            ;;
        AIX)
            ARCH="ppc$(getconf HARDWARE_BITMODE)"
            os_version_raw=$(oslevel)
            check_os_version AIX 5.3 "$os_version_raw" os_version_chevah
            OS="aix${os_version_chevah}"
            ;;
        HP-UX)
            ARCH=$(uname -m)
            os_version_raw=$(uname -r | cut -d'.' -f2-)
            check_os_version HP-UX 11.31 "$os_version_raw" os_version_chevah
            OS="hpux${os_version_chevah}"
            ;;
        *)
            (>&2 echo "Unsupported operating system: ${OS}.")
            exit 14
    esac

    # Normalize arch names. Force 32bit builds on some OS'es.
    case "$ARCH" in
        "i386"|"i686")
            ARCH="x86"
            ;;
        "amd64"|"x86_64")
            ARCH="x64"
            case "$OS" in
                sol10*)
                    # On Solaris 10, x64 built fine prior to adding "bcrypt".
                    ARCH="x86"
                    ;;
                win)
                    # 32bit build on Windows 2016, 64bit otherwise.
                    # Should work with a l10n pack too (tested with French).
                    win_ver=$(systeminfo.exe | head -n 3 | tail -n 1 \
                        | cut -d ":" -f 2 | cut -b 15-43)
                    if [ "$win_ver" = "Microsoft Windows Server 2016" ]; then
                        ARCH="x86"
                    fi
                    ;;
            esac
            ;;
        "aarch64")
            ARCH="arm64"
            ;;
        "ppc64")
            # Python has not been fully tested on AIX when compiled as a 64bit
            # binary, and has math rounding error problems (at least with XL C).
            ARCH="ppc"
            ;;
        "sparcv9")
            # We build 32bit binaries on SPARC too. Use "sparc64" for 64bit.
            ARCH="sparc"
            ;;
    esac
}

detect_os
update_path_variables
set_download_commands

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
    get_python_dist "$BINARY_DIST_URI/python" "fallback"
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
