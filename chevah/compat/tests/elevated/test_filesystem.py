# Copyright (c) 2010 Adi Roiban.
# See LICENSE for details.
'''Tests for portable filesystem access.'''

from __future__ import with_statement
import os

from chevah.compat import (
    LocalFilesystem,
    process_capabilities,
    system_users,
    SuperAvatar,
    )
from chevah.compat.testing import ChevahTestCase, manufacture
from chevah.empirical.constants import (
    TEST_ACCOUNT_GROUP,
    TEST_ACCOUNT_GROUP_OTHER,
    TEST_ACCOUNT_USERNAME,
    TEST_ACCOUNT_PASSWORD,
    TEST_ACCOUNT_USERNAME_OTHER,
    )
from chevah.empirical.filesystem import LocalTestFilesystem
from chevah.compat.exceptions import CompatError, CompatException


class TestPosixFilesystem(ChevahTestCase):
    '''Tests for path independent, OS independent tests.'''

    @classmethod
    def setUpClass(cls):
        # FIXME:924:
        # Disabled when we can not find the home folder path.
        if not process_capabilities.get_home_folder:
            raise cls.skipTest()

        user = TEST_ACCOUNT_USERNAME
        password = TEST_ACCOUNT_PASSWORD
        token = manufacture.makeToken(username=user, password=password)
        home_folder_path = system_users.getHomeFolder(
            username=user, token=token)
        cls.avatar = manufacture.makeFilesystemOSAvatar(
            name=user,
            home_folder_path=home_folder_path,
            token=token,
            )
        cls.avatar._root_folder_path = None
        cls.filesystem = LocalFilesystem(avatar=cls.avatar)

    def setUp(self):
        super(TestPosixFilesystem, self).setUp()
        test_filesystem = LocalTestFilesystem(avatar=self.avatar)
        test_filesystem.cleanHomeFolder()

    def test_getOwner(self):
        """
        Check getOwner for good and bad path.
        """
        segments = [u'non-existent-segment']
        with self.assertRaises(OSError):
            self.filesystem.getOwner(segments)
        owner = self.filesystem.getOwner(self.filesystem.home_segments)
        # FIXME:928:
        # Unify this test after the Windows issue is fixed.
        if self.os_name == 'posix':
            self.assertEqual(self.avatar.name, owner)
        else:
            self.assertEqual(u'Administrators', owner)

    def test_setOwner_bad_segments(self):
        """
        An error is raised when trying to set owner for an bad path.
        """
        segments = [u'non-existent-segment']
        with self.assertRaises(OSError):
            self.filesystem.setOwner(segments, self.avatar.name)

    def test_setOwner_bad_owner_file(self):
        """
        An error is raised when setting an unknown owner for a file.
        """
        file_name = manufacture.makeFilename()
        file_segments = self.filesystem.home_segments
        file_segments.append(file_name)
        file_object = self.filesystem.openFileForWriting(file_segments)
        file_object.close()

        with self.assertRaises(CompatError) as context:
            self.filesystem.setOwner(
                file_segments,
                u'non-existent-owner')
        self.assertEqual(1016, context.exception.event_id)

    def test_setOwner_bad_owner_folder(self):
        """
        An error is raised when setting an unknown owner for a folder.
        """
        folder_name = manufacture.makeFilename()
        folder_segments = self.filesystem.home_segments
        folder_segments.append(folder_name)
        self.filesystem.createFolder(folder_segments)

        # Check on folder.
        with self.assertRaises(CompatError) as context:
            self.filesystem.setOwner(
                folder_segments,
                u'non-existent-owner')
        self.assertEqual(1016, context.exception.event_id)

    def test_setGroup(self):
        """
        setGroup is not yet supported.
        """
        segments = [u'dont-care']
        with self.assertRaises(AssertionError):
            self.filesystem.setGroup(segments, TEST_ACCOUNT_USERNAME_OTHER)

    def test_addGroup_unknown_segments(self):
        """
        Changing the groups for an unknown file will raise an
        CompatError.
        """
        segments = [u'no-such-segments']

        with self.assertRaises(CompatError) as context:
            self.filesystem.addGroup(segments, TEST_ACCOUNT_USERNAME_OTHER)

        self.assertEqual(1017, context.exception.event_id)

    def test_addGroup_unknown_group(self):
        """
        An error is raised when adding an unknown group.
        """
        with self.assertRaises(CompatError) as context:
            self.filesystem.addGroup(
                self.filesystem.home_segments, u'non-existent-group')
        self.assertEqual(1017, context.exception.event_id)

    def test_addGroup_ok_group_file(self):
        """
        Check successful adding a group for a file.
        """
        file_name = manufacture.makeFilename()
        file_segments = self.filesystem.home_segments
        file_segments.append(file_name)
        file_object = self.filesystem.openFileForWriting(file_segments)
        file_object.close()

        if os.name == 'posix':
            root_avatar = SuperAvatar()
            root_avatar._home_folder_path = self.avatar.home_folder_path
            root_avatar._root_folder_path = self.avatar.root_folder_path
            root_filesystem = LocalFilesystem(avatar=root_avatar)
        else:
            root_filesystem = self.filesystem

        self.assertFalse(
            self.filesystem.hasGroup(
                file_segments, TEST_ACCOUNT_GROUP_OTHER))
        root_filesystem.addGroup(
            file_segments, TEST_ACCOUNT_GROUP_OTHER)
        self.assertTrue(
            self.filesystem.hasGroup(
                file_segments, TEST_ACCOUNT_GROUP_OTHER))

    def test_addGroup_ok_group_folder(self):
        """
        Check successful adding a group for a folder.
        """
        folder_name = manufacture.makeFilename()
        folder_segments = self.filesystem.home_segments
        folder_segments.append(folder_name)
        self.filesystem.createFolder(folder_segments)

        if os.name == 'posix':
            root_avatar = SuperAvatar()
            root_avatar._home_folder_path = self.avatar.home_folder_path
            root_avatar._root_folder_path = self.avatar.root_folder_path
            root_filesystem = LocalFilesystem(avatar=root_avatar)
        else:
            root_filesystem = self.filesystem

        self.assertFalse(
            self.filesystem.hasGroup(
                folder_segments, TEST_ACCOUNT_GROUP_OTHER))
        root_filesystem.addGroup(
            folder_segments, TEST_ACCOUNT_GROUP_OTHER)
        self.assertTrue(
            self.filesystem.hasGroup(
                folder_segments, TEST_ACCOUNT_GROUP_OTHER))

    def test_hasGroup(self):
        """
        Check hasGroup.
        """
        with self.assertRaises(OSError):
            self.filesystem.hasGroup([u'no-such-segment'],
            TEST_ACCOUNT_USERNAME)

        self.assertFalse(
            self.filesystem.hasGroup(
                self.filesystem.home_segments,
                TEST_ACCOUNT_GROUP_OTHER))

        # FIXME:928:
        # Update this test after the Windows issues is fixed.
        if self.os_name == 'posix':
            self.assertTrue(
                self.filesystem.hasGroup(
                    self.filesystem.home_segments,
                    TEST_ACCOUNT_GROUP))

    def test_setOwner_ok(self):
        """
        Take ownership of file/folder with valid owner ID.
        """
        file_name = manufacture.makeFilename()
        file_segments = self.filesystem.home_segments
        file_segments.append(file_name)
        file_object = self.filesystem.openFileForWriting(file_segments)
        file_object.close()
        folder_name = manufacture.makeFilename()
        folder_segments = self.filesystem.home_segments
        folder_segments.append(folder_name)
        self.filesystem.createFolder(folder_segments)

        root_avatar = SuperAvatar()
        root_avatar._home_folder_path = self.avatar.home_folder_path
        root_filesystem = LocalFilesystem(root_avatar)

        root_filesystem.setOwner(
            file_segments,
            TEST_ACCOUNT_USERNAME_OTHER)
        new_owner = self.filesystem.getOwner(file_segments)

        self.assertEqual(TEST_ACCOUNT_USERNAME_OTHER, new_owner)


