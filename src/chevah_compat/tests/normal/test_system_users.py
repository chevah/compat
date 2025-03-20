# Copyright (c) 2011 Adi Roiban.
# See LICENSE for details.
"""
Test system users portable code.
"""

import os

from chevah_compat import DefaultAvatar, SuperAvatar, system_users
from chevah_compat.exceptions import CompatError
from chevah_compat.interfaces import IFileSystemAvatar, IOSUsers
from chevah_compat.testing import (
    TEST_DOMAIN,
    TEST_PDC,
    CompatTestCase,
    conditionals,
    mk,
)


class TestSystemUsers(CompatTestCase):
    """
    Test system users operations under a non-elevated account.
    """

    def test_init(self):
        """
        Check initialization of system users.
        """
        self.assertProvides(IOSUsers, system_users)

    @conditionals.onOSFamily('posix')
    def test_getHomeFolder_posix(self):
        """
        Check getHomeFolder on Linux and Unix.
        """
        home_folder = system_users.getHomeFolder(username=mk.username)

        # For buildslave, home folder is in srv.
        if mk.username == 'buildslave':
            self.assertEqual('/srv/' + mk.username, home_folder)
        elif self.os_name == 'osx':
            self.assertEqual('/Users/' + mk.username, home_folder)
        else:
            self.assertEqual('/home/' + mk.username, home_folder)

        self.assertIsInstance(str, home_folder)

    @conditionals.onOSFamily('nt')
    @conditionals.onCapability('get_home_folder', True)
    def test_getHomeFolder_nt(self):
        """
        Check getHomeFolder for Windows.
        """
        home_folder = system_users.getHomeFolder(username=mk.username)

        self.assertContains(mk.username.lower(), home_folder.lower())
        self.assertIsInstance(str, home_folder)

    def test_userExists_not_found(self):
        """
        Return `False` when user does not exists.
        """
        result = system_users.userExists('no-such-user-\N{SUN}')

        self.assertFalse(result)

    def test_userExists_found(self):
        """
        Return `True` when user exists.
        """
        current_user = os.getenv('USER')
        result = system_users.userExists(current_user)

        self.assertTrue(result)

    @conditionals.onOSFamily('nt')
    def test_parseUPN_no_domain(self):
        """
        Return the exact username and domain `None` when username UPN
        is not a domain.
        """
        name = mk.string()

        (domain, username) = system_users._parseUPN(name)

        self.assertIsNone(domain)
        self.assertEqual(name, username)

    def test_parseUPN_domain(self):
        """
        Return the domain and username when username UPN contains
        a domain.
        """
        # This test is only running on the domain controller slave.
        if '-dc-' not in self.getHostname():
            raise self.skipTest()

        test_domain = TEST_DOMAIN
        test_pdc = TEST_PDC

        name = mk.string()
        upn = f'{name}@{test_domain}'

        (pdc, username) = system_users._parseUPN(upn)

        self.assertEqual(pdc, test_pdc)
        self.assertEqual(name, username)

    def test_shadow_support_unix(self):
        """
        Check that shadow files are supported on the expected Unix systems.
        """
        # OSX only uses PAM.
        # Windows don't support shadow.
        if self.os_name in [
            'aix',
            'freebsd',
            'hpux',
            'openbsd',
            'osx',
            'windows',
        ]:
            raise self.skipTest()

        from chevah_compat.unix_users import HAS_SHADOW_SUPPORT

        self.assertTrue(HAS_SHADOW_SUPPORT)

    @conditionals.onOSName('linux')
    def test_pamWithUsernameAndPassword_no_such_user(self):
        """
        Raise an error for any auth request.
        """
        with self.assertRaises(CompatError) as context:
            system_users.pamWithUsernameAndPassword(
                'no-such-user', 'password-ignored'
            )

        self.assertEqual(1006, context.exception.event_id)

    @conditionals.onOSName('linux')
    def test_pamOnlyWithUsernameAndPassword_no_such_user(self):
        """
        Return false when user is not found.
        """
        if self.os_version.startswith('alpine-'):
            raise self.skipTest('Alpine has no PAM')

        result = system_users.pamOnlyWithUsernameAndPassword(
            'no-such-user', 'password-ignored'
        )

        self.assertIsFalse(result)

    @conditionals.onOSName('linux')
    def test_pamOnlyWithUsernameAndPassword_root_bad_password(self):
        """
        Return false when trying to authenticate the root.
        """
        if self.os_version.startswith('alpine-'):
            raise self.skipTest('Alpine has no PAM')

        result = system_users.pamOnlyWithUsernameAndPassword(
            'root', 'password-bad'
        )

        self.assertIsFalse(result)

    @conditionals.onOSName('linux')
    def test_pamOnlyWithUsernameAndPassword_bad_password(self):
        """
        Return false when trying to authenticate the current user with
        a bad password.
        """
        if self.os_version.startswith('alpine-'):
            raise self.skipTest('Alpine has no PAM')

        if self.ci_name == self.CI.GITHUB and self.os_version == 'ubuntu-24':
            # I don't know why on GHA and Ubuntu 24 any password is accepted
            # by PAM for the curent user.
            raise self.skipTest('GitHub Action user accepts any password.')

        current_user = os.environ.get('USER')
        result = system_users.pamOnlyWithUsernameAndPassword(
            current_user, 'password-bad'
        )

        self.assertIsFalse(result)

    @conditionals.onOSName('linux')
    def test_pamOnlyWithUsernameAndPassword_no_pam(self):
        """
        Raises an error if PAM is not available on the OS.
        """
        if not self.os_version.startswith('alpine-'):
            raise self.skipTest('Test only for Alpine.')

        with self.assertRaises(CompatError) as context:
            system_users.pamWithUsernameAndPassword(
                'no-such-user', 'password-ignored'
            )

        self.assertEqual(1006, context.exception.event_id)


class TestDefaultAvatar(CompatTestCase):
    """
    Tests for default avatar.
    """

    def test_init(self):
        """
        Default avatar is initialized without arguments.
        """
        avatar = DefaultAvatar()

        self.assertProvides(IFileSystemAvatar, avatar)


class TestSuperAvatar(CompatTestCase):
    """
    Tests for super avatar.
    """

    def test_init(self):
        """
        Default avatar is initialized without arguments.
        """
        avatar = SuperAvatar()

        self.assertProvides(IFileSystemAvatar, avatar)
        self.assertFalse(avatar.lock_in_home_folder)

    @conditionals.onOSFamily('posix')
    def test_unix(self):
        """
        Check Unix specific properties.
        """
        avatar = SuperAvatar()

        self.assertEqual('root', avatar.name)
        self.assertTrue(avatar.use_impersonation)

    @conditionals.onOSFamily('nt')
    def test_windows(self):
        """
        Check Windows specific properties.
        """
        avatar = SuperAvatar()

        self.assertFalse(avatar.use_impersonation)
