# ruff: noqa: T201
# Copyright (c) 2012 Adi Roiban.
# See LICENSE for details.
"""
Code for testing compat module that requires access to system security
functions.
"""

from chevah_compat import process_capabilities
from chevah_compat.testing import (
    TEST_GROUPS,
    TEST_USERS,
    CompatTestCase,
    setup_access_control,
    teardown_access_control,
)


def runElevatedTest():
    """
    Return true if we can access privileged OS operations.
    """
    if CompatTestCase.os_name == 'openbsd':
        # On OpenBSD the automatic creation of users and groups fails,
        # and since is not a supported OS we skip the tests.
        return False

    if (
        CompatTestCase.os_name == 'osx'
        and CompatTestCase.os_version != 'osx-10.15'
    ):
        # On latest macOS we have issues creating the groups.
        # We kind of stop supporting macOS for system users,
        # so we don't care about elevated tests.
        return False

    if not process_capabilities.impersonate_local_account:
        return False

    if not process_capabilities.get_home_folder:
        return False

    return True


def setup_package():
    # Don't run these tests if we can not access privileged OS part.
    if not runElevatedTest():
        raise CompatTestCase.skipTest('Not an elevated process.')

    # Initialize the testing OS.
    try:
        setup_access_control(users=TEST_USERS, groups=TEST_GROUPS)
    except Exception:  # pragma: no cover
        import traceback

        print(traceback.format_exc())
        print('Failed to initialized the system accounts!')
        teardown_access_control(users=TEST_USERS, groups=TEST_GROUPS)
        raise


def teardown_package():
    teardown_access_control(users=TEST_USERS, groups=TEST_GROUPS)
