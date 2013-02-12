# -*- coding: utf-8 -*-
# Copyright (c) 2011 Adi Roiban.
# See LICENSE for details.
'''Test system users portable code code.'''
from __future__ import with_statement
from contextlib import nested
import os

from chevah.compat import process_capabilities
from chevah.empirical import ChevahTestCase


class TestProcessCapabilities(ChevahTestCase):

    def setUp(self):
        super(TestProcessCapabilities, self).setUp()
        self.capabilities = process_capabilities

    def test_impersonate_local_account(self):
        """
        When running as super user we can always impersonate local accounts.
        """
        result = self.capabilities.impersonate_local_account
        self.assertTrue(result)

    def test_create_home_folder(self):
        """
        When running as super user, we can always create home folders.
        """
        result = self.capabilities.create_home_folder
        self.assertTrue(result)

    def test_get_home_folder(self):
        """
        On unix we can always get home folder.

        On Windows 7 and 2008 home folder path can be retrieved. On
        all other system below Windows 7, the home folder can not be
        retrieved yet.
        """
        result = self.capabilities.get_home_folder
        hostname = self.getHostname()
        if 'win-xp' in hostname or 'win-2003' in hostname:
            self.assertFalse(result)
        else:
            self.assertTrue(result)

    def test_getCurrentPrivilegesDescription(self):
        """
        Check getCurrentPrivilegesDescription.
        """
        if os.name == 'posix':
            text = self.capabilities.getCurrentPrivilegesDescription()
            self.assertEqual(u'root capabilities enabled.', text)
        else:
            # Windows tests are done in the normal tests.
            pass


class TestNTProcessCapabilities(TestProcessCapabilities):

    def setUp(self):
        super(TestNTProcessCapabilities, self).setUp()

        if os.name != 'nt':
            raise self.skipTest("Only Windows platforms supported.")

    def test_adjustPrivilege_success(self):
        """
        Turning SE_BACKUP privilege on/off for the current process when
        running as super user.
        """
        import win32security
        initial_state = self.capabilities._hasPrivilege(
            win32security.SE_BACKUP_NAME)

        self.capabilities._adjustPrivilege(
            win32security.SE_BACKUP_NAME, False)

        self.assertIsFalse(self.capabilities._hasPrivilege(
            win32security.SE_BACKUP_NAME))

        self.capabilities._adjustPrivilege(
            win32security.SE_BACKUP_NAME, initial_state)

        self.assertEquals(initial_state, self.capabilities._hasPrivilege(
            win32security.SE_BACKUP_NAME))

    def test_hasPrivilege_impersonate(self):
        """
        By default SE_IMPERSONATE privilege is enabled when running
        as super user.
        """
        import win32security
        self.assertTrue(
            self.capabilities._hasPrivilege(
                win32security.SE_IMPERSONATE_NAME))

    def test_hasPrivilege_load_driver(self):
        """
        By default SE_LOAD_DRIVER privilege is disabled.
        """
        import win32security
        self.assertFalse(self.capabilities._hasPrivilege(
            win32security.SE_LOAD_DRIVER_NAME))

    def test_elevatePrivileges_take_ownership_success(self):
        """
        When running as super user we can successfully elevate the
        privileges to include SE_TAKE_OWNERSHIP. After leaving the context
        the privileges are lowered again to their previous state.
        """
        import win32security
        self.assertFalse(self.capabilities._hasPrivilege(
            win32security.SE_TAKE_OWNERSHIP_NAME))

        with (self.capabilities._elevatePrivileges(
                win32security.SE_TAKE_OWNERSHIP_NAME)):
            self.assertTrue(self.capabilities._hasPrivilege(
                win32security.SE_TAKE_OWNERSHIP_NAME))

        self.assertFalse(self.capabilities._hasPrivilege(
            win32security.SE_TAKE_OWNERSHIP_NAME))

    def test_elevatePrivilege_impersonate_unchanged(self):
        """
        Make sure that previously enabled privileges remain enabled after
        leaving the elevated privileges context.
        """
        import win32security
        self.assertTrue(self.capabilities._hasPrivilege(
            win32security.SE_IMPERSONATE_NAME))

        with (self.capabilities._elevatePrivileges(
                win32security.SE_IMPERSONATE_NAME)):
            self.assertTrue(self.capabilities._hasPrivilege(
                win32security.SE_IMPERSONATE_NAME))

        self.assertTrue(self.capabilities._hasPrivilege(
            win32security.SE_IMPERSONATE_NAME))

    def test_openProcess_all_access(self):
        """
        Opening current process token for all access returns a valid value.
        """
        import win32security
        with nested(
            self.capabilities._openProcess(win32security.TOKEN_QUERY)
            ) as (token):
            self.assertIsNotNone(token)
