# Copyright (c) 2011 Adi Roiban.
# See LICENSE for details.
"""
Capabilities detection tests for accounts with elevated permissions.
"""

from chevah_compat import process_capabilities, system_users
from chevah_compat.exceptions import AdjustPrivilegeException
from chevah_compat.testing import conditionals
from chevah_compat.testing.testcase import FileSystemTestCase


class TestProcessCapabilities(FileSystemTestCase):
    def setUp(self):
        super().setUp()
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

    @conditionals.onAdminPrivileges(True)
    def test_get_home_folder_windows_admin(self):
        """
        Home folder can be retrieved when running with administrator
        privileges.
        """
        result = self.capabilities.get_home_folder

        self.assertTrue(result)

    @conditionals.onOSFamily('posix')
    def test_getCurrentPrivilegesDescription_posix(self):
        """
        Lists all available privileges. On Posix there are limited
        capabilities.
        """
        text = self.capabilities.getCurrentPrivilegesDescription()
        self.assertEqual('root capabilities enabled.', text)

    @conditionals.onOSFamily('nt')
    def test_getCurrentPrivilegesDescription_nt(self):
        """
        Lists all available privileges and their state.
        """
        if self.ci_name == self.CI.TRAVIS:
            raise self.skipTest('Travis always run as Administrator.')

        text = self.capabilities.getCurrentPrivilegesDescription()
        # Capabilities for slaves running as service, outside of UAC, or
        # with UAC -> Run as administrator.
        service_capabilities = (
            'SeIncreaseQuotaPrivilege:0, SeSecurityPrivilege:0, '
            'SeTakeOwnershipPrivilege:0, SeLoadDriverPrivilege:0, '
            'SeSystemProfilePrivilege:0, SeSystemtimePrivilege:0, '
            'SeProfileSingleProcessPrivilege:0, '
            'SeIncreaseBasePriorityPrivilege:0, '
            'SeCreatePagefilePrivilege:0, SeBackupPrivilege:2, '
            'SeRestorePrivilege:2, SeShutdownPrivilege:0, '
            'SeDebugPrivilege:2, SeSystemEnvironmentPrivilege:0, '
            'SeChangeNotifyPrivilege:3, SeRemoteShutdownPrivilege:0, '
            'SeUndockPrivilege:0, SeManageVolumePrivilege:0, '
            'SeImpersonatePrivilege:3, SeCreateGlobalPrivilege:3, '
            'SeIncreaseWorkingSetPrivilege:0, SeTimeZonePrivilege:0, '
            'SeCreateSymbolicLinkPrivilege:0'
        )

        if self.os_version == 'nt-10.0':
            # On latest Windows there is an extra capability by default.
            service_capabilities += (
                ', SeDelegateSessionUserImpersonatePrivilege:0'
            )
        self.assertEqual(service_capabilities, text)

    @conditionals.onOSFamily('posix')
    def test_getCurrentPrivilegesDescription_impersonated(self):
        """
        getCurrentPrivilegesDescription can be used for impersonated accounts
        and will still get full process capabilities.

        The process under impersonated account still has root capabilities.
        """
        with system_users.executeAsUser(
            username=self.os_user.name,
            token=self.os_user.token,
        ):
            text = self.capabilities.getCurrentPrivilegesDescription()

        self.assertEqual('root capabilities enabled.', text)

    @conditionals.onOSFamily('nt')
    def test_getCurrentPrivilegesDescription_impersonated_nt(self):
        """
        getCurrentPrivilegesDescription can be used for impersonated accounts
        and will return the impersonated user's capabilities instead.
        """
        if self.ci_name == self.CI.TRAVIS:
            raise self.skipTest('Travis always run as Administrator.')

        # Unify tests once proper capabilities support is implemented.
        initial_text = self.capabilities.getCurrentPrivilegesDescription()
        self.assertContains('SeIncreaseWorkingSetPrivilege:0', initial_text)

        with system_users.executeAsUser(
            username=self.os_user.name,
            token=self.os_user.token,
        ):
            text = self.capabilities.getCurrentPrivilegesDescription()

        # These assertion are fragile. Feel free to improve it.
        self.assertContains('SeIncreaseWorkingSetPrivilege:3', text)

    @conditionals.onOSFamily('nt')
    def test_elevatePrivileges_impersonated(self):
        """
        Can elevate privileges while running under impersonated account if
        privilege is already present.
        """
        if self.ci_name == self.CI.TRAVIS:
            raise self.skipTest('Travis always run as Administrator.')

        import win32security

        initial_state = self.capabilities._getPrivilegeState(
            win32security.SE_INC_WORKING_SET_NAME,
        )
        self.assertEqual('present', initial_state)

        with system_users.executeAsUser(
            username=self.os_user.name,
            token=self.os_user.token,
        ):
            with self.capabilities._elevatePrivileges(
                win32security.SE_INC_WORKING_SET_NAME,
            ):
                update_state = self.capabilities._getPrivilegeState(
                    win32security.SE_INC_WORKING_SET_NAME,
                )

        self.assertStartsWith('enabled', update_state)

    @conditionals.onOSFamily('nt')
    def test_elevatePrivileges_impersonated_not_present(self):
        """
        Trying to elevate privilege under impersonated account will raise
        an error if privilege is not present.
        """
        import win32security

        with system_users.executeAsUser(
            username=self.os_user.name,
            token=self.os_user.token,
        ):
            initial_state = self.capabilities._getPrivilegeState(
                win32security.SE_CREATE_SYMBOLIC_LINK_NAME,
            )
            self.assertEqual('absent', initial_state)

            with self.assertRaises(AdjustPrivilegeException):
                with self.capabilities._elevatePrivileges(
                    win32security.SE_CREATE_SYMBOLIC_LINK_NAME,
                ):
                    pass
