# Copyright (c) 2011 Adi Roiban.
# See LICENSE for details.
"""
Test system users portable code.
"""
import sys

from chevah.compat import (
    DefaultAvatar,
    system_users,
    SuperAvatar,
    )
from chevah.compat.interfaces import IFileSystemAvatar, IOSUsers
from chevah.compat.testing import (
    CompatTestCase,
    conditionals,
    mk,
    TEST_DOMAIN,
    TEST_PDC,
    )


class TestSystemUsers(CompatTestCase):
    """
    Test system users operations.
    """

    def test_init(self):
        """
        Check initialization of system users.
        """
        self.assertProvides(IOSUsers, system_users)

    def test_getHomeFolder_linux(self):
        """
        Check getHomeFolder on Linux.
        """
        if not sys.platform.startswith('linux'):
            raise self.skipTest()

        home_folder = system_users.getHomeFolder(
            username=mk.username)

        # For buildslave, home folder is in srv.
        if mk.username == 'buildslave':
            self.assertEqual(u'/srv/' + mk.username, home_folder)
        else:
            self.assertEqual(u'/home/' + mk.username, home_folder)

        self.assertIsInstance(unicode, home_folder)

    @conditionals.onOSFamily('nt')
    @conditionals.onCapability('get_home_folder', True)
    def test_getHomeFolder_nt(self):
        """
        Check getHomeFolder for Windows.
        """
        home_folder = system_users.getHomeFolder(
            username=mk.username)

        self.assertContains(
            mk.username.lower(), home_folder.lower())
        self.assertIsInstance(unicode, home_folder)

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
        upn = u'%s@%s' % (name, test_domain)

        (pdc, username) = system_users._parseUPN(upn)

        self.assertEqual(pdc, test_pdc)
        self.assertEqual(name, username)

    @conditionals.onOSName('osx')
    def test_getHomeFolder_osx(self):
        """
        Check getHomeFolder for OSX.
        """
        home_folder = system_users.getHomeFolder(
            username=mk.username)

        self.assertEqual(u'/Users/' + mk.username, home_folder)
        self.assertIsInstance(unicode, home_folder)

    @conditionals.onOSFamily('posix')
    def test_pam_support_unix(self):
        """
        Check that PAM is supported on the Unix systems.
        """
        from pam import authenticate as expected_authenticate

        pam_authenticate = system_users._getPAMAuthenticate()

        self.assertEqual(expected_authenticate, pam_authenticate)

    def test_shadow_support_unix(self):
        """
        Check that shadow files are supported on the expected Unix systems.
        """
        # AIX and OSX only uses PAM.
        # Windows don't support shadow.
        if self.os_name in ['aix', 'osx', 'windows']:
            raise self.skipTest()

        from chevah.compat.unix_users import HAS_SHADOW_SUPPORT

        self.assertTrue(HAS_SHADOW_SUPPORT)


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
