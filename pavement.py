# Copyright (c) 2010-2016 Adi Roiban.
# See LICENSE for details.
"""
Build script for chevah-compat.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    )
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
    test_diff,
    test_os_dependent,
    test_os_independent,
    test_python,
    test_remote,
    test_review,
    test_normal,
    test_super,
    )
from paver.easy import call_task, consume_args, environment, needs, pushd, task

if os.name == 'nt':
    # Use shorter temp folder on Windows.
    import tempfile
    tempfile.tempdir = "c:\\temp"
    try:
        os.mkdir(tempfile.tempdir)
    except OSError:
        pass

# Keep run_packages in sync with setup.py.
# These are the hard dependencies needed by the library itself.
RUN_PACKAGES = [
    'zope.interface==3.8.0',
    # Py3 compat.
    'future==0.16.0',
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

# Packages required to use the dev/build system.
BUILD_PACKAGES = [
    # Buildbot is used for try scheduler
    'buildbot==0.8.11.c7',

    'diff_cover==0.9.11',

    # For PQM
    'chevah-github-hooks-server==0.1.6',
    'smmap==0.8.2',
    'async==0.6.1',
    'gitdb==0.6.4',
    'gitpython==1.0.1',
    'pygithub==1.10.0',
    ]


# Packages required by the static analysis tests.
LINT_PACKAGES = [
    'scame==0.3.3',
    'pyflakes==1.5.0',
    'pycodestyle==2.3.1',
    'bandit==1.4.0',
    'pylint==1.7.1',
    'astroid==1.5.3',

    # These are build packages, but are needed for testing the documentation.
    'sphinx==1.2.2',
    'repoze.sphinx.autointerface==0.7.1.c4',
    # Docutils is required for RST parsing and for Sphinx.
    'docutils==0.12.c1',

    ]

# Packages required to run the test suite.
TEST_PACKAGES = [
    # Never version of nose, hangs on closing some tests
    # due to some thread handling.
    'nose==1.3.7',
    'nose-randomly==1.2.5',
    'mock',

    'coverage==4.0.3',
    'codecov==2.0.3',

    # used for remote debugging.
    'remote_pdb==1.2.0',

    # Twisted is optionl, but we have it here for complete tests.
    'twisted==15.5.0.chevah4',

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
test_diff
test_os_dependent
test_os_independent
test_python
test_remote
test_review
test_normal
test_super

try:
    from scame.formatcheck import ScameOptions

    class ServerScameOptions(ScameOptions):
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

    options = ServerScameOptions()
    options.max_line_length = 80

    options.scope = {
        'include': [
            'pavement.py',
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

    options.closure_linter['enabled'] = True
    options.closure_linter['ignore'] = [1, 10, 11, 110, 220]

    options.pycodestyle['enabled'] = True
    options.pycodestyle['hang_closing'] = True

    options.bandit['enabled'] = True
    options.bandit['exclude'] = [
        'B104',  # Bind to 0.0.0.0
        ]

    # For now pylint is disabled, as there are to many errors.
    options.pylint['enabled'] = False
    options.pylint['disable'] = ['C0103', 'C0330', 'R0902', 'W0212']

    # For the testing and dev code we disable bandit.
    options.test_options['bandit'] = options.bandit.copy()
    options.test_options['bandit']['enabled'] = False

except ImportError:
    # This will fail before we run `paver deps`
    options = None


SETUP['product']['name'] = 'chevah-compat'
SETUP['folders']['source'] = u'chevah/compat'
SETUP['repository']['name'] = u'compat'
SETUP['repository']['github'] = u'https://github.com/chevah/compat'
SETUP['scame'] = options
SETUP['test']['package'] = 'chevah.compat.tests'
SETUP['test']['elevated'] = 'elevated'
SETUP['test']['nose_options'] = ['--with-randomly']
SETUP['buildbot']['server'] = 'buildbot.chevah.com'
SETUP['buildbot']['web_url'] = 'https://buildbot.chevah.com:10443'
SETUP['pypi']['index_url'] = 'http://pypi.chevah.com/simple'


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
    packages = RUN_PACKAGES + TEST_PACKAGES

    env_ci = os.environ.get('CI', '').strip()
    if env_ci.lower() != 'true':
        packages += BUILD_PACKAGES + LINT_PACKAGES
    else:
        builder = os.environ.get('BUILDER_NAME', '')
        if 'os-independent' in builder or '-py3' in builder:
            packages += LINT_PACKAGES
            print('Installing only lint and test dependencies.')
        elif '-gk-merge' in builder:
            packages += BUILD_PACKAGES
            print('Installing only build and test dependencies.')
        else:
            print('Installing only test dependencies.')

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
    pave.fs.deleteFolder([pave.path.build, 'setup-build'])

    build_target = pave.fs.join([pave.path.build, 'setup-build'])
    sys.argv = ['setup.py', '-q', 'build', '--build-base', build_target]
    print("Building in " + build_target)
    # Importing setup will trigger executing commands from sys.argv.
    import setup
    setup.distribution.run_command('install')


@task
@needs('test_python')
@consume_args
def test(args):
    """
    Run all Python tests.
    """


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
def test_ci(args):
    """
    Run tests in continuous integration environment.
    """
    # When running in CI mode, we want to get more reports.
    SETUP['test']['nose_options'] += [
        '--with-run-reporter',
        '--with-timer',
        ]

    # Show some info about the current environment.
    from OpenSSL import SSL, __version__ as pyopenssl_version
    from coverage.cmdline import main as coverage_main
    from chevah.compat.testing.testcase import ChevahTestCase

    print('%s / %s / %s / %s' % (
        ChevahTestCase.os_family,
        ChevahTestCase.os_name,
        ChevahTestCase.os_version,
        ChevahTestCase.cpu_type,
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
    if pave.os_name.startswith('alpine'):
        # On alpine coverage reporting segfaults.
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

    if test_type == 'os-independent':
        return call_task('test_os_independent')

    if test_type == 'py3':
        return call_task('test_py3', args=args)

    return call_task('test_os_dependent', args=args)


@task
@consume_args
def test_py3(args):
    """
    Run checks for py3 compatibility.
    """
    from pylint.lint import Run
    from nose.core import main as nose_main
    arguments = [
        '--py3k',
        # See https://github.com/PyCQA/pylint/issues/1564
        '-d exception-message-attribute',
        SETUP['folders']['source'],
        ]
    linter = Run(arguments, exit=False)
    stats = linter.linter.stats
    errors = (
        stats['info'] + stats['error'] + stats['refactor'] +
        stats['fatal'] + stats['convention'] + stats['warning']
        )
    if errors:
        print('Pylint failed')
        sys.exit(1)

    print('Compiling in Py3 ...', end='')
    command = ['python3', '-m', 'compileall', '-q', 'chevah']
    pave.execute(command, output=sys.stdout)
    print('done')

    sys.argv = sys.argv[:1]
    pave.python_command_normal.extend(['-3'])

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

    sys.args = ['nose', 'chevah.compat.tests.normal'] + args
    runner = nose_main(exit=False)
    if not runner.success:
        print('Test failed')
        sys.exit(1)
    if not captured_warnings:
        sys.exit(0)

    print('\nCaptured warnings\n')
    for warning, filename, line in captured_warnings:
        print('%s:%s %s' % (filename, line, warning))
    sys.exit(1)
