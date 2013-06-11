#!/usr/bin/env bash
# Copyright (c) 2010-2013 Adi Roiban.
# See LICENSE for details.
#
# Helper script for bootstraping the build system on Unix/Msys.
# It will write the default values into 'DEFAULT_VALUES' file.

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
PROJECT_ROOT=""
BOOTSTRAP_PATH=""
BUILD_FOLDER=""
PYTHON_BIN=""
PYTHON_LIB=""


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
# Update global variables with current paths.
#
update_path_variables() {

    # Initialize PROJECT_ROOT and later fix it.
    PROJECT_ROOT=`pwd`
    PROJECT_ROOT=${PROJECT_ROOT%chevah*}
    PROJECT_ROOT=${PROJECT_ROOT}chevah

    if [ "${OS}" = "windows" ] ; then
        PYTHON_BIN="/lib/python.exe"
        PYTHON_LIB="/lib/Lib/"
    else
        PYTHON_BIN="/bin/python"
        PYTHON_LIB="/lib/${PYTHON_VERSION}/"
    fi

    BOOTSTRAP_PATH=${PROJECT_ROOT}/brink

    BUILD_FOLDER="build-${OS}-${ARCH}"
    PYTHON_BIN="${BUILD_FOLDER}${PYTHON_BIN}"
    PYTHON_LIB="${BUILD_FOLDER}${PYTHON_LIB}"

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
    exit_code=$?

    # This code will be deprecated in future versions since we will no longer
    # support pavement_lib imports.
    if [ $exit_code -ne 0 ]; then
        # Brink version was not found, so we go with default.
        echo "Installing latest version of pavement_lib.py..."
        PAVEMENT_LIB_PATH=${BOOTSTRAP_PATH}/pavement_commons.py
        cp ${PAVEMENT_LIB_PATH} pavement_lib.py
        return
    fi

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

    ${PYTHON_BIN} -m \
        pip.__init__ install chevah-brink==$version \
            --index-url=http://172.20.0.1:10042/simple \
            --download-cache=${PROJECT_ROOT}/brink/cache/pypi \
            --find-links=file://${PROJECT_ROOT}/brink/cache/pypi \
            --upgrade

    exit_code=$?
    if [ $exit_code -ne 0 ]; then
        echo "Failed to install brink."
        exit 1
    fi
}

get_python_version() {
    raw_version=`grep "PYTHON_VERSION =" pavement.py`
    exit_code=$?
    if [ $exit_code -ne 0 ]; then
        # Python version was not found, so we go with default.
        return
    fi 

    # Extract version and remove quotes.
    version=${raw_version#PYTHON_VERSION = }
    version=${version#\'}
    version=${version%\'}
    version=${version#\"}
    version=${version%\"}
    PYTHON_VERSION="python$version"
}

#
# Copy python to build folder from binary distribution.
#
copy_python() {

    PYTHON_DISTRIBUTABLE=${BOOTSTRAP_PATH}/cache/${PYTHON_VERSION}-${OS}-${ARCH}

    # Check that python dist was installed
    if [ ! -s ${PYTHON_BIN} ]; then
        # Install python-dist since everything else depends on it.
        echo "Bootstraping ${PYTHON_VERSION} environment to ${BUILD_FOLDER}..."
        mkdir -p ${BUILD_FOLDER}

        # If we don't have a cached python distributable,
        # get one.
        if [ ! -d ${PYTHON_DISTRIBUTABLE} ]; then
            echo "No ${PYTHON_VERSION} environment. Start downloading it..."
            pushd ${BOOTSTRAP_PATH}
            git pull
            ./make-it-happen.sh get_python ${PYTHON_VERSION} ${OS}-${ARCH}
            popd
        fi

        cp -R ${PYTHON_DISTRIBUTABLE}/* ${BUILD_FOLDER}
        cp -r ${BUILD_FOLDER}/lib/config/include ${BUILD_FOLDER}/
        # Copy pywintypes25.dll as it is required by paver on windows.
        if [ "$OS" = "windows" ]; then
            cp -R ${PYTHON_DISTRIBUTABLE}/lib/pywintypes25.dll .
        fi

        WAS_PYTHON_JUST_INSTALLED=1
    fi
}


# Copy base python packages to Python.
# We can not install them using pip, since we don't have pip or easy_install.
copy_base_packages() {
    # Always update paver ... at least until we have a stable buildsystem.
    cp -RL ${BOOTSTRAP_PATH}/paver/paver ${PYTHON_LIB}/site-packages/
    cp -RL ${BOOTSTRAP_PATH}/pip/pip ${PYTHON_LIB}/site-packages/
    cp -RL ${BOOTSTRAP_PATH}/distribute/setuptools ${PYTHON_LIB}/site-packages/
    cp -RL ${BOOTSTRAP_PATH}/distribute/distribute.egg-info ${PYTHON_LIB}/site-packages/
    cp ${BOOTSTRAP_PATH}/distribute/pkg_resources.py ${PYTHON_LIB}/site-packages/
    cp ${BOOTSTRAP_PATH}/distribute/easy_install.py ${PYTHON_LIB}/site-packages/
}


#
# Install dependencies after python was just installed.
#
install_dependencies(){

    if [ $WAS_PYTHON_JUST_INSTALLED -ne 1 ]; then
        return
    fi

    install_brink

    ${PYTHON_BIN} -c 'from paver.tasks import main; main()' deps
    python_exit_code=$?
    if [ $python_exit_code -ne 0 ]; then
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
                '2.1')
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
PYTHON_VERSION="python2.5"

detect_os
get_python_version
update_path_variables

if [ "$1" = "clean" ] ; then
    clean_build
    exit 0
fi

if [ "$1" = "get_default_values" ] ; then
    write_default_values
    exit 0
fi

check_source_folder
write_default_values
copy_python
copy_base_packages
install_dependencies

# Always update brink when running buildbot tasks.
for paver_task in "deps" "test_os_dependent" "test_os_independent"; do
    if [ "$1" == "$paver_task" ] ; then
        install_brink
    fi
done

# Now that we have Python and Paver, let's call Paver from Python :)
${PYTHON_BIN} -c 'from paver.tasks import main; main()' $@
python_exit_code=$?
exit $python_exit_code
