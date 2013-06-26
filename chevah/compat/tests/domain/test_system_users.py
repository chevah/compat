# -*- coding: utf-8 -*-
# Copyright (c) 2011 Adi Roiban.
# See LICENSE for details.
'''Test system users portable code code.'''
from __future__ import with_statement
import os
import sys

from nose.plugins.attrib import attr

from chevah.compat import (
    HasImpersonatedAvatar,
    process_capabilities,
    system_users,
    )
from chevah.compat.constants import (
    WINDOWS_PRIMARY_GROUP,
    )
from chevah.compat.administration import os_administration
from chevah.compat.testing import (
    ChevahTestCase,
    manufacture,
    TestUser,
    TEST_ACCOUNT_CENTRIFY_USERNAME,
    TEST_ACCOUNT_CENTRIFY_PASSWORD,
    TEST_ACCOUNT_UID,
    TEST_ACCOUNT_GID,
    TEST_ACCOUNT_GID_ANOTHER,
    TEST_ACCOUNT_GROUP,
    TEST_ACCOUNT_GROUP_WIN,
    TEST_ACCOUNT_PASSWORD,
    TEST_ACCOUNT_USERNAME,
    TEST_ACCOUNT_USERNAME_DOMAIN,
    TEST_ACCOUNT_LDAP_PASSWORD,
    TEST_ACCOUNT_LDAP_USERNAME,
    )
from chevah.compat.exceptions import (
    ChangeUserException,
    CompatError,
    )


class TestSystemUsers(ChevahTestCase):
    """
    SystemUsers tests with users from Domain Controller.
    """

    def test_userExists_good(self):
        """
        Return `True` when user exists.
        """
        self.assertFalse(
            system_users.userExists(TEST_ACCOUNT_USERNAME_DOMAIN))
