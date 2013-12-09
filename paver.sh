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

# Script initialization.
set -o nounset
set -o errexit
set -o pipefail

# Initialize default value.
COMMAND=${1-''}
DEBUG=${DEBUG-0}

BINARY_DIST_URI="http://binary.chevah.com/production/python"
PAVER_VERSION='1.2.1'
PIP_VERSION="1.4.1-c1"
SETUPTOOLS_VERSION="1.4.1"

# Set default locale.
# We use C (alias for POSIX) for having a basic default value and
# to make sure we explictly convert all unicode values.
export LANG='C'
export LANGUAGE='C'
export LC_ALL='C'
export LC_CTYPE='C'
export LC_COLLATE='C'
export LC_MESSAGES='C'
export PATH=$PATH:'/sbin:/usr/sbin'

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


clean_build() {
    # Shortcut for clear since otherwise it will depend on python
    echo "Removing ${BUILD_FOLDER}..."
    rm -rf ${BUILD_FOLDER}
    echo "Removing dist..."
    rm -rf ${DIST_FOLDER}
    echo "Removing publish..."
    rm -rf 'publish'
    echo "Cleaning project temporary files..."
    rm -f DEFAULT_VALUES
    rm -f pavement_lib.py*
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
    echo ${BUILD_FOLDER} ${PYTHON_VERSION} ${OS} ${ARCH} > DEFAULT_VALUES
}


