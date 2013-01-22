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
from chevah.compat.platform import os_administration, OSUser
from chevah.compat.helpers import NoOpContext
from chevah.empirical import ChevahTestCase, factory
from chevah.empirical.constants import (
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
from chevah.utils.exceptions import (
    ChangeUserException,
    OperationalException,
    )
from chevah.utils.interfaces import IHasImpersonatedAvatar


class TestSystemUsers(ChevahTestCase):
    '''Test system users operations.'''

    def test_userExists(self):
        '''Test userExists.'''
        self.assertTrue(system_users.userExists(TEST_ACCOUNT_USERNAME))
        self.assertFalse(system_users.userExists('non-existent-patricia'))

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

        credentials = factory.makePasswordCredentials(
            username=TEST_ACCOUNT_USERNAME,
            password=TEST_ACCOUNT_PASSWORD)
        token = factory.makeToken(credentials)

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

        with self.assertRaises(OperationalException) as context:
            system_users.getHomeFolder(username=TEST_ACCOUNT_USERNAME)

        self.assertEqual(1014, context.exception.id)

    def test_getHomeFolder_bad_nt(self):
        """
        If no token is provided, we can get to folder path for current
        account.
        """
        if os.name != 'nt' or not process_capabilities.get_home_folder:
            raise self.skipTest()

        home_folder = system_users.getHomeFolder(factory.username)
        self.assertContains(factory.username, home_folder)

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
        user = OSUser(
            name=username, uid=None, password=password, home_path=home_path)

        try:
            # We don't want to create the profile here since this is
            # what we are testing.
            os_administration._addUser_windows(user, create_profile=False)
            credentials = factory.makePasswordCredentials(
                username=username,
                password=password)
            token = factory.makeToken(credentials)

            home_path = system_users.getHomeFolder(
                username=username, token=token)

            self.assertTrue(
                username.lower() in home_path.lower(),
                'Home folder "%s" is not good for user "%s"' % (
                    home_path, username))
        finally:
            os_administration.deleteUser(user)
            # Delete user does not removed the user home folder,
            # so we explictly remove it here.
            if home_path:
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
        getHomeFolder will always return an unicode path.
        """
        # This test is skiped if we can not get the home folder.
        if not process_capabilities.get_home_folder:
            raise self.skipTest()

        credentials = factory.makePasswordCredentials(
            username=TEST_ACCOUNT_USERNAME,
            password=TEST_ACCOUNT_PASSWORD)
        token = factory.makeToken(credentials)

        home_folder = system_users.getHomeFolder(
            username=TEST_ACCOUNT_USERNAME, token=token)

        self.assertTrue(isinstance(home_folder, unicode))

    def test_getHomeFolder_non_existent_user(self):
        """
        An error is raised by getHomeFolder if account does not exists.
        """
        with self.assertRaises(OperationalException) as context:
            system_users.getHomeFolder(username=u'non-existent-patricia')

        self.assertEqual(1014, context.exception.id)

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
                password=u'mțș',
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
                username=u'other-mșț', password=u'other-mțs')
        self.assertFalse(result)
        self.assertIsNone(token)

    def test_authenticateWithUsernameAndPasswordPAM(self):
        '''Test username and password authentication using PAM.

        This test is only executed on a single slave, which is configured
        with PAM-LDAP. For now it is Ubuntu 10.04 x64.

        I tried to create a custom PAM module, which allows only a specific
        username, but I failed (adi).
        '''
        if 'ubuntu-1004-x64' not in self.getHostname():
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
        credentials = factory.makePasswordCredentials(
            username=TEST_ACCOUNT_USERNAME,
            password=TEST_ACCOUNT_PASSWORD,
            )
        token = factory.makeToken(credentials)
        with system_users.executeAsUser(
                username=credentials.username, token=token):
            pass

        with system_users.executeAsUser(
                username=credentials.username, token=token):
            pass

    def test_getCurrentUserName_NT(self):
        '''Test executing as a different user.'''
        if os.name != 'nt':
            raise self.skipTest()

        self.assertEqual(factory.username, system_users.getCurrentUserName())

    def test_executeAsUser_NT(self):
        '''Test executing as a different user.'''
        if os.name != 'nt':
            raise self.skipTest()

        credentials = factory.makePasswordCredentials(
            username=TEST_ACCOUNT_USERNAME,
            password=TEST_ACCOUNT_PASSWORD,
            )
        token = factory.makeToken(credentials)

        with system_users.executeAsUser(
            username=credentials.username, token=token):
            self.assertEqual(
                credentials.username, system_users.getCurrentUserName())

        self.assertEqual(factory.username, system_users.getCurrentUserName())

    def test_executeAsUser_Unix(self):
        '''Test executing as a different user.'''
        if os.name != 'posix':
            raise self.skipTest()
        initial_uid, initial_gid = os.geteuid(), os.getegid()
        initial_groups = os.getgroups()
        cred = factory.makePasswordCredentials(
            username=TEST_ACCOUNT_USERNAME,
            password=TEST_ACCOUNT_PASSWORD,
            )
        with system_users.executeAsUser(username=cred.username):
            import pwd
            import grp
            uid, gid = os.geteuid(), os.getegid()
            username = pwd.getpwuid(uid)[0].decode('utf-8')
            groupname = grp.getgrgid(gid)[0].decode('utf-8')
            groups = os.getgroups()
            self.assertEqual(cred.username, username)
            self.assertEqual(TEST_ACCOUNT_GROUP, groupname)
            self.assertNotEqual(initial_uid, uid)
            self.assertNotEqual(initial_gid, gid)
            self.assertEqual(2, len(groups))
            self.assertTrue(TEST_ACCOUNT_GID_ANOTHER in groups)
            self.assertTrue(TEST_ACCOUNT_GID in groups)

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
        credentials = factory.makePasswordCredentials(
            username=TEST_ACCOUNT_USERNAME, password=TEST_ACCOUNT_PASSWORD)
        token = factory.makeToken(credentials)

        groups = [u'non-existent-group']
        self.assertFalse(system_users.isUserInGroups(
            username=credentials.username, groups=groups, token=token))

    def test_isUserInGroups_not_in_groups(self):
        """
        False is returned if user is not in the groups.
        """
        credentials = factory.makePasswordCredentials(
            username=TEST_ACCOUNT_USERNAME, password=TEST_ACCOUNT_PASSWORD)
        token = factory.makeToken(credentials)

        groups = [u'root', u'Administrators']

        self.assertFalse(system_users.isUserInGroups(
            username=credentials.username, groups=groups, token=token))

    def test_isUserInGroups_success(self):
        """
        True is returned if user is in groups.
        """
        credentials = factory.makePasswordCredentials(
            username=TEST_ACCOUNT_USERNAME, password=TEST_ACCOUNT_PASSWORD)
        token = factory.makeToken(credentials)

        groups = [
            TEST_ACCOUNT_GROUP,
            TEST_ACCOUNT_GROUP_WIN,
            ]
        self.assertTrue(system_users.isUserInGroups(
            username=credentials.username, groups=groups, token=token))

        groups = [
            u'non-existent-group',
            TEST_ACCOUNT_GROUP,
            TEST_ACCOUNT_GROUP_WIN,
            ]
        self.assertTrue(system_users.isUserInGroups(
            username=credentials.username, groups=groups, token=token))

    def test_getPrimaryGroup_good(self):
        """
        Check getting primary group.
        """
        user = TEST_ACCOUNT_USERNAME
        password = TEST_ACCOUNT_PASSWORD
        credentials = factory.makePasswordCredentials(
            username=user, password=password)
        token = factory.makeToken(credentials)
        avatar = factory.makeOSAvatar(name=TEST_ACCOUNT_USERNAME, token=token)

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
        with self.assertRaises(OperationalException) as context:
            system_users.getPrimaryGroup(username=username)
        self.assertEqual(1015, context.exception.id)


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


class TestHasImpersonatedAvatar(ChevahTestCase):

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
        initial_uid, initial_gid = os.geteuid(), os.getegid()
        initial_groups = os.getgroups()

        with avatar.getImpersonationContext():
            import pwd
            import grp
            uid, gid = os.geteuid(), os.getegid()
            username = pwd.getpwuid(uid)[0].decode('utf-8')
            groupname = grp.getgrgid(gid)[0].decode('utf-8')
            groups = os.getgroups()
            self.assertEqual(TEST_ACCOUNT_USERNAME, username)
            self.assertEqual(TEST_ACCOUNT_GROUP, groupname)
            self.assertNotEqual(initial_uid, uid)
            self.assertNotEqual(initial_gid, gid)
            self.assertEqual(2, len(groups))
            self.assertTrue(TEST_ACCOUNT_GID_ANOTHER in groups)
            self.assertTrue(TEST_ACCOUNT_GID in groups)

        self.assertEqual(initial_uid, os.geteuid())
        self.assertEqual(initial_gid, os.getegid())
        self.assertEqual(initial_groups, os.getgroups())

        self.assertEqual(TEST_ACCOUNT_UID, avatar._euid)
        self.assertEqual(TEST_ACCOUNT_GID, avatar._egid)
        self.assertContains(TEST_ACCOUNT_GID_ANOTHER, avatar._groups)
        self.assertContains(TEST_ACCOUNT_GID, avatar._groups)

    def test_getImpersonationContext_use_impersonation_nt(self):
        """
        If use_impersonation is `True` an impersonation context is active.

        Inside the context we have the new user and outside we have the normal
        user.
        """
        if os.name != 'nt':
            raise self.skipTest()

        credentials = factory.makePasswordCredentials(
            username=TEST_ACCOUNT_USERNAME,
            password=TEST_ACCOUNT_PASSWORD,
            )
        token = factory.makeToken(credentials)
        avatar = ImpersonatedAvatarImplementation(
            name=TEST_ACCOUNT_USERNAME,
            token=token,
            use_impersonation=True,
            )

        with avatar.getImpersonationContext():
            self.assertEqual(
                TEST_ACCOUNT_USERNAME, system_users.getCurrentUserName())

        self.assertEqual(factory.username, system_users.getCurrentUserName())
