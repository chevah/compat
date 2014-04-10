# Copyright (c) 2011 Adi Roiban.
# See LICENSE for details.
"""
Capabilities detection tests for accounts with elevated permissions.
"""
import os

from chevah.compat import process_capabilities, system_users
from chevah.compat.testing import (
    conditionals,
    manufacture,
    TEST_ACCOUNT_PASSWORD,
    TEST_ACCOUNT_USERNAME,
    )
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
        text = self.capabilities.getCurrentPrivilegesDescription()
        if os.name == 'posix':
            self.assertEqual(u'root capabilities enabled.', text)
        else:
            # This assertion is fragile. Feel free to improve it.
            self.assertEqual(
                u'SeIncreaseQuotaPrivilege:0, SeSecurityPrivilege:0, '
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
                'SeCreateSymbolicLinkPrivilege:0',
                text,
                )

    @conditionals.onOSFamily('posix')
    def test_getCurrentPrivilegesDescription_impersonated(self):
        """
        getCurrentPrivilegesDescription can be used for impersonated accounts
        and will still get full process capabilities.

        The process under impersonated account still has root capabilities.
        """
        username = TEST_ACCOUNT_USERNAME
        token = manufacture.makeToken(
            username=username, password=TEST_ACCOUNT_PASSWORD)

        with system_users.executeAsUser(username=username, token=token):
            text = self.capabilities.getCurrentPrivilegesDescription()

        self.assertEqual(u'root capabilities enabled.', text)

    @conditionals.onOSFamily('nt')
    def test_getCurrentPrivilegesDescription_impersonated_nt(self):
        """
        getCurrentPrivilegesDescription can be used for impersonated accounts
        and will return the impersonated user's capabilities instead.
        """
        username = TEST_ACCOUNT_USERNAME
        token = manufacture.makeToken(
            username=username, password=TEST_ACCOUNT_PASSWORD)

        # FIXME:2095:
        # Unify tests once proper capabilities support is implemented.
        with system_users.executeAsUser(username=username, token=token):
            text = self.capabilities.getCurrentPrivilegesDescription()

        # This assertion is fragile. Feel free to improve it.
        self.assertEqual(
            u'SeShutdownPrivilege:3, SeChangeNotifyPrivilege:3, '
            'SeUndockPrivilege:3, SeIncreaseWorkingSetPrivilege:3, '
            'SeTimeZonePrivilege:3, SeCreateSymbolicLinkPrivilege:3',
            text,
            )

    @conditionals.onOSFamily('nt')
    def test_elevatePrivileges_impersonated(self):
        """
        Can elevate privileges while running under impersonated account.
        """
        import win32security

        username = TEST_ACCOUNT_USERNAME
        token = manufacture.makeToken(
            username=username, password=TEST_ACCOUNT_PASSWORD)
        initial_state = self.capabilities._getPrivilegeState(
            win32security.SE_CREATE_SYMBOLIC_LINK_NAME)
        self.assertEqual(u'present', initial_state)

        with system_users.executeAsUser(username=username, token=token):
            with self.capabilities.elevatePrivileges(
                    win32security.SE_CREATE_SYMBOLIC_LINK_NAME):
                update_state = self.capabilities._getPrivilegeState(
                    win32security.SE_CREATE_SYMBOLIC_LINK_NAME)

        self.assertStartsWith(u'enabled', update_state)
