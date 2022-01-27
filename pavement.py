# Copyright (c) 2010-2016 Adi Roiban.
# See LICENSE for details.
"""
Build script for chevah-compat.
"""
import compileall
import imp
import os
import py_compile
import struct
import sys

from brink.pavement_commons import (
    buildbot_list,
    buildbot_try,
    coverage_prepare,
    codecov_publish,
    default,
    help,
    lint,
    merge_init,
    merge_commit,
    pave,
    pqm,
    SETUP,
    test_coverage,
    test_diff,
    test_python,
    test_remote,
    test_normal,
    test_super,
    )
from paver.easy import call_task, consume_args, environment, needs, pushd, task

if os.name == 'nt':
    # Use shorter temp folder on Windows.
    import tempfile
    import win32api

    # Create the short temp.
    tempfile.tempdir = "c:\\temp"
    try:
        os.mkdir(tempfile.tempdir)
    except OSError:
        pass

    # Create default temp.
    if not os.path.exists(win32api.GetTempPath()):
        os.mkdir(win32api.GetTempPath())


# Keep run_packages in sync with setup.py.
# These are the hard dependencies needed by the library itself.
RUN_PACKAGES = [
    'zope.interface==5.4.0+chevah.2',
    'six==1.15.0',
    ]

if os.name == 'posix':
    RUN_PACKAGES.extend([
        # This is required as any other version will try to also update pip.
        'lockfile==0.9.1',
        'pam==0.1.4.c3',
        # Required for loading PAM libs on AIX.
        'arpy==1.1.1.c2',
        ])

# Packages required to use the dev/build system.
BUILD_PACKAGES = [
    # For Lint and static checkers.
    'scame==0.6.3',
    'pyflakes>=2.4.0',
    'pycodestyle==2.8.0',
    'pylint==1.9.4',
    'astroid==1.6.6',
    # These are build packages, but are needed for testing the documentation.
    'sphinx==4.2.0',

    # Packages required to run the test suite.
    'nose==1.3.7',
    'nose-randomly==1.2.5',
    'mock',

    'coverage==6.3',
    'diff_cover==6.4.4',
    'codecov==2.1.12',

    # Twisted is optional, but we have it here for complete tests.
    'Twisted==20.3.0+chevah.3',
    'service_identity==21.1.0',

    # We install wmi everywhere even though it is only used on Windows.
    'wmi==1.4.9',

    # Used to detect Linux distributions.
    'ld==0.5.0',

    # Required for some unicode handling.
    'unidecode',

    'bunch',
    ]

# Make pylint shut up.
buildbot_list
buildbot_try
coverage_prepare
codecov_publish
default
help
lint
merge_init
merge_commit
pqm
test_coverage
test_diff
test_python
test_remote
test_normal
test_super

try:
    from scame.formatcheck import ScameOptions

    class CompatScameOptions(ScameOptions):
        """
        Scame options for the this project.
        """
        test_options = {}

        def get(self, option, path):
            tests_path = os.path.join('chevah', 'compat', 'tests')
            testing_path = os.path.join('chevah', 'compat', 'testing')
            admin_path = os.path.join('chevah', 'compat', 'administration.py')
            if (
                tests_path in path or
                testing_path in path or
                admin_path in path or
                path == 'pavement.py'
                    ):
                # We have a testing code.
                test_value = self.test_options.get(option, None)
                if test_value is not None:
                    return test_value

            return getattr(self, option)

    options = CompatScameOptions()
    options.max_line_length = 80
    options.progress = True

    options.scope = {
        'include': [
            'pavement.py',
            'example/',
            'README.rst',
            'chevah/compat/',
            ],
        'exclude': [],
        }

    options.towncrier = {
        'enabled': True,
        'fragments_directory': None,
        'excluded_fragments': 'readme.rst',
        }

    options.pyflakes['enabled'] = True

    options.pycodestyle['enabled'] = True
    options.pycodestyle['hang_closing'] = True

    options.bandit['enabled'] = False

    # For now pylint is disabled, as there are to many errors.
    options.pylint['enabled'] = False
    options.pylint['disable'] = ['C0103', 'C0330', 'R0902', 'W0212']


