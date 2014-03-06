# -*- coding: utf-8 -*-
# Copyright (c) 2011 Adi Roiban.
# See LICENSE for details.
"""
Test for platform capabilities detection.
"""
import os
try:
    import win32security
except ImportError:
    pass

from zope.interface.verify import verifyObject

from chevah.compat import process_capabilities
from chevah.compat.exceptions import AdjustPrivilegeException
from chevah.compat.interfaces import IProcessCapabilities
from chevah.compat.testing import CompatTestCase, manufacture


class TestProcessCapabilities(CompatTestCase):

    def setUp(self):
        super(TestProcessCapabilities, self).setUp()
        self.capabilities = process_capabilities

    def runningAsAdministrator(self):
        """
        Return True if slave runs as administrator.
        """
        # Windows 2008 and DC client tests are done in administration mode,
        # 2003 and XP under normal mode.
        if 'win-2003' in self.hostname or 'win-xp' in self.hostname:
            return False
        else:
            return True

    def test_init(self):
        """
        Check ProcessCapabilities initialization.
        """
        verifyObject(IProcessCapabilities, self.capabilities)

    def test_impersonate_local_account(self):
        """
        When running under normal account, impersonation is always False
        on Unix and always True on Windows.
        """
        result = self.capabilities.impersonate_local_account
        if os.name == 'posix':
            self.assertFalse(result)
        elif os.name == 'nt':
            self.assertTrue(result)
        else:
            raise AssertionError('Unsupported os.')

    def test_create_home_folder(self):
        """
        When running under normal account, we can not create home folders
        on Unix.

        On Windows home folders can be created if required privileges
        are configured for the process.
        """
        result = self.capabilities.create_home_folder
        if os.name == 'posix':
            self.assertFalse(result)
        elif os.name == 'nt':
            self.assertTrue(result)
        else:
            raise AssertionError('Unsupported os.')

    def test_get_home_folder(self):
        """
        On Unix we can always get home home folder.
        On Windows, only Windows 2008 and Windows 7 can get home folder path.
        """
        result = self.capabilities.get_home_folder
        if os.name == 'posix':
            self.assertTrue(result)
        elif os.name == 'nt':
            # The Windows test is handled in elevated module.
            pass
        else:
            raise AssertionError('Unsupported os.')

    def test_getCurrentPrivilegesDescription(self):
        """
        Check getCurrentPrivilegesDescription.
        """
        text = self.capabilities.getCurrentPrivilegesDescription()
        if self.os_family == 'posix':
            self.assertEqual(u'root capabilities disabled.', text)
        else:
            # Normal Window account can impersonate.
            self.assertContains('SeChangeNotifyPrivilege:3', text)
            self.assertContains('SeImpersonatePrivilege:3', text)
            self.assertContains('SeCreateGlobalPrivilege:3', text)

            if self.runningAsAdministrator():
                self.assertContains('SeCreateSymbolicLinkPrivilege:0', text)
            else:
                self.assertNotContains(
                    'SeCreateSymbolicLinkPrivilege', text)


