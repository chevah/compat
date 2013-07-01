# -*- coding: utf-8 -*-
# Copyright (c) 2011 Adi Roiban.
# See LICENSE for details.
'''Test system users portable code code.'''
from __future__ import with_statement
import os
import sys

from chevah.compat import (
    DefaultAvatar,
    process_capabilities,
    system_users,
    SuperAvatar,
    )
from chevah.compat.interfaces import IFileSystemAvatar, IOSUsers
from chevah.compat.testing import (
    CompatTestCase,
    manufacture,
    TEST_DOMAIN,
    TEST_PDC,
    )


class TestSystemUsers(CompatTestCase):
    '''Test system users operations.'''

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
            username=manufacture.username)

        # For buidlslave, home folder is in srv.
        if manufacture.username == 'buildslave':
            self.assertEqual(u'/srv/' + manufacture.username, home_folder)
        else:
            self.assertEqual(u'/home/' + manufacture.username, home_folder)

    def test_getHomeFolder_nt(self):
        """
        Check getHomeFolder for Windows.
        """
        if os.name != 'nt' or not process_capabilities.get_home_folder:
            raise self.skipTest()

        home_folder = system_users.getHomeFolder(
            username=manufacture.username)

        self.assertNotEqual(
            -1,
            home_folder.lower().find(manufacture.username.lower()),
            '%s not in %s' % (manufacture.username, home_folder))

    def test_parseUPN_no_domain(self):
        """
        Return the exact username and domain `None` when username UPN
        is not a domain.
        """
        if os.name != 'nt':
            raise self.skipTest()
        name = manufacture.string()

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

        name = manufacture.string()
        upn = u'%s@%s' % (name, test_domain)

        (pdc, username) = system_users._parseUPN(upn)

        self.assertEqual(pdc, test_pdc)
        self.assertEqual(name, username)

    def test_getHomeFolder_osx(self):
        """
        Check getHomeFolder for OSX.
        """
        if not sys.platform.startswith('darwin'):
            raise self.skipTest()

        home_folder = system_users.getHomeFolder(
            username=manufacture.username)

        self.assertEqual(u'/Users/' + manufacture.username, home_folder)

    def test_getHomeFolder_return_type(self):
        """
        getHomeFolder will always return an unicode path.
        """
        if not process_capabilities.get_home_folder:
            raise self.skipTest()

        home_folder = system_users.getHomeFolder(
            username=manufacture.username)

        self.assertTrue(isinstance(home_folder, unicode))

    def test_pam_support_unix(self):
        """
        Check that PAM is supported on the Unix systems.
        """
        if os.name != 'posix':
            raise self.skipTest()

        from chevah.compat.unix_users import HAS_PAM_SUPPORT

        self.assertTrue(HAS_PAM_SUPPORT)

    def test_shadow_support_unix(self):
        """
        Check that shadow files are supported on the Unix systems.
        """
        if os.name != 'posix':
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

    def test_unix(self):
        """
        Check Unix specific properties.
        """
        if self.os_name != 'posix':
            raise self.skipTest()

        avatar = SuperAvatar()

        self.assertEqual('root', avatar.name)
        self.assertTrue(avatar.use_impersonation)

    def test_windows(self):
        """
        Check Windows specific properties.
        """
        if self.os_name != 'nt':
            raise self.skipTest()

        avatar = SuperAvatar()

        self.assertFalse(avatar.use_impersonation)
