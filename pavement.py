# Copyright (c) 2010-2013 Adi Roiban.
# See LICENSE for details.
"""
Build script for chevah-compat.
"""
import os
import sys

if os.name == 'nt':
    # Use shorter temp folder on Windows.
    import tempfile
    tempfile.tempdir = "c:\\temp"

# Keep run_packages in sync with setup.py.
RUN_PACKAGES = [
    'zope.interface==3.8.0',
    ]

if os.name == 'posix':
    RUN_PACKAGES.extend([
        'python-daemon==1.5.5',
        'pam==0.1.4.c3',
        ])

if sys.platform.startswith('aix'):
    RUN_PACKAGES.append('arpy==1.1.1-c1')


BUILD_PACKAGES = [
    'sphinx==1.1.3-chevah1',
    'repoze.sphinx.autointerface==0.7.1-chevah2',
    # Docutils is required for RST parsing and for Sphinx.
    'docutils>=0.9.1-chevah2',

    'twisted==12.1.0-chevah3',

    # Buildbot is used for try scheduler
    'buildbot==0.8.11.pre.143.gac88f1b.c2',

    # For PQM
    'chevah-github-hooks-server==0.1.6',
    'smmap==0.8.2',
    'async==0.6.1',
    'gitdb==0.5.4',
    'gitpython==0.3.2.RC1',
    'pygithub==1.10.0',
    ]


TEST_PACKAGES = [
    'chevah-empirical==0.30.1',

    'pyflakes==0.7.3',
    'pocketlint==1.4.4.c4',

    # Never version of nose, hangs on closing some tests
    # due to some thread handling.
    'nose==1.1.2-chevah1',
    'mock',

    # We install wmi everywhere even though it is only used on Windows.
    'wmi==1.4.9',

    # Test SFTP service using a 3rd party client.
    'paramiko',

    # Required for some unicode handling.
    'unidecode',

    'bunch',
    ]


from brink.pavement_commons import (
    buildbot_list,
    buildbot_try,
    default,
    github,
    harness,
    help,
    lint,
    merge_init,
    merge_commit,
    pave,
    pqm,
    SETUP,
    test_python,
    test_remote,
    test_review,
    test_normal,
    test_super,
    )
from paver.easy import call_task, consume_args, needs, task

# Make pylint shut up.
buildbot_list
buildbot_try
default
github
harness
help
lint
merge_init
merge_commit
pqm
test_python
test_remote
test_review
test_normal
test_super

SETUP['product']['name'] = 'chevah-compat'
SETUP['folders']['source'] = u'chevah/compat'
SETUP['repository']['name'] = u'compat'
SETUP['github']['repo'] = 'chevah/compat'
SETUP['pocket-lint']['include_files'] = ['pavement.py', 'release-notes.rst']
SETUP['pocket-lint']['include_folders'] = ['chevah/compat']
SETUP['pocket-lint']['exclude_files'] = []
SETUP['test']['package'] = 'chevah.compat.tests'
SETUP['test']['elevated'] = 'elevated'
SETUP['github']['url'] = 'https://github.com/chevah/compat'
SETUP['buildbot']['server'] = 'build.chevah.com'
SETUP['buildbot']['web_url'] = 'http://build.chevah.com:10088'
SETUP['pypi']['index_url'] = 'http://pypi.chevah.com:10042/simple'


@task
@needs('deps_testing', 'deps_build')
def deps():
    """
    Install all dependencies.
    """


@task
def deps_testing():
    """
    Install dependencies for testing.
    """
    print('Installing testing dependencies to %s...' % (pave.path.build))
    pave.pip(
        command='install',
        arguments=RUN_PACKAGES,
        silent=True,
        )
    pave.pip(
        command='install',
        arguments=TEST_PACKAGES,
        silent=True,
        )


@task
@needs('deps_testing')
def deps_build():
    """
    Install dependencies for build environment.
    """
    print('Installing build dependencies to %s...' % (pave.path.build))
    pave.pip(
        command='install',
        arguments=BUILD_PACKAGES,
        silent=True,
        )


@task
def build():
    """
    Copy new source code to build folder.
    """
    # Clean previous files.
    pave.fs.deleteFolder([
        pave.path.build, pave.getPythonLibPath(), 'chevah', 'compat',
        ])
    pave.fs.deleteFolder([pave.path.build, 'setup-build'])

    build_target = pave.fs.join([pave.path.build, 'setup-build'])
    sys.argv = ['setup.py', '-q', 'build', '--build-base', build_target]
    print "Building in " + build_target
    # Importing setup will trigger executing commands from sys.argv.
    import setup
    setup.distribution.run_command('install')


@task
@needs('deps_testing', 'test_python')
@consume_args
def test_os_dependent(args):
    """
    Run os dependent tests.
    """


@task
@needs('deps_build')
@consume_args
def test_os_independent(args):
    """
    Run os independent tests.
    """
    call_task('lint', options={'all': True})


@task
@needs('test_python')
@consume_args
def test(args):
    """
    Run all Python tests.
    """


@task
# It needs consume_args to initialize the paver environment.
@consume_args
def test_ci(args):
    """
    Run tests in continuous integration environment.
    """
    env = os.environ.copy()
    args = env.get('TEST_ARGUMENTS', '')
    if not args:
        args = []
    else:
        args = [args]
    test_type = env.get('TEST_TYPE', 'normal')

    if test_type == 'os-independent':
        return call_task('test_os_independent')

    return call_task('test_os_dependent', args=args)
