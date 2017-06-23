# Copyright (c) 2012 Adi Roiban.
# See LICENSE for details.
"""
Code for testing compat module that requires access to Windows Domain
Controller.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import os

from chevah.compat.testing.testcase import (
    ChevahTestCase,
    )
from chevah.compat.testing import (
    TestGroup,
    TestUser,
    setup_access_control,
    teardown_access_control,
    TEST_ACCOUNT_GROUP_DOMAIN,
    TEST_ACCOUNT_PASSWORD_DOMAIN,
    TEST_ACCOUNT_USERNAME_DOMAIN,
    TEST_DOMAIN,
    TEST_GROUPS,
    TEST_PDC,
    TEST_USERS,
    )


def runDomainTest():
    """
    Return True if buildslave is a domain member.
    """
    # FIXME:3832:
    # Domain tests are broken.
    return False

    # For now, elevated tests are executed only on the domain controller
    # buildslave.
    BUILDER_NAME = os.getenv('BUILDER_NAME', '')
    if '-dc-' in BUILDER_NAME:
        return True

    return False


def setup_package():
    # Don't run these tests if we can not access privileged OS part.
    if not runDomainTest():
        raise ChevahTestCase.skipTest()

    # Initialize the testing OS.
    DOMAIN_USERS = {
        u'domain': TestUser(
            name=TEST_ACCOUNT_USERNAME_DOMAIN,
            password=TEST_ACCOUNT_PASSWORD_DOMAIN,
            domain=TEST_DOMAIN,
            pdc=TEST_PDC,
            create_local_profile=True,
            ),
        }

    DOMAIN_GROUPS = {
        u'domain': TestGroup(
            name=TEST_ACCOUNT_GROUP_DOMAIN,
            members=[TEST_ACCOUNT_USERNAME_DOMAIN],
            pdc=TEST_PDC,
            ),
        }

    TEST_USERS.update(DOMAIN_USERS)
    TEST_GROUPS.update(DOMAIN_GROUPS)

    try:
        setup_access_control(
            users=TEST_USERS, groups=TEST_GROUPS)
    except Exception:
        import traceback
        print(traceback.format_exc())
        print("Failed to initialized the system accounts!")
        teardown_access_control(
            users=TEST_USERS, groups=TEST_GROUPS)
        raise


def teardown_package():
    teardown_access_control(
        users=TEST_USERS, groups=TEST_GROUPS)
