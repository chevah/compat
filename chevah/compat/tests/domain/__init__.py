# Copyright (c) 2012 Adi Roiban.
# See LICENSE for details.
"""
Code for testing compat module that requires access to Windows Domain
Controller.
"""
from chevah.empirical.testcase import (
    ChevahTestCase,
    setup_os,
    teardown_os,
    )
from chevah.compat.testing import (
    TestGroup,
    TestUser,
    )

TEST_DOMAIN = 'chevah-dc'
TEST_ACCOUNT_USERNAME_DOMAIN = 'domaintestuser'
TEST_ACCOUNT_PASSWORD_DOMAIN = u'qwe123QWE'
TEST_ACCOUNT_GROUP_DOMAIN = 'domaintestgroup'


TEST_USERS = [
    TestUser(
        name=TEST_ACCOUNT_USERNAME_DOMAIN,
        password=TEST_ACCOUNT_PASSWORD_DOMAIN,
        domain=TEST_DOMAIN,
        )
    ]

TEST_GROUPS = [
    TestGroup(
        name=TEST_ACCOUNT_GROUP_DOMAIN,
        members=[TEST_ACCOUNT_USERNAME_DOMAIN]
        )
    ]


def runDomainTest():
    """
    Return true if we can access privileged OS operations.
    """
    # For now, elevated tests are executed only on the domain controller
    # buildslave.
    if '-dc-' in ChevahTestCase.getHostname():
        return True
    return False


def setup_package():
    # Don't run these tests if we can not access privileged OS part.
    if not runDomainTest():
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
