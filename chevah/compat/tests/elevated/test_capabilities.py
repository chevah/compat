# -*- coding: utf-8 -*-
# Copyright (c) 2011 Adi Roiban.
# See LICENSE for details.
'''Test system users portable code code.'''
from __future__ import with_statement
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

    def test_hasPrivilege_enabled(self):
        """
        hasPrivilege return True for a privilege which is present and is
        enabled.
        """
        # We use  SE_IMPERSONATE privilege as it is enabled by default
        # when running as super user.
        import win32security
        privilege = win32security.SE_IMPERSONATE_NAME
        self.assertTrue(self.capabilities._hasPrivilege(privilege))

    def test_hasPrivilege_disabled(self):
        """
        hasPrivilege return False for a privilege which is disabled.
        """
        # By default SE_LOAD_DRIVER privilege is disabled.
        import win32security
        privilege = win32security.SE_LOAD_DRIVER_NAME
        self.assertFalse(self.capabilities._hasPrivilege(privilege))

    def test_elevatePrivileges_take_ownership_success(self):
        """
        elevatePrivileges is a context manager which will elevates the
        privileges for current process upon entering the context,
        and restore them at exit.
        """
        # We use SE_TAKE_OWNERSHIP privilege at it should be present for
        # super user and disabled by default.
        import win32security
        privilege = win32security.SE_TAKE_OWNERSHIP_NAME
        self.assertFalse(self.capabilities._hasPrivilege(privilege))

        with (self.capabilities._elevatePrivileges(privilege)):
            self.assertTrue(self.capabilities._hasPrivilege(privilege))

        self.assertFalse(self.capabilities._hasPrivilege(privilege))

    def test_elevatePrivilege_impersonate_unchanged(self):
        """
        elevatePrivilege will not modify the process if the privilege is
        already enabled.
        """
        # We use SE_IMPERSONATE as it should be enabled by default.
        import win32security
        privilege = win32security.SE_IMPERSONATE_NAME
        self.assertTrue(self.capabilities._hasPrivilege(privilege))

        with (self.capabilities._elevatePrivileges(privilege)):
            self.assertTrue(self.capabilities._hasPrivilege(privilege))

        self.assertTrue(self.capabilities._hasPrivilege(privilege))