except ImportError:
    # This will fail before we run `./brink.sh deps`
    options = None


SETUP['product']['name'] = 'chevah-compat'
SETUP['folders']['source'] = 'chevah/compat'
SETUP['repository']['name'] = 'compat'
SETUP['repository']['github'] = 'https://github.com/chevah/compat'
SETUP['scame'] = options
SETUP['test']['package'] = 'chevah.compat.tests'
SETUP['test']['elevated'] = 'elevated'
SETUP['test']['nose_options'] = ['--with-randomly']
SETUP['test']['coverator_url'] = 'http://coverator.chevah.com:8080'
SETUP['buildbot']['server'] = 'buildbot.chevah.com'
SETUP['buildbot']['web_url'] = 'https://buildbot.chevah.com:10443'
SETUP['pypi']['index_url'] = os.environ['PIP_INDEX']


def _set_umask(mask):
    """
    Try to set the umask on any OS.

    Does nothing if the OS doesn't support the umask operation.
    """
    if not hasattr(os, 'umask'):
        # Not an OS where we can set umask.
        return
    os.umask(mask)


# Set a consistent umask across all project tools.
# Some tests assume that a specific umask is set in the OS.
_set_umask(0o002)


def compile_file(fullname, ddir=None, force=0, rx=None, quiet=0):
    """
    <Byte-compile one file.

    Arguments (only fullname is required):

    fullname:  the file to byte-compile
    ddir:      if given, the directory name compiled in to the
               byte-code file.
    force:     if 1, force compilation, even if timestamps are up-to-date
    quiet:     if 1, be quiet during compilation
    """
    success = 1
    name = os.path.basename(fullname)
    if ddir is not None:
        dfile = os.path.join(ddir, name)
    else:
        dfile = None
    if rx is not None:
        mo = rx.search(fullname)
        if mo:
            return success
    if os.path.isfile(fullname):
        tail = name[-3:]
        if tail == '.py':
            if not force:
                try:
                    mtime = int(os.stat(fullname).st_mtime)
                    expect = struct.pack('<4sl', imp.get_magic(), mtime)
                    cfile = fullname + (__debug__ and 'c' or 'o')
                    with open(cfile, 'rb') as chandle:
                        actual = chandle.read(8)
                    if expect == actual:
                        return success
                except OSError:
                    pass
            if not quiet:
                print('Compiling', fullname.encode('utf-8'), '...')
            try:
                ok = py_compile.compile(fullname, None, dfile, True)
            except py_compile.PyCompileError as err:
                if quiet:
                    print('Compiling', fullname.encode('utf-8'), '...')
                print(err.msg.encode('utf-8'))
                success = 0
            except OSError as e:
                print('Sorry', e)
                success = 0
            else:
                if ok == 0:
                    success = 0
    return success


# Path the upstream code.
compileall.compile_file = compile_file


@task
def update_setup():
    """
    Does nothing for now. Here to comply with standard build system.
    """


