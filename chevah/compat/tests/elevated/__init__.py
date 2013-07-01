# Copyright (c) 2012 Adi Roiban.
# See LICENSE for details.
"""
Code for testing compat module that requires access to system security
functions.
"""

from chevah.compat import process_capabilities
from chevah.empirical.testcase import (
    ChevahTestCase,
    )
from chevah.compat.constants_empirical import (
    TEST_GROUPS,
    TEST_USERS,
    )


def runElevatedTest():
    """
    Return true if we can access privileged OS operations.
    """
    if not process_capabilities.impersonate_local_account:
        return False

    if not process_capabilities.get_home_folder:
        return False

    return True


def setup_os(users, groups):
    """
    Create testing environment

    Add users, groups, create temporary folders and other things required
    by the testing system.
    """
    from chevah.compat.administration import OSAdministration

    os_administration = OSAdministration()
    for group in groups:
        os_administration.addGroup(group)

    for user in users:
        os_administration.addUser(user)

    for group in groups:
        os_administration.addUsersToGroup(group, group.members)


def teardown_os(users, groups):
    """
    Revert changes from `setup_os`.
    """

    from chevah.compat.administration import OSAdministration

    os_administration = OSAdministration()

    for group in groups:
        os_administration.deleteGroup(group)

    for user in users:
        os_administration.deleteUser(user)


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
