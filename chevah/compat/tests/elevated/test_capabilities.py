# Copyright (c) 2011 Adi Roiban.
# See LICENSE for details.
"""
Capabilities detection tests for accounts with elevated permissions.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import os

from chevah.compat import process_capabilities, system_users
from chevah.compat.exceptions import AdjustPrivilegeException
from chevah.compat.testing import conditionals
from chevah.compat.testing.testcase import FileSystemTestCase


class TestProcessCapabilities(FileSystemTestCase):

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

    @conditionals.onOSFamily('posix')
    def test_get_home_folder_posix(self):
        """
        On Unix we can always get home folder.
        """
        result = self.capabilities.get_home_folder

        self.assertTrue(result)

    @conditionals.onOSFamily('nt')
    @conditionals.onAdminPrivileges(True)
    def test_get_home_folder_windows_admin(self):
        """
        Home folder can be retrieved when running with administrator
        privileges.
        """
        result = self.capabilities.get_home_folder

        self.assertTrue(result)

    def test_getCurrentPrivilegesDescription(self):
        """
        Lists all available privileges and their state.
        """
        text = self.capabilities.getCurrentPrivilegesDescription()
        if os.name == 'posix':
            self.assertEqual(u'root capabilities enabled.', text)
        else:
            expected_capabilities = (
                'SeIncreaseQuotaPrivilege:0, SeSecurityPrivilege:0, '
                'SeTakeOwnershipPrivilege:0, SeLoadDriverPrivilege:0, '
                'SeSystemProfilePrivilege:0, SeSystemtimePrivilege:0, '
                'SeProfileSingleProcessPrivilege:0, '
                'SeIncreaseBasePriorityPrivilege:0, '
                'SeCreatePagefilePrivilege:0, SeBackupPrivilege:0, '
                'SeRestorePrivilege:0, SeShutdownPrivilege:0, '
                'SeDebugPrivilege:0, SeSystemEnvironmentPrivilege:0, '
                'SeChangeNotifyPrivilege:3, SeRemoteShutdownPrivilege:0, '
                'SeUndockPrivilege:0, SeManageVolumePrivilege:0, '
                'SeImpersonatePrivilege:3, SeCreateGlobalPrivilege:3, '
                'SeIncreaseWorkingSetPrivilege:0, SeTimeZonePrivilege:0, '
                'SeCreateSymbolicLinkPrivilege:0'
                )
            if self.os_version == 'nt-10.0':
                # On Win 2016 we have an extra capability by default.
                expected_capabilities += (
                    ', SeDelegateSessionUserImpersonatePrivilege:0'
                    )
            # This assertion is fragile. Feel free to improve it.
            self.assertEqual(expected_capabilities, text)

    @conditionals.onOSFamily('posix')
    def test_getCurrentPrivilegesDescription_impersonated(self):
        """
        getCurrentPrivilegesDescription can be used for impersonated accounts
        and will still get full process capabilities.

        The process under impersonated account still has root capabilities.
        """
        with system_users.executeAsUser(
                username=self.os_user.name, token=self.os_user.token):
            text = self.capabilities.getCurrentPrivilegesDescription()

        self.assertEqual(u'root capabilities enabled.', text)

    @conditionals.onOSFamily('nt')
    def test_getCurrentPrivilegesDescription_impersonated_nt(self):
        """
        getCurrentPrivilegesDescription can be used for impersonated accounts
        and will return the impersonated user's capabilities instead.
        """
        # FIXME:2095:
        # Unify tests once proper capabilities support is implemented.
        initial_text = self.capabilities.getCurrentPrivilegesDescription()
        self.assertContains(u'SeIncreaseWorkingSetPrivilege:0', initial_text)

        with system_users.executeAsUser(
                username=self.os_user.name, token=self.os_user.token):
            text = self.capabilities.getCurrentPrivilegesDescription()

        # These assertion are fragile. Feel free to improve it.
        self.assertContains(u'SeIncreaseWorkingSetPrivilege:3', text)

    @conditionals.onOSFamily('nt')
    def test_elevatePrivileges_impersonated(self):
        """
        Can elevate privileges while running under impersonated account if
        privilege is already present.
        """
        import win32security

        initial_state = self.capabilities._getPrivilegeState(
            win32security.SE_INC_WORKING_SET_NAME)
        self.assertEqual(u'present', initial_state)

        with system_users.executeAsUser(
                username=self.os_user.name, token=self.os_user.token):
            with self.capabilities._elevatePrivileges(
                    win32security.SE_INC_WORKING_SET_NAME):
                update_state = self.capabilities._getPrivilegeState(
                    win32security.SE_INC_WORKING_SET_NAME)

        self.assertStartsWith(u'enabled', update_state)

    @conditionals.onOSFamily('nt')
    def test_elevatePrivileges_impersonated_not_present(self):
        """
        Trying to elevate privilege under impersonated account will raise
        an error if privilege is not present.
        """
        import win32security

        with system_users.executeAsUser(
                username=self.os_user.name, token=self.os_user.token):
            initial_state = self.capabilities._getPrivilegeState(
                win32security.SE_CREATE_SYMBOLIC_LINK_NAME)
            self.assertEqual(u'absent', initial_state)

            with self.assertRaises(AdjustPrivilegeException):
                with self.capabilities._elevatePrivileges(
                        win32security.SE_CREATE_SYMBOLIC_LINK_NAME):
                    pass
