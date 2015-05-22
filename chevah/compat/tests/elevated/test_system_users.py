# Copyright (c) 2011 Adi Roiban.
# See LICENSE for details.
'''Test system users portable code code.'''
from __future__ import with_statement
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from builtins import str
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
from chevah.compat.helpers import NoOpContext
from chevah.compat.testing import (
    CompatTestCase,
    conditionals,
    mk,
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
    TEST_ACCOUNT_LDAP_PASSWORD,
    TEST_ACCOUNT_LDAP_USERNAME,
    )
from chevah.compat.exceptions import (
    ChangeUserException,
    CompatError,
    )
from chevah.compat.interfaces import IHasImpersonatedAvatar


class SystemUsersTestCase(CompatTestCase):
    """
    Common code for system users elevated tests.
    """

    def getGroupsIDForTestAccount(self):
        """
        Return a list with groups id for test account.
        """
        expected_groups = [
            TEST_ACCOUNT_GID_ANOTHER,
            TEST_ACCOUNT_GID,
            ]
        if sys.platform.startswith('aix'):
            # On AIX normal accounts are also part of staff group id 1.
            expected_groups.append(1)
        return expected_groups


class TestSystemUsers(SystemUsersTestCase):
    """
    Test system users operations.
    """
    def test_userExists(self):
        """
        Test userExists.
        """
        self.assertTrue(system_users.userExists(TEST_ACCOUNT_USERNAME))
        self.assertFalse(system_users.userExists('non-existent-patricia'))
        self.assertFalse(system_users.userExists(u'non-existent@no-domain'))
        self.assertFalse(system_users.userExists(''))

    def test_getHomeFolder_linux(self):
        """
        On Linux the OS accounts are based in '/home/' folder.
        """
        if not sys.platform.startswith('linux'):
            raise self.skipTest()

        home_folder = system_users.getHomeFolder(
            username=TEST_ACCOUNT_USERNAME)

        self.assertEqual(u'/home/%s' % TEST_ACCOUNT_USERNAME, home_folder)
        self.assertIsInstance(str, home_folder)

    def test_getHomeFolder_no_capabilities(self):
        """
        An error is raised when trying to get home folder when we don't
        have the required capabilities.
        """
        if process_capabilities.get_home_folder:
            raise self.skipTest()

        with self.assertRaises(CompatError) as context:
            system_users.getHomeFolder(username=TEST_ACCOUNT_USERNAME)

        self.assertEqual(1014, context.exception.event_id)

    @conditionals.onOSFamily('osx')
    def test_getHomeFolder_osx(self):
        """
        Check getHomeFolder for OSX.
        """
        home_folder = system_users.getHomeFolder(
            username=TEST_ACCOUNT_USERNAME)

        self.assertEqual(u'/Users/%s' % TEST_ACCOUNT_USERNAME, home_folder)
        self.assertIsInstance(str, home_folder)

    def test_getHomeFolder_non_existing_user(self):
        """
        An error is raised by getHomeFolder if account does not exists.
        """
        with self.assertRaises(CompatError) as context:
            system_users.getHomeFolder(username=u'non-existent-patricia')

        self.assertCompatError(1014, context.exception)

    @conditionals.onOSFamily('nt')
    @conditionals.onCapability('get_home_folder', True)
    def test_getHomeFolder_nt_existing_user_no_token(self):
        """
        An error is raised if user exists but no token is provided.
        """
        username = TEST_ACCOUNT_USERNAME

        with self.assertRaises(CompatError) as context:
            system_users.getHomeFolder(username)

        self.assertCompatError(1014, context.exception)

    @conditionals.onOSFamily('nt')
    @conditionals.onCapability('get_home_folder', True)
    def test_getHomeFolder_nt_custom_user_no_token(self):
        """
        An error is raised if no token is provided and the username differs
        from the current/service username.
        """
        test_user = mk.getTestUser(u'other')

        with self.assertRaises(CompatError) as context:
            system_users.getHomeFolder(test_user.name)

        self.assertCompatError(1014, context.exception)
        self.assertContains(
            'Invalid username/token combination.', context.exception.message)

    @conditionals.onOSFamily('nt')
    @conditionals.onCapability('get_home_folder', True)
    def test_getHomeFolder_nt_good(self):
        """
        If a valid token is provided the home folder path can be retrieved
        for it's corresponding account, as long as the process has the
        required capabilities.
        """
        test_user = TestUser(
            name=mk.string(),
            password=mk.string(),
            create_local_profile=True,
            )
        os_administration.addUser(test_user)

        home_folder = system_users.getHomeFolder(
            username=test_user.name, token=test_user.token)

        self.assertContains(
            test_user.name.lower(), home_folder.lower())
        self.assertIsInstance(str, home_folder)
        self.addCleanup(os_administration.deleteUser, test_user)

    @conditionals.onOSFamily('nt')
    @conditionals.onCapability('get_home_folder', True)
    def test_getHomeFolder_nt_no_token(self):
        """
        If no token is provided, it can still be successfully used for getting
        home folder for current account.
        """
        username = mk.username

        home_folder = system_users.getHomeFolder(username)

        self.assertContains(username.lower(), home_folder.lower())
        self.assertIsInstance(str, home_folder)

    @conditionals.onOSFamily('nt')
    @conditionals.onCapability('get_home_folder', True)
    @conditionals.onCapability('create_home_folder', True)
    def test_getHomeFolder_nt_no_existing_profile(self):
        """
        On Windows, if user has no local home folder it will be created
        automatically when getting the home folder path.

        This test creates a temporary account and in the end it deletes
        the account and it's home folder.
        """
        test_user = TestUser(
            name=u'no-home',
            password=mk.string(),
            create_local_profile=False,
            )
        # Unfortunately there is no API to get default base home path for
        # users, we need to rely on an existing pattern.
        home_base = os.path.dirname(os.getenv('USERPROFILE'))
        expected_home_path = os.path.join(home_base, test_user.name)
        expected_home_segments = mk.fs.getSegmentsFromRealPath(
            expected_home_path)

        try:
            os_administration.addUser(test_user)
            # Home folder path is not created on successful login.
            token = test_user.token
            self.assertFalse(mk.fs.isFolder(expected_home_segments))

            self.home_folder = system_users.getHomeFolder(
                username=test_user.name, token=token)

            self.assertContains(
                test_user.name.lower(), self.home_folder.lower())
            self.assertIsInstance(str, self.home_folder)
            self.assertTrue(mk.fs.isFolder(expected_home_segments))
        finally:
            os_administration.deleteUser(test_user)
            os_administration.deleteHomeFolder(test_user)

    def test_authenticateWithUsernameAndPassword_good(self):
        """
        Check successful call to authenticateWithUsernameAndPassword.
        """
        result, token = system_users.authenticateWithUsernameAndPassword(
            username=TEST_ACCOUNT_USERNAME,
            password=TEST_ACCOUNT_PASSWORD,
            )

        self.assertTrue(result)
        if os.name != 'nt':
            self.assertIsNone(token)
        else:
            self.assertIsNotNone(token)

    def test_authenticateWithUsernameAndPassword_bad_password(self):
        """
        authenticateWithUsernameAndPassword will return False if
        credentials are not valid.
        """
        result, token = system_users.authenticateWithUsernameAndPassword(
            username=TEST_ACCOUNT_USERNAME,
            password=mk.string(),
            )

        self.assertFalse(result)
        self.assertIsNone(token)

    @attr('slow')
    def test_authenticateWithUsernameAndPassword_bad_user(self):
        """
        Check authentication for bad password.

        This is slow since the OS adds a timeout or checks for various
        PAM modules.
        """
        result, token = system_users.authenticateWithUsernameAndPassword(
            username=mk.string(), password=mk.string())

        self.assertFalse(result)
        self.assertIsNone(token)

    def test_authenticateWithUsernameAndPassword_PAM_ldap(self):
        """
        Test username and password authentication using PAM.

        This test is only executed on slaves which are configured
        with PAM-LDAP.

        I tried to create a custom PAM module, which allows only a specific
        username, but I failed (adi).
        """
        if 'ldap' not in self.getHostname():
            raise self.skipTest()

        result, token = system_users.authenticateWithUsernameAndPassword(
            username=TEST_ACCOUNT_LDAP_USERNAME,
            password=TEST_ACCOUNT_LDAP_PASSWORD,
            )
        self.assertTrue(result)
        self.assertIsNone(token)

    def test_authenticateWithUsernameAndPassword_centrify(self):
        '''Test username and password authentication using Centrify.

        Centrify client is only installed on SLES-11-x64.
        '''
        # FIXME:1265:
        # The Centrify server was accidentally removed. We wait for it
        # to be reinstalled and re-enabled this test.
        raise self.skipTest()
        if 'sles-11-x64' not in self.getHostname():
            raise self.skipTest()

        result, token = system_users.authenticateWithUsernameAndPassword(
            username=TEST_ACCOUNT_CENTRIFY_USERNAME,
            password=TEST_ACCOUNT_CENTRIFY_PASSWORD,
            )
        self.assertIsTrue(result)
        self.assertIsNone(token)

    def test_executeAsUser_multiple_call_on_same_credentials(self):
        """
        Test executing as a different user reusing the credentials.
        """
        test_user = mk.getTestUser(u'normal')
        with system_users.executeAsUser(
                username=test_user.name, token=test_user.token):
            pass

        with system_users.executeAsUser(
                username=test_user.name, token=test_user.token):
            pass

    @conditionals.onOSFamily('nt')
    def test_getCurrentUserName_NT(self):
        """
        Check for helper method.
        """
        self.assertEqual(
            mk.username, system_users.getCurrentUserName())

    @conditionals.onOSFamily('nt')
    def test_executeAsUser_NT(self):
        """
        Test executing as a different user.
        """
        test_user = mk.getTestUser(u'normal')

        with system_users.executeAsUser(
                username=test_user.name, token=test_user.token):
            self.assertEqual(
                test_user.name, system_users.getCurrentUserName())

        self.assertEqual(
            mk.username, system_users.getCurrentUserName())

    @conditionals.onOSFamily('posix')
    def test_executeAsUser_Unix(self):
        '''Test executing as a different user.'''
        if os.name != 'posix':
            raise self.skipTest()

        initial_uid, initial_gid = os.geteuid(), os.getegid()
        initial_groups = os.getgroups()
        test_user = mk.getTestUser(u'normal')

        with system_users.executeAsUser(username=test_user.name):
            import pwd
            import grp
            uid, gid = os.geteuid(), os.getegid()
            impersonated_username = pwd.getpwuid(uid)[0].decode('utf-8')
            impersonated_groupname = grp.getgrgid(gid)[0].decode('utf-8')
            impersonated_groups = os.getgroups()
            self.assertEqual(test_user.name, impersonated_username)
            self.assertEqual(TEST_ACCOUNT_GROUP, impersonated_groupname)
            self.assertNotEqual(initial_uid, uid)
            self.assertNotEqual(initial_gid, gid)
            self.assertItemsEqual(
                self.getGroupsIDForTestAccount(), impersonated_groups)

        self.assertEqual(initial_uid, os.geteuid())
        self.assertEqual(initial_gid, os.getegid())
        self.assertEqual(initial_groups, os.getgroups())

    def test_executeAsUser_unix_user_does_not_exists(self):
        """
        If the user does not exist, executeAsUser will raise
        ChangeUserException.
        """
        with self.assertRaises(ChangeUserException):
            system_users.executeAsUser(username=u'no-such-user')

    def test_isUserInGroups_only_default_user_group_unix(self):
        """
        Check isUserInGroups on Unix.
        """
        if os.name != 'posix':
            raise self.skipTest()

        groups = [u'other-non-group', TEST_ACCOUNT_GROUP, u'here-we-go']

        self.assertTrue(system_users.isUserInGroups(
            username=TEST_ACCOUNT_USERNAME, groups=groups))

    def test_isUserInGroups_non_existent_group(self):
        """
        False is returned if isUserInGroups is asked for a non-existent group.
        """
        test_user = mk.getTestUser(u'normal')

        groups = [u'non-existent-group']
        self.assertFalse(system_users.isUserInGroups(
            username=test_user.name, groups=groups, token=test_user.token))

    def test_isUserInGroups_not_in_groups(self):
        """
        False is returned if user is not in the groups.
        """
        test_user = mk.getTestUser(u'normal')

        groups = [u'root', u'Administrators']

        self.assertFalse(system_users.isUserInGroups(
            username=test_user.name, groups=groups, token=test_user.token))

    def test_isUserInGroups_success(self):
        """
        True is returned if user is in groups.
        """
        test_user = mk.getTestUser(u'normal')

        groups = [
            TEST_ACCOUNT_GROUP,
            TEST_ACCOUNT_GROUP_WIN,
            ]
        self.assertTrue(system_users.isUserInGroups(
            username=test_user.name, groups=groups, token=test_user.token))

        groups = [
            u'non-existent-group',
            TEST_ACCOUNT_GROUP,
            TEST_ACCOUNT_GROUP_WIN,
            ]
        self.assertTrue(system_users.isUserInGroups(
            username=test_user.name, groups=groups, token=test_user.token))

    def test_getPrimaryGroup_good(self):
        """
        Check getting primary group.
        """
        test_user = mk.getTestUser(u'normal')
        avatar = mk.makeFilesystemOSAvatar(
            name=TEST_ACCOUNT_USERNAME, token=test_user.token)

        group_name = system_users.getPrimaryGroup(username=avatar.name)
        if os.name == 'nt':
            self.assertEqual(WINDOWS_PRIMARY_GROUP, group_name)
        else:
            self.assertEqual(TEST_ACCOUNT_GROUP, group_name)

    def test_getPrimaryGroup_unknown_username(self):
        """
        An error is raised when requesting the primary group for an
        unknown user.
        """
        username = u'non-existent-username'
        with self.assertRaises(CompatError) as context:
            system_users.getPrimaryGroup(username=username)
        self.assertEqual(1015, context.exception.event_id)