class TestUnixFilesystem(ChevahTestCase):
    '''Tests for path independent Unix tests.'''

    @classmethod
    def setUpClass(cls):
        if os.name != 'posix':
            raise cls.skipTest()

        user = TEST_ACCOUNT_USERNAME
        password = TEST_ACCOUNT_PASSWORD
        token = manufacture.makeToken(username=user, password=password)
        home_folder_path = system_users.getHomeFolder(username=user)
        cls.avatar = manufacture.makeFilesystemOSAvatar(
            name=user,
            home_folder_path=home_folder_path,
            token=token,
            )
        cls.avatar._root_folder_path = None
        cls.filesystem = LocalFilesystem(avatar=cls.avatar)

    def setUp(self):
        super(TestUnixFilesystem, self).setUp()
        test_filesystem = LocalTestFilesystem(avatar=self.avatar)
        test_filesystem.cleanHomeFolder()

    def test_addGroup_denied_group_file(self):
        """
        On Unix we can not set the group for a file that we own.

        Stupid Unix!
        """
        file_name = manufacture.makeFilename()
        file_segments = self.filesystem.home_segments
        file_segments.append(file_name)
        file_object = self.filesystem.openFileForWriting(file_segments)
        file_object.close()
        with self.assertRaises(CompatError) as context:
            self.filesystem.addGroup(
                file_segments, TEST_ACCOUNT_GROUP_OTHER)
        self.assertEqual(1017, context.exception.event_id)

    def test_addGroup_denied_group_folder(self):
        """
        On Unix we can not set the group for a folder that we own.

        Stupid Unix!
        """
        folder_name = manufacture.makeFilename()
        folder_segments = self.filesystem.home_segments
        folder_segments.append(folder_name)
        self.filesystem.createFolder(folder_segments)
        with self.assertRaises(CompatError) as context:
            self.filesystem.addGroup(
                folder_segments, TEST_ACCOUNT_GROUP_OTHER)
        self.assertEqual(1017, context.exception.event_id)

    def test_removeGroup(self):
        """
        Check removeGroup.
        """
        # Right now, on Unix it does nothing.
        self.filesystem.removeGroup(
            self.filesystem.home_segments,
            TEST_ACCOUNT_GROUP_OTHER)

        self.filesystem.removeGroup(
            self.filesystem.home_segments,
            u'no-such-group')


