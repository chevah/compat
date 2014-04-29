# Copyright (c) 2012 Adi Roiban.
# See LICENSE for details.
"""
Code for testing compat module that requires access to Windows Domain
Controller.
"""
from chevah.empirical.testcase import (
    ChevahTestCase,
    )
from chevah.compat.testing import (
    setup_access_control,
    teardown_access_control,
    TEST_GROUPS_DOMAIN,
    TEST_USERS_DOMAIN,
    )


def runDomainTest():
    """
    Return True if buildslave is a domain member.
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
        setup_access_control(
            users=TEST_USERS_DOMAIN, groups=TEST_GROUPS_DOMAIN)
    except:
        import traceback
        print traceback.format_exc()
        print "Failed to initialized the system accounts!"
        teardown_access_control(
            users=TEST_USERS_DOMAIN, groups=TEST_GROUPS_DOMAIN)
        raise


def teardown_package():
    teardown_access_control(
        users=TEST_USERS_DOMAIN, groups=TEST_GROUPS_DOMAIN)
