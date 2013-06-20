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
from chevah.empirical.constants import (
    TestGroup,
    TestUser,
    )

TEST_USERS = [
    TestUser(
            name='trial-user',
            uid=1222,
            password='qwe123QWE',
            ),
    ]

TEST_GROUPS = [
    TestGroup(
        name='trial-group',
        gid=1233,
        members=['trial-user'],
        ),
    ]


def runElevatedTest():
    """
    Return true if we can access privileged OS operations.
    """
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