class TestNTFilesystem(ChevahTestCase):
    '''
    Tests for path independent NT tests.
    '''

    @classmethod
    def setUpClass(cls):
        if os.name != 'nt':
            raise cls.skipTest()

        # FIXME:924:
        # Disabled when we can not find the home folder path.
        if not process_capabilities.get_home_folder:
            raise cls.skipTest()

        user = TEST_ACCOUNT_USERNAME
        password = TEST_ACCOUNT_PASSWORD
        token = manufacture.makeToken(username=user, password=password)
        home_folder_path = system_users.getHomeFolder(
            username=user, token=token)
        cls.avatar = manufacture.makeFilesystemOSAvatar(
            name=user,
            home_folder_path=home_folder_path,
            token=token,
            )
        cls.filesystem = LocalFilesystem(avatar=cls.avatar)

    def setUp(self):
        super(TestNTFilesystem, self).setUp()
        test_filesystem = LocalTestFilesystem(avatar=self.avatar)
        test_filesystem.cleanHomeFolder()

    def test_removeGroup_good(self):
        """
        Check group removal for a file/folder.
        """
        folder_name = manufacture.makeFilename()
        folder_segments = self.filesystem.home_segments
        folder_segments.append(folder_name)
        self.filesystem.createFolder(folder_segments)

        self.assertFalse(
            self.filesystem.hasGroup(
                folder_segments, TEST_ACCOUNT_GROUP_OTHER))

        self.filesystem.addGroup(
            folder_segments, TEST_ACCOUNT_GROUP_OTHER)

        self.assertTrue(
            self.filesystem.hasGroup(
                folder_segments, TEST_ACCOUNT_GROUP_OTHER))

        self.filesystem.removeGroup(
            folder_segments, TEST_ACCOUNT_GROUP_OTHER)

        self.assertFalse(
            self.filesystem.hasGroup(
                folder_segments, TEST_ACCOUNT_GROUP_OTHER))

        # Try to remove it again.
        self.filesystem.removeGroup(
            folder_segments, TEST_ACCOUNT_GROUP_OTHER)

        with self.assertRaises(OSError):
            self.filesystem.removeGroup(
                [u'no-such-segments'], TEST_ACCOUNT_GROUP_OTHER)

        with self.assertRaises(CompatError) as context:
            self.filesystem.removeGroup(
                folder_segments, u'no-such-group')
        self.assertEqual(1013, context.exception.event_id)

    def test_setOwner_CompatError(self):
        """
        setOwner will convert CompatExceptions into CompatError.
        """
        def set_owner(segments, owner):
            raise CompatException(message='test-message')

        with self.assertRaises(CompatError) as context:
            with self.Patch.object(self.filesystem, '_setOwner', set_owner):
                self.filesystem.setOwner('something', 'don-t care')

        self.assertEqual(1016, context.exception.event_id)
        self.assertContains('test-message', context.exception.message)