#
# Install brink package.
#
install_brink() {
    raw_version=`grep "BRINK_VERSION =" pavement.py`

    # Extract version and remove quotes.
    version=${raw_version#BRINK_VERSION = }
    version=${version#\'}
    version=${version%\'}
    version=${version#\"}
    version=${version%\"}

    if [ "$version" = "skip" ]; then
        echo "Skipping brink installation."
        return
    fi

    echo "Installing version: chevah-brink==$version of brink..."

    pip install "chevah-brink==$version"
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
            --index-url=http://172.20.0.1:10042/simple \
            --download-cache=${CACHE_FOLDER}/pypi \
            --find-links=file://${CACHE_FOLDER}/cache/pypi \
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
    dist_name=$1

    echo "Getting $dist_name ..."

    tar_gz_file=${dist_name}.tar.gz
    tar_file=${dist_name}.tar

    mkdir -p ${CACHE_FOLDER}
    pushd ${CACHE_FOLDER}

        # Get and extract archive.
        rm -rf $dist_name
        rm -f $tar_gz_file
        rm -f $tar_file
        # Use 1M dot to reduce console polution.
        execute wget --progress=dot -e dotbytes=1M $BINARY_DIST_URI/${tar_gz_file}
        execute gunzip $tar_gz_file
        execute tar -xf $tar_file
        rm -f $tar_gz_file
        rm -f $tar_file

    popd
}

#
# Return a version defined in pavement.py file.
#
get_version_from_pavement() {
    local name
    local raw_version
    local version=''

    name=$1

    set +e
    raw_version=`grep "$name =" pavement.py`
    exit_code=$?
    set -e
    if [ $exit_code -ne 0 ]; then
        # Version was not found, so we go with default.
        return version
    fi

    # Extract version and remove quotes.
    version=${raw_version#$name = }
    version=${version#\'}
    version=${version%\'}
    version=${version#\"}
    version=${version%\"}

    echo $version
}


#
# Return the version of python used in the current repository.
#
get_python_version() {
    local version

    version=$(get_version_from_pavement PYTHON_VERSION)

    echo "python$version"
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
            get_binary_dist ${PYTHON_VERSION}-${OS}-${ARCH}
            get_binary_dist "$pip_package"
            get_binary_dist "$setuptools_package"
        fi

        echo "Copying bootstraping files... "
        cp -R ${python_distributable}/* ${BUILD_FOLDER}

        cp -RL "${CACHE_FOLDER}/$pip_package/pip" ${PYTHON_LIB}/site-packages/
        cp -RL "${CACHE_FOLDER}/$setuptools_package/setuptools" ${PYTHON_LIB}/site-packages/
        cp -RL "${CACHE_FOLDER}/$setuptools_package//setuptools.egg-info" ${PYTHON_LIB}/site-packages/
        cp "${CACHE_FOLDER}/$setuptools_package/pkg_resources.py" ${PYTHON_LIB}/site-packages/
        cp "${CACHE_FOLDER}/$setuptools_package/easy_install.py" ${PYTHON_LIB}/site-package

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
# Update OS and ARCH variables with the current values.
#
detect_os() {
    OS=`uname -s | tr '[:upper:]' '[:lower:]'`

    if [ "${OS%mingw*}" = "" ] ; then

        OS='windows'
        ARCH='x86'

    elif [ "${OS}" = "sunos" ] ; then

        OS="solaris"
        ARCH=`uname -p`
        VERSION=`uname -r`

        if [ "$ARCH" = "i386" ] ; then
            ARCH='x86'
        fi

        if [ "$VERSION" = "5.10" ] ; then
            OS="solaris10"
        fi

    elif [ "${OS}" = "aix" ] ; then

        release=`oslevel`
        case $release in
            5.1.*)
                OS='aix51'
                ARCH='ppc'
                ;;
            *)
                # By default we go for AIX 5.3 on PPC64
                OS='aix53'
                ARCH='ppc64'
            ;;
        esac

    elif [ "${OS}" = "hp-ux" ] ; then

        OS="hpux"
        ARCH=`uname -m`

    elif [ "${OS}" = "linux" ] ; then

        ARCH=`uname -m`

        if [ -f /etc/redhat-release ] ; then
            # Careful with the indentation here.
            # Make sure rhel_version does not has spaces before and after the
            # number.
            rhel_version=`\
                cat /etc/redhat-release | sed s/.*release\ // | sed s/\ .*//`
            # RHEL4 glibc is not compatible with RHEL 5 and 6.
            rhel_major_version=${rhel_version%.*}
            if [ "$rhel_major_version" = "4" ] ; then
                OS='rhel4'
            elif [ "$rhel_major_version" = "5" ] ; then
                OS='rhel5'
            elif [ "$rhel_major_version" = "6" ] ; then
                OS='rhel6'
            else
                echo 'Unsuported RHEL version.'
                exit 1
            fi
        elif [ -f /etc/SuSE-release ] ; then
            sles_version=`\
                grep VERSION /etc/SuSE-release | sed s/VERSION\ =\ //`
            if [ "$sles_version" = "11" ] ; then
                OS='sles11'
            else
                echo 'Unsuported SLES version.'
                exit 1
            fi
        elif [ -f /etc/lsb-release ] ; then
            release=`lsb_release -sr`
            case $release in
                '10.04' | '10.10' | '11.04' | '11.10')
                    OS='ubuntu1004'
                ;;
                '12.04' | '12.10' | '13.04' | '13.10')
                    OS='ubuntu1204'
                ;;
                # Lie for dumol's Gentoo. Separate so that it's clear
                '2.2')
                    OS='ubuntu1204'
                ;;
                *)
                    echo 'Unsuported Ubuntu version.'
                    exit 1
                ;;
            esac

        elif [ -f /etc/slackware-version ] ; then

            # For Slackware, for now we use Ubuntu 10.04.
            # Special dedication for all die hard hackers like Ion.
    	    OS="ubuntu1004"

        elif [ -f /etc/debian_version ] ; then
            OS="debian"

        fi

    elif [ "${OS}" = "darwin" ] ; then
        osx_version=`sw_vers -productVersion`
        osx_major_version=${osx_version%.*}
    	if [ "$osx_major_version" = "10.4" ] ; then
    		OS='osx104'
    	else
    		echo 'Unsuported OS X version.'
    		exit 1
    	fi

    	osx_arch=`uname -m`
    	if [ "$osx_arch" = "Power Macintosh" ] ; then
    		ARCH='ppc'
    	else
    		echo 'Unsuported OS X architecture.'
    		exit 1
    	fi
    else
        echo 'Unsuported operating system.'
        exit 1
    fi

    # Fix arch names.
    if [ "$ARCH" = "i686" ] ; then
        ARCH='x86'

    fi
    if [ "$ARCH" = "i386" ] ; then
        ARCH='x86'
    fi

    if [ "$ARCH" = "x86_64" ] ; then
        ARCH='x64'
    fi
}

# Put default values and create them as global variables.
OS='not-detected-yet'
ARCH='x86'
PYTHON_VERSION=$(get_python_version)

detect_os
update_path_variables

if [ "$COMMAND" = "clean" ] ; then
    clean_build
    exit 0
fi

if [ "$COMMAND" = "get_default_values" ] ; then
    write_default_values
    exit 0
fi

if [ "$COMMAND" = "get_python" ] ; then
    get_binary_dist $2
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