@task
def deps():
    """
    Install all dependencies.
    """
    print('Installing dependencies to %s...' % (pave.path.build,))
    packages = RUN_PACKAGES + BUILD_PACKAGES

    pave.pip(
        command='install',
        arguments=packages,
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

    # On AIX, pip (setuptools) fails to re-install, so we do some custom
    # cleaning as a workaround.
    members = pave.fs.listFolder(pave.fs.join([
        pave.path.build, pave.getPythonLibPath()]))
    for member in members:
        # We are looking for folder like chevah_compat-0.45.1-py2.7.egg-info.
        if member.startswith('chevah_compat-') and member.endswith('-info'):
            pave.fs.deleteFolder([
                pave.path.build, pave.getPythonLibPath(), member,
                ])
            break

    pave.fs.deleteFolder([pave.path.build, 'setup-build'])

    build_target = pave.fs.join([pave.path.build, 'setup-build'])
    sys.argv = ['setup.py', '-q', 'build', '--build-base', build_target]
    print("Building in " + build_target)
    # Importing setup will trigger executing commands from sys.argv.
    import setup
    setup.distribution.run_command('install')


@task
@needs('build', 'test_python')
@consume_args
def test(args):
    """
    Run all Python tests.
    """


@task
@consume_args
def remote(args):
    """
    Run tests on remote and wait for results.
    """
    call_task('test_remote', args=args + ['--wait'])


@task
def test_documentation():
    """
    Does nothing.
    """


def _generate_coverate_reports():
    """
    Generate reports.
    """
    import coverage
    from diff_cover.tool import main as diff_cover_main
    with pushd(pave.path.build):
        cov = coverage.Coverage(auto_data=True, config_file='.coveragerc')
        cov.load()
        cov.xml_report()
        cov.html_report()
        print(
            'HTML report file://%s/coverage-report/index.html' % (
                pave.path.build,))
        print('--------')
        diff_cover_main(argv=[
            'diff-cover',
            'coverage.xml',
            '--fail-under', '100'
            ])


@task
@consume_args
def test_coverage(args):
    """
    Run tests with coverage.
    """
    # Trigger coverage creation.
    os.environ['CODECOV_TOKEN'] = 'local'
    call_task('test', args=args)
    _generate_coverate_reports()


@task
# It needs consume_args to initialize the paver environment.
@consume_args
@needs('build')
def test_ci(args):
    """
    Run tests in continuous integration environment.
    """
    exit_code = call_task('test_ci2', args=args)

    if os.environ.get(b'CODECOV_TOKEN', ''):
        call_task('codecov_publish')

    return exit_code


@task
# It needs consume_args to initialize the paver environment.
@consume_args
@needs('build')
def test_ci2(args):
    """
    Run tests in continuous integration environment for CI which read
    their configuration from the repo/branch (Ex GitHub actions).

    It runs the coverage, but the coverage is published in a separate step.
    """
    # When running in CI mode, we want to get more reports.
    SETUP['test']['nose_options'] += [
        '--with-run-reporter',
        '--with-timer',
        '-v',
        ]

    # Show some info about the current environment.
    from OpenSSL import SSL, __version__ as pyopenssl_version
    from coverage.cmdline import main as coverage_main
    from chevah.compat.testing.testcase import ChevahTestCase

    print('%s / os_name:%s / os_version:%s / cpu_type:%s / ci_name:%s' % (
        ChevahTestCase.os_family,
        ChevahTestCase.os_name,
        ChevahTestCase.os_version,
        ChevahTestCase.cpu_type,
        ChevahTestCase.ci_name,
        ))
    print('PYTHON %s on %s with %s' % (sys.version, pave.os_name, pave.cpu))
    print('%s (%s)' % (
        SSL.SSLeay_version(SSL.SSLEAY_VERSION), SSL.OPENSSL_VERSION_NUMBER))
    print('pyOpenSSL %s' % (pyopenssl_version,))
    coverage_main(argv=['--version'])

    print('\n#\n# Installed packages\n#')
    pave.pip(
        command='freeze',
        )

    env = os.environ.copy()
    args = [env.get('TEST_ARGUMENTS', '')]
    environment.args = args

    skip_coverage = False
    if pave.os_name.startswith('alpine') or pave.os_name.startswith('hpux'):
        # On alpine coverage reporting segfaults.
        # On HPUX we run out of memory.
        skip_coverage = True

    if skip_coverage:
        os.environ[b'CODECOV_TOKEN'] = ''
    if os.environ.get(b'CODECOV_TOKEN', ''):
        print('Running tests with coverage')
    else:
        print('Running tests WITHOUT coverage.')

    args = env.get('TEST_ARGUMENTS', '')
    if not args:
        args = []
    else:
        args = [args]
    test_type = env.get('TEST_TYPE', 'normal')

    if test_type == 'py3':
        os.environ[b'CODECOV_TOKEN'] = ''
        return call_task('test_py3', args=args)

    exit_code = call_task('test_python', args=args)

    return exit_code