class ImpersonatedAvatarImplementation(HasImpersonatedAvatar):
    """
    Implementation of HasImpersonatedAvatar to help with testing.

    'name' and 'token' attributes should be provided, and
    'use_impersonation' implemented.
    """
    def __init__(self, name=None, token=None, use_impersonation=None):
        self.name = name
        self.token = token
        self._use_impersonation = use_impersonation

    @property
    def use_impersonation(self):
        return self._use_impersonation


class TestHasImpersonatedAvatar(SystemUsersTestCase):

    def test_init_implementation(self):
        """
        Check default values for an implementation.
        """
        avatar = ImpersonatedAvatarImplementation()

        self.assertProvides(IHasImpersonatedAvatar, avatar)

        # On Unix we have some cached values.
        if os.name == 'posix':
            self.assertIsNone(avatar._groups)
            self.assertIsNone(avatar._euid)
            self.assertIsNone(avatar._egid)

    def test_getImpersonationContext_no_impersonation(self):
        """
        If use_impersonation is `False` NoOpContext will be returned.
        """
        avatar = ImpersonatedAvatarImplementation(use_impersonation=False)

        result = avatar.getImpersonationContext()

        self.assertIsInstance(NoOpContext, result)

        # On Unix the cached values should not change.
        if os.name == 'posix':
            self.assertIsNone(avatar._groups)
            self.assertIsNone(avatar._euid)
            self.assertIsNone(avatar._egid)

    def test_getImpersonationContext_use_impersonation_posix(self):
        """
        If use_impersonation is `True` an impersonation context is active.
        """
        if os.name != 'posix':
            raise self.skipTest()

        avatar = ImpersonatedAvatarImplementation(
            name=TEST_ACCOUNT_USERNAME,
            use_impersonation=True,
            )

        with self.patch('chevah.compat.unix_users._ExecuteAsUser') as (
                mock_execute):
            with avatar.getImpersonationContext():
                pass

        self.assertEqual(1, mock_execute.call_count)
        _, kwargs = mock_execute.call_args
        self.assertEqual(TEST_ACCOUNT_GID, kwargs['egid'])
        self.assertEqual(TEST_ACCOUNT_UID, kwargs['euid'])
        self.assertItemsEqual(
            self.getGroupsIDForTestAccount(), kwargs['groups'])

    @conditionals.onOSFamily('nt')
    def test_getImpersonationContext_use_impersonation_nt(self):
        """
        If use_impersonation is `True` an impersonation context is active.

        Inside the context we have the new user and outside we have the normal
        user.
        """
        test_user = mk.getTestUser(u'normal')
        avatar = ImpersonatedAvatarImplementation(
            name=test_user.name,
            token=test_user.token,
            use_impersonation=True,
            )

        with avatar.getImpersonationContext():
            self.assertEqual(
                test_user.name, system_users.getCurrentUserName())

        self.assertEqual(
            mk.username, system_users.getCurrentUserName())