class TestNTProcessCapabilities(TestProcessCapabilities):

    def setUp(self):
        super(TestNTProcessCapabilities, self).setUp()

        if os.name != 'nt':
            raise self.skipTest("Only Windows platforms supported.")

    def test_openProcess_success(self):
        """
        _openProcess can be used for process token for the current
        process having a specified mode enabled.
        """
        with self.capabilities._openProcess(win32security.TOKEN_QUERY) as (
                process_token):
            self.assertIsNotNone(process_token)

    def test_getAvailablePrivileges(self):
        """
        Return a list with privileges and state value.
        """
        result = self.capabilities._getAvailablePrivileges()

        self.assertIsNotEmpty(result)
        privilege = self.capabilities._getPrivilegeID(
            win32security.SE_IMPERSONATE_NAME)
        self.assertContains((privilege, 3), result)

        privilege = self.capabilities._getPrivilegeID(
            win32security.SE_SECURITY_NAME)
        self.assertContains((privilege, 0), result)

        if self.runningAsAdministrator():
            privilege = self.capabilities._getPrivilegeID(
                win32security.SE_CREATE_SYMBOLIC_LINK_NAME)
            self.assertContains((privilege, 0), result)

    def test_getPrivilegeState_invalid(self):
        """
        Return `absent` for unknown names.
        """
        privilege = manufacture.getUniqueString()

        result = self.capabilities._getPrivilegeState(privilege)

        self.assertEqual(u'absent', result)

    def test_getPrivilegeState_absent(self):
        """
        Return `absent` for privileges which are not attached to current
        process.
        """
        result = self.capabilities._getPrivilegeState(
            win32security.SE_ASSIGNPRIMARYTOKEN_NAME)

        self.assertEqual(u'absent', result)

    def test_getPrivilegeState_present(self):
        """
        Return `present` for privileges which are attached to current
        process but are not enabled.
        """
        result = self.capabilities._getPrivilegeState(
            win32security.SE_SECURITY_NAME)

        self.assertEqual(u'present', result)

    def test_getPrivilegeState_enabled_default(self):
        """
        Return `enabled-by-default` for privileges which are attached to
        current process but are enabled by default.
        """
        result = self.capabilities._getPrivilegeState(
            win32security.SE_IMPERSONATE_NAME)

        self.assertEqual(u'enabled-by-default', result)

    def test_isPrivilegeEnabled_enabled(self):
        """
        Returns True for a privilege which is present and is enabled.
        """
        # We use SE_IMPERSONATE privilege as it is enabled by default.
        privilege = win32security.SE_IMPERSONATE_NAME
        self.assertTrue(self.capabilities._isPrivilegeEnabled(privilege))

    def test_isPrivilegeEnabled_disabled(self):
        """
        Returns False for a privilege which is present but disabled.
        """
        # By default SE_LOAD_DRIVER privilege is disabled.
        privilege = win32security.SE_LOAD_DRIVER_NAME
        self.assertFalse(self.capabilities._isPrivilegeEnabled(privilege))

    def test_isPrivilegeEnabled_absent(self):
        """
        Returns False for a privilege which is not present.
        """
        # By default SE_RELABEL_NAME should not be available to test
        # accounts.
        privilege = win32security.SE_RELABEL_NAME
        self.assertEqual(
            u'absent', self.capabilities._getPrivilegeState(privilege))

        self.assertFalse(self.capabilities._isPrivilegeEnabled(privilege))

    def test_adjustPrivilege_success(self):
        """
        Turning SE_BACKUP privilege on/off for the current process when
        running as super user.
        """
        initial_state = self.capabilities._isPrivilegeEnabled(
            win32security.SE_BACKUP_NAME)

        self.capabilities._adjustPrivilege(
            win32security.SE_BACKUP_NAME, False)

        self.assertIsFalse(self.capabilities._isPrivilegeEnabled(
            win32security.SE_BACKUP_NAME))

        self.capabilities._adjustPrivilege(
            win32security.SE_BACKUP_NAME, initial_state)

        self.assertEquals(
            initial_state,
            self.capabilities._isPrivilegeEnabled(
                win32security.SE_BACKUP_NAME),
            )

    def test_elevatePrivileges_invalid_privilege(self):
        """
        It raise an exception when an invalid privilege name is requested.
        """
        with self.assertRaises(AdjustPrivilegeException):
            with (self.capabilities.elevatePrivileges(
                win32security.SE_IMPERSONATE_NAME,
                'no-such-privilege-name',
                    )):
                pass

    def test_elevatePrivileges_take_ownership_success(self):
        """
        elevatePrivileges is a context manager which will elevate the
        privileges for current process upon entering the context,
        and restore them on exit.
        """
        # We use SE_TAKE_OWNERSHIP privilege as it should be present for
        # super user and disabled by default.
        privilege = win32security.SE_TAKE_OWNERSHIP_NAME
        self.assertFalse(self.capabilities._isPrivilegeEnabled(privilege))

        with (self.capabilities.elevatePrivileges(privilege)):
            self.assertTrue(self.capabilities._isPrivilegeEnabled(privilege))

        # We should be able to take ownership again.
        with (self.capabilities.elevatePrivileges(privilege)):
            self.assertTrue(self.capabilities._isPrivilegeEnabled(privilege))

        self.assertFalse(self.capabilities._isPrivilegeEnabled(privilege))

    def test_elevatePrivilege_impersonate_unchanged(self):
        """
        elevatePrivilege will not modify the process if the privilege is
        already enabled.
        """
        # We use SE_IMPERSONATE as it should be enabled by default.
        privilege = win32security.SE_IMPERSONATE_NAME
        self.assertTrue(self.capabilities._isPrivilegeEnabled(privilege))

        capabilities = self.capabilities
        with self.Patch.object(capabilities, '_adjustPrivilege') as method:
            with (capabilities.elevatePrivileges(privilege)):
                self.assertFalse(method.called)
                self.assertTrue(capabilities._isPrivilegeEnabled(privilege))

        self.assertTrue(self.capabilities._isPrivilegeEnabled(privilege))

    def test_elevatePrivilege_multiple_privileges_success(self):
        """
        elevatePrivileges supports a variable list of privilege name
        arguments and will make sure all of them are enabled.
        """
        # We use SE_IMPERSONATE as it is enabled by default
        # We also use SE_TAKE_OWNERSHIP as it is disabled by default but can
        # be enabled when running as super user.
        take_ownership = win32security.SE_TAKE_OWNERSHIP_NAME
        impersonate = win32security.SE_IMPERSONATE_NAME
        self.assertTrue(self.capabilities._isPrivilegeEnabled(impersonate))
        self.assertFalse(
            self.capabilities._isPrivilegeEnabled(take_ownership))

        capabilities = self.capabilities
        with (capabilities.elevatePrivileges(take_ownership, impersonate)):
            self.assertTrue(
                self.capabilities._isPrivilegeEnabled(impersonate))
            self.assertTrue(
                self.capabilities._isPrivilegeEnabled(take_ownership))

        self.assertTrue(self.capabilities._isPrivilegeEnabled(impersonate))
        self.assertFalse(
            self.capabilities._isPrivilegeEnabled(take_ownership))

    def test_symbolic_link(self):
        """
        Support on all Unix and Vista and above.

        Not supported on Windows without elevated permissions.
        """
        symbolic_link = self.capabilities.symbolic_link

        if self.os_family == 'posix':
            self.assertTrue(symbolic_link)
            return

        if self.runningAsAdministrator():
            self.assertTrue(symbolic_link)
        else:
            self.assertFalse(symbolic_link)
