# Copyright (c) 2012 Adi Roiban.
# See LICENSE for details.
"""
Unit tests for simple the simplest avatar.
"""
from __future__ import with_statement
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from __future__ import unicode_literals

from chevah_compat.avatar import FilesystemAvatar
from chevah_compat.interfaces import IFileSystemAvatar
from chevah_compat.testing import ChevahTestCase, mk


class TestFilesystemAvatar(ChevahTestCase):

    def test_init_no_arguments(self):
        """
        An error is raised if initialized without arguments.
        """
        with self.assertRaises(TypeError):
            FilesystemAvatar()

    def test_init_home_folder_path_no_text(self):
        """
        An error is raised if initialized with a home_folder_path which is
        not text.
        """
        with self.assertRaises(RuntimeError):
            FilesystemAvatar(name='something', home_folder_path=b'data')

    def test_init_root_folder_path_no_text(self):
        """
        An error is raised if initialized with a root_folder_path which is
        not text.
        """
        with self.assertRaises(RuntimeError):
            FilesystemAvatar(
                name=u'something',
                home_folder_path=u'good-path',
                root_folder_path=b'data',
                )

    def test_init(self):
        """
        Avatar can be initialized with credentials and home_folder_path.
        """
        name = mk.getUniqueString()
        avatar = FilesystemAvatar(
            name=name, home_folder_path=mk.fs.temp_path)

        with self.assertRaises(NotImplementedError):
            avatar.use_impersonation

        self.assertEqual(mk.fs.temp_path, avatar.home_folder_path)
        self.assertEqual(name, avatar.name)
        self.assertIsNone(avatar.root_folder_path)
        self.assertEqual((), avatar.virtual_folders)

    def test_init_all_arguments(self):
        """
        Avatar can also be initialized with argument and the exported
        attributes are read only.
        """
        avatar = FilesystemAvatar(
            name=mk.getUniqueString(),
            home_folder_path=u'some-path',
            root_folder_path=u'other-path',
            token=u'the-token',
            virtual_folders=(
                (['base', 'segment'], '/some/real/path'),
                (['other', 'segment'], 'c:\\other\\path'),
                )
            )

        self.assertEqual(u'other-path', avatar.root_folder_path)
        with self.assertRaises(AttributeError):
            avatar.root_folder_path = 'something'

        self.assertEqual(u'the-token', avatar.token)
        with self.assertRaises(AttributeError):
            avatar.token = 'something'

        self.assertEqual(
            (
                (['base', 'segment'], '/some/real/path'),
                (['other', 'segment'], 'c:\\other\\path'),
                ),
            avatar.virtual_folders,
            )
        with self.assertRaises(AttributeError):
            avatar.virtual_folders = 'something'


class TestApplicationAvatar(ChevahTestCase):
    """
    Tests for ApplicationAvatar.
    """

    def test_init(self):
        """
        ApplicationAvatar can not be impersonated.
        """
        avatar = mk.makeFilesystemApplicationAvatar()

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
        avatar = mk.makeFilesystemOSAvatar()

        self.assertTrue(avatar.use_impersonation)
        self.assertProvides(IFileSystemAvatar, avatar)
