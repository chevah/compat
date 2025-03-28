# Copyright (c) 2010-2016 Adi Roiban.
# See LICENSE for details.
# ruff: noqa: T201
"""
Build script for chevah-compat.
"""

import os
import subprocess
import sys

from brink.pavement_commons import (
    SETUP,
    codecov_publish,
    coverage_prepare,
    default,
    help,
    merge_commit,
    merge_init,
    pave,
    pqm,
    test_coverage,
    test_diff,
    test_normal,
    test_python,
    test_remote,
    test_super,
)
from paver.easy import call_task, consume_args, environment, needs, pushd, task

if os.name == 'nt':
    # Use shorter temp folder on Windows.
    import tempfile

    # Create the short temp.
    tempfile.tempdir = 'c:\\temp'
    try:
        os.mkdir(tempfile.tempdir)
    except OSError:
        pass

# Make pylint shut up.
coverage_prepare
codecov_publish
default
help
merge_init
merge_commit
pqm
test_coverage
test_diff
test_python
test_remote
test_normal
test_super


SETUP['product']['name'] = 'chevah-compat'
SETUP['folders']['source'] = 'src/chevah_compat'
SETUP['repository']['name'] = 'compat'
SETUP['repository']['github'] = 'https://github.com/chevah/compat'
SETUP['test']['package'] = 'chevah_compat.tests'
SETUP['test']['elevated'] = 'elevated'
SETUP['test']['nose_options'] = [
    # TODO: Add support for extenstions.
    # 690
    # '--with-timer',
    # '--with-run-reporter',
    # '--with-memory-usage',
]
SETUP['pypi']['index_url'] = os.environ['PIP_INDEX_URL']


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
    print('Installing dependencies to ', pave.path.build)
    dev_mode = []

    env_ci = os.environ.get('CI', '').strip()
    if env_ci.lower() != 'true':
        dev_mode = ['-e']
        pave.fs.deleteFile(
            [
                pave.path.build,
                pave.getPythonLibPath(),
                'chevah-compat.egg-link',
            ],
        )
    else:
        print('Installing in non-dev mode.')

    pave.pip(command='install', arguments=dev_mode + ['.[dev]'])


@task
@needs('coverage_prepare')
def build():
    """
    Copy new source code to build folder.
    """


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
            f'HTML report file://{pave.path.build}/coverage-report/index.html',
        )
        print('--------')
        diff_cover_main(
            argv=['diff-cover', 'coverage.xml', '--fail-under', '100'],
        )


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
        # TODO: Add support for extensions.
        # 690
        # '--with-run-reporter',
        # '--with-timer',
        '-v',
    ]

    # Show some info about the current environment.
    from coverage.cmdline import main as coverage_main
    from OpenSSL import SSL
    from OpenSSL import __version__ as pyopenssl_version

    from chevah_compat.testing.testcase import ChevahTestCase

    print(
        f'{ChevahTestCase.os_family} / '
        f'os_name:{ChevahTestCase.os_name} / '
        f'os_version:{ChevahTestCase.os_version} / '
        f'cpu_type:{ChevahTestCase.cpu_type} / '
        f'ci_name:{ChevahTestCase.ci_name}',
    )
    print(f'PYTHON {sys.version} on {pave.os_name} with {pave.cpu}')
    print(
        f'{SSL.SSLeay_version(SSL.SSLEAY_VERSION)} '
        f'({SSL.OPENSSL_VERSION_NUMBER})',
    )
    print(f'pyOpenSSL {pyopenssl_version}')
    coverage_main(argv=['--version'])

    print('\n#\n# Installed packages\n#')
    pave.pip(command='freeze')

    env = os.environ.copy()
    args = [env.get('TEST_ARGUMENTS', '')]
    environment.args = args

    skip_coverage = False
    if pave.os_name.startswith('alpine') or pave.os_name.startswith('hpux'):
        # On alpine coverage reporting segfaults.
        # On HPUX we run out of memory.
        skip_coverage = True

    if skip_coverage:
        os.environ['CODECOV_TOKEN'] = ''
    if os.environ.get('CODECOV_TOKEN', ''):
        print('Running tests with coverage')
    else:
        print('Running tests WITHOUT coverage.')

    args = env.get('TEST_ARGUMENTS', '')
    if not args:
        args = []
    else:
        args = [args]

    return call_task('test_python', args=args)


@task
@consume_args
def pytest(args):
    """
    Run tests using pytest.
    """
    import sys

    from pytest import console_main

    sys.argv = ['pytest'] + args
    sys.exit(console_main())


@task
@consume_args
def lint(args):
    """
    Check that the source code is ok
    """
    check_args = args

    if pave.os_name == 'windows':
        ruff_bin = os.path.join(pave.path.build, 'lib', 'Scripts', 'ruff')
    else:
        ruff_bin = os.path.join(pave.path.build, 'bin', 'ruff')

    check_result = subprocess.run(
        [ruff_bin, 'check'] + check_args,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    format_result = subprocess.run(
        [ruff_bin, 'format', '--check'] + check_args,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    if check_result.returncode != 0 or format_result.returncode != 0:
        print('Lint failed.')
        sys.exit(1)


@task
@consume_args
def fix(args):
    """
    Try to fix the source code.
    """
    ruff_bin = os.path.join(pave.path.build, 'bin', 'ruff')
    check_result = subprocess.run(
        [ruff_bin, 'check', '--fix', '--unsafe-fixes', '--no-cache'] + args,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    format_result = subprocess.run(
        [ruff_bin, 'format', '--no-cache'] + args,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    if check_result.returncode != 0 or format_result != 0:
        sys.exit(1)


@task
def migrate_fixme():
    """
    Migrate the FIX_ME markers to the ruff TO_DO markers.
    """
    for root, dirs, files in os.walk('.'):
        for name in files:
            if not name.endswith('.py'):
                continue

            have_fixes = False
            file_path = os.path.join(root, name)
            with open(file_path) as stream:
                lines = stream.readlines()
                for line_no, line in enumerate(lines):
                    if '# FIXME:' not in line:
                        continue

                    have_fixes = True
                    padding = line.split('# ')[0]
                    comment = lines[line_no + 1].split('# ', 1)[-1].strip()
                    issue = line.split('FIXME:')[1].replace(':', '')
                    lines[line_no] = f'{padding}# TODO: {comment}\n'
                    lines[line_no + 1] = f'{padding}# {issue}\n'

            if not have_fixes:
                continue

            with open(file_path, 'w') as stream:
                stream.write(''.join(lines))
