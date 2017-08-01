# -*- coding: utf-8 -*-
# Copyright (c) 2011 Adi Roiban.
# See LICENSE for details.
"""
Test for platform capabilities detection.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
try:
    import win32security
except ImportError:
    pass

from zope.interface.verify import verifyObject

from chevah.compat import process_capabilities
from chevah.compat.exceptions import AdjustPrivilegeException
from chevah.compat.interfaces import IProcessCapabilities
from chevah.compat.testing import conditionals, CompatTestCase, mk


@conditionals.onOSFamily('posix')
class TestProcessCapabilitiesPosix(CompatTestCase):
    """
    Unit tests for process capabilities executed on Posix platforms.
    """

    def setUp(self):
        super(TestProcessCapabilitiesPosix, self).setUp()

        self.capabilities = process_capabilities

    def test_init(self):
        """
        Check ProcessCapabilities initialization.
        """
        verifyObject(IProcessCapabilities, self.capabilities)

    def test_impersonate_local_account(self):
        """
        When running under normal account, impersonation is always False
        on Unix.
        """
        result = self.capabilities.impersonate_local_account
        self.assertFalse(result)

    def test_create_home_folder(self):
        """
        When running under normal account, we can not create home folders
        on Unix.
        """
        result = self.capabilities.create_home_folder

        self.assertFalse(result)

    def test_get_home_folder(self):
        """
        On Unix we can always get home home folder.
        On Windows, only Windows 2008 and Windows 7 can get home folder path.
        """
        result = self.capabilities.get_home_folder

        self.assertTrue(result)

    def test_getCurrentPrivilegesDescription(self):
        """
        Check getCurrentPrivilegesDescription.
        """
        text = self.capabilities.getCurrentPrivilegesDescription()

        self.assertEqual(u'root capabilities disabled.', text)

    def test_pam(self):
        """
        PAM is supported on Linux/Unix.
        """
        if self.os_name == 'hpux':
            # FIXME:2745:
            # PAM is not yet supported on HPUX.
            self.assertFalse(self.capabilities.pam)
        elif self.os_name == 'openbsd':
            # OpenBSD does not has PAM by default.
            self.assertFalse(self.capabilities.pam)
        else:
            self.assertTrue(self.capabilities.pam)

    def test_symbolic_link(self):
        """
        Support on all Unix.
        """
        symbolic_link = self.capabilities.symbolic_link

        self.assertTrue(symbolic_link)


@conditionals.onOSFamily('nt')
class TestNTProcessCapabilities(CompatTestCase):
    """
    Capability tests executed only on Windows slaves.
    """

    def setUp(self):
        super(TestNTProcessCapabilities, self).setUp()

        self.capabilities = process_capabilities

    def test_init(self):
        """
        Check ProcessCapabilities initialization.
        """
        verifyObject(IProcessCapabilities, self.capabilities)

    def test_openProcess_success(self):
        """
        _openProcess can be used for process token for the current
        process having a specified mode enabled.
        """
        with self.capabilities._openProcess(win32security.TOKEN_QUERY) as (
                process_token):
            self.assertIsNotNone(process_token)

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

    def test_elevatePrivileges_invalid_privilege(self):
        """
        It raises an exception when an invalid privilege name is requested.
        """
        with self.assertRaises(AdjustPrivilegeException):
            with (self.capabilities._elevatePrivileges(
                    win32security.SE_IMPERSONATE_NAME,
                    'no-such-privilege-name',
                    )):
                pass  # pragma: no cover

    def test_pam(self):
        """
        PAM is not supported on Windows
        """
        self.assertFalse(self.capabilities.pam)


@conditionals.onOSFamily('nt')
@conditionals.onAdminPrivileges(False)
class TestNTProcessCapabilitiesNormalUser(CompatTestCase):
    """
    Capability tests executed only on Windows slaves that are configured to
    run without administrator rights.
    """

    def setUp(self):
        super(TestNTProcessCapabilitiesNormalUser, self).setUp()

        self.capabilities = process_capabilities

    def test_getAvailablePrivileges(self):
        """
        Return a list with privileges and state value.
        """
        result = self.capabilities._getAvailablePrivileges()

        self.assertIsNotEmpty(result)

        privilege = self.capabilities._getPrivilegeID(
            win32security.SE_CHANGE_NOTIFY_NAME)
        self.assertContains((privilege, 3), result)

    def test_getPrivilegeState_invalid(self):
        """
        Return `absent` for unknown names.
        """
        privilege = mk.getUniqueString()

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
        Return `absent` for privileges which are attached to current
        process but are not enabled.
        """
        result = self.capabilities._getPrivilegeState(
            win32security.SE_SECURITY_NAME)

        self.assertEqual(u'absent', result)

    def test_getPrivilegeState_enabled_default(self):
        """
        Return `absent` for privileges which are attached to
        current process but are not enabled by default.
        """
        result = self.capabilities._getPrivilegeState(
            win32security.SE_IMPERSONATE_NAME)

        self.assertEqual(u'absent', result)

    def test_isPrivilegeEnabled_enabled(self):
        """
        Returns False for a privilege which is present and is not enabled.
        """
        # We use SE_IMPERSONATE privilege as it is enabled by default.
        privilege = win32security.SE_IMPERSONATE_NAME

        self.assertFalse(self.capabilities._isPrivilegeEnabled(privilege))

    def test_isPrivilegeEnabled_disabled(self):
        """
        Returns False for a privilege which is present but disabled.
        """
        # By default SE_SECURITY_NAME privilege is disabled.
        privilege = win32security.SE_SECURITY_NAME
        self.assertFalse(self.capabilities._isPrivilegeEnabled(privilege))

    def test_symbolic_link(self):
        """
        Not supported on Windows without elevated permissions.
        """
        symbolic_link = self.capabilities.symbolic_link

        self.assertFalse(symbolic_link)

    def test_impersonate_local_account_windows(self):
        """
        Impersonation is not available when running as a normal user.
        """
        result = self.capabilities.impersonate_local_account

        self.assertFalse(result)

    def test_get_home_folder(self):
        """
        The home folder cannot be retrieved.
        """
        result = self.capabilities.get_home_folder

        self.assertFalse(result)

    def test_create_home_folder(self):
        """
        On Windows home folders can be created if SE_BACKUP and SE_RESTORE
        privileges are available for the process.
        """
        result = self.capabilities.create_home_folder

        # Windows XP does not have SE_BACKUP/SE_RESTORE enabled when not
        # running with administrator privileges.
        if self.os_version == 'nt-5.1':
            self.assertFalse(result)
        else:
            self.assertTrue(result)

    def test_getCurrentPrivilegesDescription(self):
        """
        Check getCurrentPrivilegesDescription.
        """
        text = self.capabilities.getCurrentPrivilegesDescription()

        self.assertContains('SeChangeNotifyPrivilege:3', text)
        self.assertNotContains('SeCreateSymbolicLinkPrivilege', text)
        self.assertNotContains('SeImpersonatePrivilege', text)

        if self.os_version == 'nt-5.1':
            # Windows XP has SE_CREATE_GLOBAL enabled even when
            # running without administrator privileges.
            self.assertContains('SeCreateGlobalPrivilege:3', text)
        else:
            # Windows 2003 is not admin
            self.assertNotContains('SeCreateGlobalPrivilege', text)
            # But the slave should be set up with SE_BACKUP/SE_RESTORE
            self.assertContains('SeBackupPrivilege:0', text)
            self.assertContains('SeRestorePrivilege', text)


