# Copyright (c) 2010-2013 Adi Roiban.
# See LICENSE for details.
"""
Build script for chevah-compat.
"""
from __future__ import with_statement
import os
import sys

# Marker for paver.sh.
# This value is pavers by bash. Use a strict format.
BRINK_VERSION = '0.9.0'

EXTRA_PACKAGES = [
    'chevah-utils==0.3.4',
    'chevah-empirical==0.3.2',
    ]

if os.name == 'posix':
    EXTRA_PACKAGES.extend(['pam>=0.1.4.chevah'])

from brink.pavement_commons import (
    _p,
    buildbot_list,
    buildbot_try,
    default,
    github,
    harness,
    help,
    lint,
    pave,
    SETUP,
    test,
    test_remote,
    test_normal,
    test_super,
    )
from paver.easy import task

# Make pylint shut up.
buildbot_list
buildbot_try
default
github
harness
help
lint
test
test_remote
test_normal
test_super

SETUP['product']['name'] = 'chevah-compat'
SETUP['folders']['source'] = u'chevah/compat'
SETUP['repository']['name'] = u'compat'
SETUP['github']['url'] = 'https://github.com/chevah/compat'
SETUP['pocket-lint']['include_files'] = ['pavement.py']
SETUP['pocket-lint']['include_folders'] = ['chevah/compat']
SETUP['pocket-lint']['exclude_files'] = []
SETUP['test']['package'] = 'chevah.compat.tests'
SETUP['test']['elevated'] = 'elevated'


@task
def deps():
    """
    Copy external dependencies.
    """
    print('Installing dependencies to %s...' % (pave.path.build))
    pave.installRunDependencies(extra_packages=EXTRA_PACKAGES)
    pave.installBuildDependencies()


@task
def build():
    """
    Copy new source code to build folder.
    """
    build_target = _p([pave.path.build, 'setup-build'])
    sys.argv = ['setup.py', 'build', '--build-base', build_target]
    print "Building in " + build_target
    import setup
    setup.distribution.run_command('install')
