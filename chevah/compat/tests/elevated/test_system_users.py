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
from chevah.compat.helpers import NoOpContext
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
    TEST_ACCOUNT_LDAP_PASSWORD,
    TEST_ACCOUNT_LDAP_USERNAME,
    )
from chevah.compat.exceptions import (
    ChangeUserException,
    CompatError,
    )
from chevah.compat.interfaces import IHasImpersonatedAvatar


class SystemUsersTestCase(ChevahTestCase):
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
    '''Test system users operations.'''

    def test_userExists(self):
        """Test userExists."""
        self.assertTrue(system_users.userExists(TEST_ACCOUNT_USERNAME))
        self.assertFalse(system_users.userExists('non-existent-patricia'))
        self.assertFalse(system_users.userExists('non-existent@no-domain'))
        self.assertFalse(system_users.userExists(''))

    def test_getHomeFolder_linux(self):
        """
        On Linux the OS accounts are based in '/home/' folder.
        """
        if not sys.platform.startswith('linux'):
            raise self.skipTest()

        home_folder = system_users.getHomeFolder(
            username=TEST_ACCOUNT_USERNAME)

        self.assertEqual(u'/home/' + TEST_ACCOUNT_USERNAME, home_folder)

    def test_getHomeFolder_good_nt(self):
        """
        If a valid token is provided the home folder path can be retrieved
        for any other account, as long as the process has the required
        capabilities.
        """
        if os.name != 'nt' or not process_capabilities.get_home_folder:
            raise self.skipTest()

        token = manufacture.makeToken(
            username=TEST_ACCOUNT_USERNAME,
            password=TEST_ACCOUNT_PASSWORD)

        home_folder = system_users.getHomeFolder(
            username=TEST_ACCOUNT_USERNAME, token=token)

        self.assertContains(
            TEST_ACCOUNT_USERNAME.lower(), home_folder.lower())

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

    def test_getHomeFolder_bad_nt(self):
        """
        If no token is provided, we can get to folder path for current
        account.
        """
        if os.name != 'nt' or not process_capabilities.get_home_folder:
            raise self.skipTest()

        home_folder = system_users.getHomeFolder(manufacture.username)
        self.assertContains(manufacture.username, home_folder)

    def test_getHomeFolder_nt_no_previous_profile(self):
        """
        On Windows, if user has no profile it will be created.

        This tests creates a temporary account and in the end it deletes
        the account and home folder.
        """
        # Only available on Windows
        if os.name != 'nt':
            raise self.skipTest()

        # Only available if we can get user's home folder path.
        if not process_capabilities.get_home_folder:
            raise self.skipTest()

        # Only available if we can create user's home folder.
        if not process_capabilities.create_home_folder:
            raise self.skipTest()

        username = u'no-home'
        password = u'no-home'
        home_path = None
        user = TestUser(
            name=username, uid=None, password=password, home_path=home_path)

        try:
            # We don't want to create the profile here since this is
            # what we are testing.
            os_administration._addUser_windows(user, create_profile=False)
            token = manufacture.makeToken(
                username=username, password=password)

            home_path = system_users.getHomeFolder(
                username=username, token=token)

            self.assertTrue(
                username.lower() in home_path.lower(),
                'Home folder "%s" is not good for user "%s"' % (
                    home_path, username))
        finally:
            os_administration.deleteUser(user)
            # Delete user does not removed the user home folder,
            # so we explicitly remove it here.
            if home_path:
                # If filesystem.deleteFolder is used then 'Access denied'
                # is return because Windows sees some opened files inside the
                # directory.
                os.system('rmdir /S /Q ' + home_path.encode('utf-8'))

    def test_getHomeFolder_osx(self):
        """
        Check getHomeFolder for OSX.
        """
        if not sys.platform.startswith('darwin'):
            raise self.skipTest()

        home_folder = system_users.getHomeFolder(
            username=TEST_ACCOUNT_USERNAME)

        self.assertEqual(u'/Users/' + TEST_ACCOUNT_USERNAME, home_folder)

    def test_getHomeFolder_return_type(self):
        """
        getHomeFolder will always return an Unicode path.
        """
        # This test is skipped if we can not get the home folder.
        if not process_capabilities.get_home_folder:
            raise self.skipTest()

        token = manufacture.makeToken(
            username=TEST_ACCOUNT_USERNAME,
            password=TEST_ACCOUNT_PASSWORD)

        home_folder = system_users.getHomeFolder(
            username=TEST_ACCOUNT_USERNAME, token=token)

        self.assertTrue(isinstance(home_folder, unicode))

    def test_getHomeFolder_non_existent_user(self):
        """
        An error is raised by getHomeFolder if account does not exists.
        """
        with self.assertRaises(CompatError) as context:
            system_users.getHomeFolder(username=u'non-existent-patricia')

        self.assertEqual(1014, context.exception.event_id)

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
        credendials are not valid.
        """
        result, token = system_users.authenticateWithUsernameAndPassword(
                username=TEST_ACCOUNT_USERNAME,
                password=manufacture.string(),
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
                username=manufacture.string(), password=manufacture.string())
        self.assertFalse(result)
        self.assertIsNone(token)

    def test_authenticateWithUsernameAndPasswordPAM(self):
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
        if not 'sles-11-x64' in self.getHostname():
            raise self.skipTest()

        result, token = system_users.authenticateWithUsernameAndPassword(
                username=TEST_ACCOUNT_CENTRIFY_USERNAME,
                password=TEST_ACCOUNT_CENTRIFY_PASSWORD,
                )
        self.assertIsTrue(result)
        self.assertIsNone(token)

    def test_executeAsUser_multiple_call_on_same_credentials(self):
        '''Test executing as a different user reusing the credentials.'''
        username = TEST_ACCOUNT_USERNAME
        token = manufacture.makeToken(
            username=username, password=TEST_ACCOUNT_PASSWORD)
        with system_users.executeAsUser(
                username=username, token=token):
            pass

        with system_users.executeAsUser(
                username=username, token=token):
            pass

    def test_getCurrentUserName_NT(self):
        """
        Check for helper method.
        """
        if os.name != 'nt':
            raise self.skipTest()

        self.assertEqual(
            manufacture.username, system_users.getCurrentUserName())

    def test_executeAsUser_NT(self):
        '''Test executing as a different user.'''
        if os.name != 'nt':
            raise self.skipTest()

        username = TEST_ACCOUNT_USERNAME
        token = manufacture.makeToken(
            username=username, password=TEST_ACCOUNT_PASSWORD)

        with system_users.executeAsUser(
            username=username, token=token):
            self.assertEqual(
                username, system_users.getCurrentUserName())

        self.assertEqual(
            manufacture.username, system_users.getCurrentUserName())

    def test_executeAsUser_Unix(self):
        '''Test executing as a different user.'''
        if os.name != 'posix':
            raise self.skipTest()
        initial_uid, initial_gid = os.geteuid(), os.getegid()
        initial_groups = os.getgroups()
        username = TEST_ACCOUNT_USERNAME

        with system_users.executeAsUser(username=username):

            import pwd
            import grp
            uid, gid = os.geteuid(), os.getegid()
            impersonated_username = pwd.getpwuid(uid)[0].decode('utf-8')
            impersonated_groupname = grp.getgrgid(gid)[0].decode('utf-8')
            impersonated_groups = os.getgroups()
            self.assertEqual(username, impersonated_username)
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
        If the user does not exist, exetueAsUser will raise
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
        username = TEST_ACCOUNT_USERNAME
        token = manufacture.makeToken(
            username=username, password=TEST_ACCOUNT_PASSWORD)

        groups = [u'non-existent-group']
        self.assertFalse(system_users.isUserInGroups(
            username=username, groups=groups, token=token))

    def test_isUserInGroups_not_in_groups(self):
        """
        False is returned if user is not in the groups.
        """
        username = TEST_ACCOUNT_USERNAME
        token = manufacture.makeToken(
            username=username, password=TEST_ACCOUNT_PASSWORD)

        groups = [u'root', u'Administrators']

        self.assertFalse(system_users.isUserInGroups(
            username=username, groups=groups, token=token))

    def test_isUserInGroups_success(self):
        """
        True is returned if user is in groups.
        """
        username = TEST_ACCOUNT_USERNAME
        token = manufacture.makeToken(
            username=TEST_ACCOUNT_USERNAME, password=TEST_ACCOUNT_PASSWORD)

        groups = [
            TEST_ACCOUNT_GROUP,
            TEST_ACCOUNT_GROUP_WIN,
            ]
        self.assertTrue(system_users.isUserInGroups(
            username=username, groups=groups, token=token))

        groups = [
            u'non-existent-group',
            TEST_ACCOUNT_GROUP,
            TEST_ACCOUNT_GROUP_WIN,
            ]
        self.assertTrue(system_users.isUserInGroups(
            username=username, groups=groups, token=token))

    def test_getPrimaryGroup_good(self):
        """
        Check getting primary group.
        """
        user = TEST_ACCOUNT_USERNAME
        password = TEST_ACCOUNT_PASSWORD
        token = manufacture.makeToken(
            username=user, password=password)
        avatar = manufacture.makeFilesystemOSAvatar(
            name=TEST_ACCOUNT_USERNAME, token=token)

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
    Implementatation of HasImpersonatedAvatar to help with testing.

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

    def test_getImpersonationContext_use_impersonation_nt(self):
        """
        If use_impersonation is `True` an impersonation context is active.

        Inside the context we have the new user and outside we have the normal
        user.
        """
        if os.name != 'nt':
            raise self.skipTest()

        token = manufacture.makeToken(
            username=TEST_ACCOUNT_USERNAME,
            password=TEST_ACCOUNT_PASSWORD,
            )
        avatar = ImpersonatedAvatarImplementation(
            name=TEST_ACCOUNT_USERNAME,
            token=token,
            use_impersonation=True,
            )

        with avatar.getImpersonationContext():
            self.assertEqual(
                TEST_ACCOUNT_USERNAME, system_users.getCurrentUserName())

        self.assertEqual(
            manufacture.username, system_users.getCurrentUserName())
