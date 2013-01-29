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
    )
from chevah.empirical import ChevahTestCase, factory
from chevah.compat.interfaces import IAvatarBase


class TestSystemUsers(ChevahTestCase):
    '''Test system users operations.'''

    def test_getHomeFolder_linux(self):
        """
        Check getHomeFolder on Linux.
        """
        if not sys.platform.startswith('linux'):
            raise self.skipTest()
        home_folder = system_users.getHomeFolder(
            username=factory.username)

        # For buidlslave, home folder is in srv.
        if factory.username == 'buildslave':
            self.assertEqual(u'/srv/' + factory.username, home_folder)
        else:
            self.assertEqual(u'/home/' + factory.username, home_folder)

    def test_getHomeFolder_nt(self):
        """
        Check getHomeFolder for Windows.
        """
        if os.name != 'nt' or not process_capabilities.get_home_folder:
            raise self.skipTest()

        home_folder = system_users.getHomeFolder(
            username=factory.username)

        self.assertNotEqual(
            -1,
            home_folder.lower().find(factory.username.lower()),
            '%s not in %s' % (factory.username, home_folder))

    def test_getHomeFolder_osx(self):
        """
        Check getHomeFolder for OSX.
        """
        if not sys.platform.startswith('darwin'):
            raise self.skipTest()

        home_folder = system_users.getHomeFolder(
            username=factory.username)

        self.assertEqual(u'/Users/' + factory.username, home_folder)

    def test_getHomeFolder_return_type(self):
        """
        getHomeFolder will always return an unicode path.
        """
        if not process_capabilities.get_home_folder:
            raise self.skipTest()

        home_folder = system_users.getHomeFolder(username=factory.username)

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

    def test_getSuperAvatar_application_avatar(self):
        """
        For application accounts, the super avatar will have the same
        home folder.

        On unix this is the root account.
        """
        name = factory.getUniqueString()
        home_folder_path = factory.getUniqueString()
        normal_avatar = factory.makeApplicationAvatar(
            name=name, home_folder_path=home_folder_path)

        super_avatar = system_users.getSuperAvatar(avatar=normal_avatar)

        self.assertEqual(home_folder_path, super_avatar.home_folder_path)
        if os.name == 'posix':
            self.assertFalse(super_avatar.lock_in_home_folder)
            self.assertEqual(u'root', super_avatar.name)
        else:
            self.assertTrue(super_avatar.lock_in_home_folder)
            self.assertEqual(name, super_avatar.name)

    def test_getSuperAvatar_os_avatar(self):
        """
        For os accounts, the super avatar will have the same
        home folder.

        On unix this is the root account.
        """
        name = factory.getUniqueString()
        home_folder_path = factory.getUniqueString()
        normal_avatar = factory.makeOSAvatar(
            name=name, home_folder_path=home_folder_path)

        super_avatar = system_users.getSuperAvatar(avatar=normal_avatar)

        self.assertFalse(super_avatar.lock_in_home_folder)
        self.assertEqual(home_folder_path, super_avatar.home_folder_path)
        if os.name == 'posix':
            self.assertEqual(u'root', super_avatar.name)
        else:
            self.assertEqual(name, super_avatar.name)


class TestDefaultAvatar(ChevahTestCase):
    """
    Tests for default avatar.
    """

    def test_init(self):
        """
        Default avatar is initialized without arguments.
        """
        avatar = DefaultAvatar()

        self.assertProvides(IAvatarBase, avatar)
