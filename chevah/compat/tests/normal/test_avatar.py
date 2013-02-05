# Copyright (c) 2012 Adi Roiban.
# See LICENSE for details.
'''Unit tests for simple the simplest avatar.'''
from __future__ import with_statement

from chevah.compat.avatar import FilesystemAvatar
from chevah.compat.interfaces import IFileSystemAvatar
from chevah.compat.testing import ChevahTestCase, manufacture


class TestAvatarBase(ChevahTestCase):

    def test_init_no_argumets(self):
        """
        An error is raised if initialized without arguments.
        """
        with self.assertRaises(TypeError):
            FilesystemAvatar()

    def test_init(self):
        """
        Avatar can be initialized with credentials and home_folder_path.
        """
        name = manufacture.getUniqueString()
        avatar = FilesystemAvatar(
            name=name, home_folder_path=manufacture.fs.temp_path)

        with self.assertRaises(NotImplementedError):
            avatar.use_impersonation

        self.assertEqual(manufacture.fs.temp_path, avatar.home_folder_path)
        self.assertEqual(name, avatar.name)
        self.assertIsNone(avatar.root_folder_path)

    def test_init_all_arguemts(self):
        """
        Avatar can also be intialized with a root path.
        """
        avatar = FilesystemAvatar(
            name=manufacture.getUniqueString(),
            home_folder_path=u'some-path',
            root_folder_path=u'other-path',
            token=u'the-token',
            )

        self.assertEqual(u'other-path', avatar.root_folder_path)
        self.assertEqual(u'the-token', avatar.token)

    def test_getCopy(self):
        """
        Test copying an avatar.
        """
        initial_avatar = manufacture.makeFilesystemApplicationAvatar()
        copy_avatar = initial_avatar.getCopy()

        self.assertNotEqual(id(initial_avatar), id(copy_avatar))
        self.assertEqual(
            initial_avatar._home_folder_path, copy_avatar._home_folder_path)


class TestApplicationAvatar(ChevahTestCase):
    """
    Tests for ApplicationAvatar.
    """

    def test_init(self):
        """
        ApplicationAvatar can not be impersonated.
        """
        avatar = manufacture.makeFilesystemApplicationAvatar()

        self.assertFalse(avatar.use_impersonation)
        self.assertProvides(IFileSystemAvatar, avatar)


class TestOSAvatar(ChevahTestCase):
    """
    Tests for OSAvatar.
    """

    def test_init(self):
        """
        OSAvatar is impersonated.
        """
        avatar = manufacture.makeFilesystemOSAvatar()

        self.assertTrue(avatar.use_impersonation)
        self.assertProvides(IFileSystemAvatar, avatar)
