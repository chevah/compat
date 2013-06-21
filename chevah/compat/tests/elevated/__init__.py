# Copyright (c) 2012 Adi Roiban.
# See LICENSE for details.
"""
Code for testing compat module that requires access to system security
functions.
"""
import win32net

from chevah.compat import process_capabilities
from chevah.empirical.testcase import (
    ChevahTestCase,
    #setup_os,
    #teardown_os,
    )
from chevah.compat.constants import (
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

def get_primary_domain_controller_name(domain):
        """
        Returns the name of the primary domain controller.
        """
        return win32net.NetGetDCName(None, domain)[2:]

def setup_os(users, groups):
    '''Create testing environemnt

    Add users, groups, create temporary folders and other things required
    by the testing system.
    '''
    from chevah.compat.administration import OSAdministration

    domain = 'chevah'
    pdc = get_primary_domain_controller_name(domain)

    os_administration = OSAdministration()
    for group in groups:
        os_administration.addGroup(group=group, server=pdc)

    for user in users:
        os_administration.addUser(user=user, server=pdc)

    for group in groups:
        os_administration.addUsersToGroup(
            group=group, users=group.members, server=pdc)

def teardown_os(users, groups):
    '''Revert changes from setUpOS.'''

    from chevah.compat.administration import OSAdministration

    domain = 'chevah'
    pdc = get_primary_domain_controller_name(domain)

    os_administration = OSAdministration()

    for group in groups:
        os_administration.deleteGroup(group=group, server=pdc)

    for user in users:
        os_administration.deleteUser(user=user, server=pdc)

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
