# Copyright (c) 2012 Adi Roiban.
# See LICENSE for details.
"""
Code for testing compat module that requires access to system security
functions.
"""

from chevah.compat import process_capabilities
from chevah.empirical.testcase import (
    ChevahTestCase,
    setup_os,
    teardown_os,
    )
from chevah.compat.testing import (
    TEST_GROUPS,
    TEST_USERS,
    )


def runElevatedTest():
    """
    Return true if we can access privileged OS operations.
    """
    # For now, elevated tests are skipped on domain controller,
    # and we have a separate set of tests.
    if '-dc-' in ChevahTestCase.getHostname():
        return False

    if not process_capabilities.impersonate_local_account:
        return False

    if not process_capabilities.get_home_folder:
        return False

    return True


def setup_package():
    # Don't run these tests if we can not access privileged OS part.
    if not runElevatedTest():
        raise ChevahTestCase.skipTest()
    # Initialize the testing OS.

    try:
        setup_os(users=TEST_USERS, groups=TEST_GROUPS)
    except:
        import traceback
        print traceback.format_exc()
        print "Failed to initialized the system accounts!"
        teardown_os(users=TEST_USERS, groups=TEST_GROUPS)
        raise


def teardown_package():
    teardown_os(users=TEST_USERS, groups=TEST_GROUPS)
