# Copyright (c) 2010-2016 Adi Roiban.
# See LICENSE for details.
"""
Build script for chevah-compat.
"""
import os
import sys
import warnings

from brink.pavement_commons import (
    buildbot_list,
    buildbot_try,
    coverage_prepare,
    coverage_publish,
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
    test_coverage,
    test_python,
    test_remote,
    test_review,
    test_normal,
    test_super,
    )
from paver.easy import call_task, consume_args, needs, task

if os.name == 'nt':
    # Use shorter temp folder on Windows.
    import tempfile
    tempfile.tempdir = "c:\\temp"

# Keep run_packages in sync with setup.py.
RUN_PACKAGES = [
    'zope.interface==3.8.0',
    # Py3 compat.
    'future',
    ]

if os.name == 'posix':
    RUN_PACKAGES.extend([
        'python-daemon==1.5.5',
        # This is required as any other version will try to also update pip.
        'lockfile==0.9.1',
        'pam==0.1.4.c3',
        # Required for loading PAM lib on AIX.
        'arpy==1.1.1.c2',
        ])


BUILD_PACKAGES = [
    'sphinx==1.2.2',
    'repoze.sphinx.autointerface==0.7.1.c4',
    # Docutils is required for RST parsing and for Sphinx.
    'docutils==0.12.c1',

    'twisted==15.5.0.chevah3',

    # Buildbot is used for try scheduler
    'buildbot==0.8.11.c7',

    # For PQM
    'chevah-github-hooks-server==0.1.6',
    'smmap==0.8.2',
    'async==0.6.1',
    'gitdb==0.6.4',
    'gitpython==1.0.1',
    'pygithub==1.10.0',
    ]


TEST_PACKAGES = [
    'chevah-empirical==0.38.1',

    'pyflakes==0.8.1',
    'pocketlint==1.4.4.c4',

    # Used for py3 porting and other checks.
    'pylint==1.4.3',
    'pep8 >= 1.6.2',

    # Never version of nose, hangs on closing some tests
    # due to some thread handling.
    'nose==1.3.6',
    'mock',

    'coverage==4.0.3',
    'codecov==2.0.3',

    # We install wmi everywhere even though it is only used on Windows.
    'wmi==1.4.9',

    # Required for some unicode handling.
    'unidecode',

    'bunch',
    ]

# Make pylint shut up.
buildbot_list
buildbot_try
coverage_prepare
coverage_publish
default
github
harness
help
lint
merge_init
merge_commit
pqm
test_coverage
test_python
test_remote
test_review
test_normal
test_super

SETUP['product']['name'] = 'chevah-compat'
SETUP['folders']['source'] = u'chevah/compat'
SETUP['repository']['name'] = u'compat'
SETUP['repository']['github'] = u'https://github.com/chevah/compat'
SETUP['pocket-lint']['include_files'] = ['pavement.py', 'release-notes.rst']
SETUP['pocket-lint']['include_folders'] = ['chevah/compat']
SETUP['pocket-lint']['exclude_files'] = []
SETUP['test']['package'] = 'chevah.compat.tests'
SETUP['test']['elevated'] = 'elevated'
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
        arguments=RUN_PACKAGES + TEST_PACKAGES,
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
@needs('coverage_prepare')
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
@consume_args
def test_os_dependent(args):
    """
    Run os dependent tests.
    """
    call_task('test_python', args=args)

    # Only publish coverage for os dependent tests.
    codecov_token = os.environ.get('CODECOV_TOKEN', '')
    if codecov_token:
        # Only publish if we have a token.
        call_task('coverage_publish')


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

    if test_type == 'py3':
        return call_task('test_py3', args=args)

    return call_task('test_os_dependent', args=args)


@task
def test_py3():
    """
    Run checks for py3 compatibility.
    """
    from pylint.lint import Run
    from nose.core import main as nose_main
    arguments = ['--py3k', SETUP['folders']['source']]
    linter = Run(arguments, exit=False)
    stats = linter.linter.stats
    errors = (
        stats['info'] + stats['error'] + stats['refactor'] +
        stats['fatal'] + stats['convention'] + stats['warning']
        )
    if errors:
        print 'Pylint failed'
        sys.exit(1)

    print 'Compiling in Py3 ...',
    command = ['python3', '-m', 'compileall', '-q', 'chevah']
    pave.execute(command, output=sys.stdout)
    print 'done'

    sys.argv = sys.argv[:1]
    pave.python_command_normal.extend(['-3'])

    warnings.filterwarnings('always', module='chevah.empirical')
    captured_warnings = []

    def capture_warning(
        message, category, filename,
        lineno=None, file=None, line=None
            ):
        if not filename.startswith('chevah'):
            # Not our code.
            return
        line = (message.message, filename, lineno)
        if line in captured_warnings:
            # Don't include duplicate warnings.
            return
        captured_warnings.append(line)

    warnings.showwarning = capture_warning

    sys.args = ['nose', 'chevah.empirical.tests.normal']
    runner = nose_main(exit=False)
    if not runner.success:
        print 'Test failed'
        sys.exit(1)
    if not captured_warnings:
        sys.exit(0)

    print '\nCaptured warnings\n'
    for warning, filename, line in captured_warnings:
        print '%s:%s %s' % (filename, line, warning)
    sys.exit(1)