@conditionals.onOSFamily('nt')
@conditionals.onAdminPrivileges(True)
class TestNTProcessCapabilitiesAdministrator(CompatTestCase):
    """
    Capability tests executed only on Windows slaves that are configured to
    run with administrator rights.
    """

    def setUp(self):
        super(TestNTProcessCapabilitiesAdministrator, self).setUp()

        self.capabilities = process_capabilities

    def test_getAvailablePrivileges(self):
        """
        Return a list with privileges and state value.
        """
        result = self.capabilities._getAvailablePrivileges()

        self.assertIsNotEmpty(result)

        privilege = self.capabilities._getPrivilegeID(
            win32security.SE_SECURITY_NAME)
        self.assertContains((privilege, 0), result)

        privilege = self.capabilities._getPrivilegeID(
            win32security.SE_IMPERSONATE_NAME)
        self.assertContains((privilege, 3), result)

        privilege = self.capabilities._getPrivilegeID(
            win32security.SE_CREATE_SYMBOLIC_LINK_NAME)
        self.assertContains((privilege, 0), result)

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

        with (self.capabilities._elevatePrivileges(privilege)):
            self.assertTrue(self.capabilities._isPrivilegeEnabled(privilege))

        # We should be able to take ownership again.
        with (self.capabilities._elevatePrivileges(privilege)):
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
            with (capabilities._elevatePrivileges(privilege)):
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
        with (capabilities._elevatePrivileges(take_ownership, impersonate)):
            self.assertTrue(
                self.capabilities._isPrivilegeEnabled(impersonate))
            self.assertTrue(
                self.capabilities._isPrivilegeEnabled(take_ownership))

        self.assertTrue(self.capabilities._isPrivilegeEnabled(impersonate))
        self.assertFalse(
            self.capabilities._isPrivilegeEnabled(take_ownership))

    def test_symbolic_link(self):
        """
        Supported on Vista and above.
        """
        symbolic_link = self.capabilities.symbolic_link

        self.assertTrue(symbolic_link)

    def test_get_home_folder(self):
        """
        The home folder can be retrieved.
        """
        result = self.capabilities.get_home_folder

        self.assertTrue(result)

    def test_create_home_folder(self):
        """
        On Windows home folders can be created if required privileges
        are configured for the process.
        """
        result = self.capabilities.create_home_folder

        self.assertTrue(result)

    def test_getCurrentPrivilegesDescription(self):
        """
        Check that SE_CHANGE_NOTIFY_NAME, SE_IMPERSONATE_NAME and
        SE_CREATE_GLOBAL_NAME are all present in the privileges description
        and enabled.

        Check that SE_CREATE_SYMBOLIC_LINK_NAME is present in the privileges
        description and it's disabled.
        """
        text = self.capabilities.getCurrentPrivilegesDescription()

        self.assertContains('SeChangeNotifyPrivilege:3', text)

        self.assertContains('SeCreateSymbolicLinkPrivilege:0', text)
        self.assertContains('SeImpersonatePrivilege:3', text)
        self.assertContains('SeCreateGlobalPrivilege:3', text)
