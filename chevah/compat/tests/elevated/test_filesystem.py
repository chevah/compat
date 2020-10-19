# Copyright (c) 2010 Adi Roiban.
# See LICENSE for details.
"""
Tests for portable filesystem access.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from __future__ import unicode_literals
from six import text_type
import errno
import os

from chevah.compat import (
    LocalFilesystem,
    SuperAvatar,
    )
from chevah.compat.interfaces import IFileAttributes
from chevah.compat.testing import (
    conditionals,
    mk,
    TEST_ACCOUNT_GROUP,
    TEST_ACCOUNT_GROUP_OTHER,
    TEST_ACCOUNT_USERNAME,
    TEST_ACCOUNT_USERNAME_OTHER,
    TestUser,
    TEST_USERS,
    )
from chevah.compat.exceptions import (
    CompatError,
    CompatException,
    )
from chevah.compat.testing.testcase import (
    FileSystemTestCase,
    OSAccountFileSystemTestCase,
    )
from chevah.compat.tests.mixin.filesystem import SymbolicLinksMixin


class TestPosixFilesystem(FileSystemTestCase):
    """
    Path independent, OS independent tests.
    """

    def test_getOwner_path_not_found(self):
        """
        It raises an exception when the requested path is not found.
        """
        with self.assertRaises(OSError):
            self.filesystem.getOwner([u'non-existent-segment'])

    @conditionals.onOSFamily('posix')
    def test_getOwner_ok_posix(self):
        """
        Returns the owner as string.
        """
        owner = self.filesystem.getOwner(self.filesystem.home_segments)
        self.assertEqual(self.avatar.name, owner)

    @conditionals.onCIName(
        [FileSystemTestCase.CI.LOCAL, FileSystemTestCase.CI.BUILDBOT])
    @conditionals.onOSFamily('nt')
    def test_getOwner_ok_nt(self):
        """
        Returns the owner as string.
        """
        owner = self.filesystem.getOwner(['c', 'Users'])
        self.assertEqual('Administrators', owner)

        # This is a folder.
        owner = self.filesystem.getOwner(['c', 'Users', 'chevah_ci_support'])
        self.assertEqual('chevah', owner)

        # This is a file
        owner = self.filesystem.getOwner(
            ['c', 'Users', 'chevah_ci_support', 'users_ci_support'])
        self.assertEqual('Users', owner)

    def test_setOwner_bad_segments(self):
        """
        An error is raised when trying to set owner for an bad path.
        """
        segments = [u'c', u'non-existent-segment']
        with self.assertRaises(CompatError) as context:

            self.filesystem.setOwner(segments, self.avatar.name)

        self.assertCompatError(1016, context.exception)

        self.assertContains(
            'Failed to set owner to', context.exception.message)

        if self.os_family == 'posix':
            self.assertContains(
                u'No such file or directory', context.exception.message)
        elif self.TEST_LANGUAGE == 'FR':
            self.assertContains(
                u'[2] Le fichier sp\xe9cifi\xe9 est introuvable.',
                context.exception.message,
                )
        else:
            self.assertContains(
                u'The system cannot find the file specified',
                context.exception.message,
                )

    def test_setOwner_bad_owner_file(self):
        """
        An error is raised when setting an unknown owner for a file.
        """
        file_name = mk.makeFilename()
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
        folder_name = mk.makeFilename()
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
        segments = [u'c', u'no-such-segments']

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
        file_name = mk.makeFilename()
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
        folder_name = mk.makeFilename()
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
            self.filesystem.hasGroup(
                [u'no-such-segment'], TEST_ACCOUNT_USERNAME)

        self.assertFalse(
            self.filesystem.hasGroup(
                self.filesystem.home_segments,
                TEST_ACCOUNT_GROUP_OTHER))

        # FIXME:928:
        # Update this test after the Windows issues is fixed.
        if self.os_family == 'posix':
            self.assertTrue(
                self.filesystem.hasGroup(
                    self.filesystem.home_segments,
                    TEST_ACCOUNT_GROUP))

    def test_setOwner_ok(self):
        """
        Take ownership of file/folder with valid owner ID.
        """
        file_name = mk.makeFilename()
        file_segments = self.filesystem.home_segments
        file_segments.append(file_name)
        file_object = self.filesystem.openFileForWriting(file_segments)
        file_object.close()

        root_avatar = SuperAvatar()
        root_avatar._home_folder_path = self.avatar.home_folder_path
        root_filesystem = LocalFilesystem(root_avatar)

        root_filesystem.setOwner(file_segments, TEST_ACCOUNT_USERNAME_OTHER)
        current_owner = self.filesystem.getOwner(file_segments)

        self.assertEqual(TEST_ACCOUNT_USERNAME_OTHER, current_owner)

        folder_name = mk.makeFilename()
        folder_segments = self.filesystem.home_segments
        folder_segments.append(folder_name)
        self.filesystem.createFolder(folder_segments)

        root_filesystem.setOwner(folder_segments, TEST_ACCOUNT_USERNAME_OTHER)
        current_owner = self.filesystem.getOwner(folder_segments)

        self.assertEqual(TEST_ACCOUNT_USERNAME_OTHER, current_owner)

    # For now we don't have the API to set permissions on Windows so we
    # don't have a test here.
    @conditionals.onOSFamily('posix')
    def test_iterateFolderContent_no_permission(self):
        """
        It will raise an error if user has no permissions to list folder.
        """
        avatar = mk.FilesystemOsAvatar(
            user=TEST_USERS['normal'],
            home_folder_path=mk.fs.temp_path,
            )
        user_fs = mk.makeLocalTestFilesystem(avatar)
        user_fs.folder(user_fs.temp_segments, cleanup=self.addCleanup)

        user_fs.setAttributes(user_fs.temp_segments, {'mode': 0o700})

        error = self.assertRaises(
            OSError,
            mk.fs.iterateFolderContent, user_fs.temp_segments,
            )
        self.assertEqual(errno.EACCES, error.errno)

    def test_iterateFolderContent_non_empty(self):
        """
        After the iterator is created the process context is returned to
        the normal user.
        """
        avatar = mk.FilesystemOsAvatar(
            user=TEST_USERS['normal'],
            home_folder_path=mk.fs.temp_path,
            )
        user_fs = mk.makeLocalTestFilesystem(avatar)
        user_fs.folder(user_fs.temp_segments, cleanup=self.addCleanup)

        base_segments = user_fs.temp_segments
        user_fs.setAttributes(base_segments, {'mode': 0o700})

        file_name = mk.makeFilename(prefix='file-')
        folder_name = mk.makeFilename(prefix='folder-')

        file_segments = base_segments + [file_name]
        folder_segments = base_segments + [folder_name]

        user_fs.createFile(file_segments, content=b'12345678901')
        user_fs.createFolder(folder_segments)

        content = user_fs.iterateFolderContent(base_segments)

        result = list(content)
        self.assertEqual(2, len(result))
        self.assertProvides(IFileAttributes, result[0])
        self.assertProvides(IFileAttributes, result[1])
        result = {r.name: r for r in result}
        folder_attributes = result[folder_name]
        self.assertTrue(folder_attributes.is_folder)
        self.assertFalse(folder_attributes.is_file)
        self.assertFalse(folder_attributes.is_link)

        file_attributes = result[file_name]
        self.assertFalse(file_attributes.is_folder)
        self.assertTrue(file_attributes.is_file)
        self.assertFalse(file_attributes.is_link)
        self.assertEqual(11, file_attributes.size)
        self.assertAlmostEqual(self.now(), file_attributes.modified, delta=5)
        self.assertIsInstance(text_type, file_attributes.name)


@conditionals.onOSFamily('posix')
class TestUnixFilesystem(FileSystemTestCase):
    """
    Path independent Unix tests.
    """

    def test_temp_segments_location(self):
        """
        On Unix the normal temporary folder is used.
        """
        # We check that the elevated filesystem start with the same
        # path as normal filesystem
        self.assertEqual([u'tmp'], self.filesystem.temp_segments)

    def test_addGroup_denied_group_file(self):
        """
        On Unix we can not set the group for a file that we own to a group
        to which we are not members, with the exception of HPUX.
        """
        file_name = mk.makeFilename()
        file_segments = self.filesystem.home_segments
        file_segments.append(file_name)
        file_object = self.filesystem.openFileForWriting(file_segments)
        file_object.close()

        def act():
            self.filesystem.addGroup(file_segments, TEST_ACCOUNT_GROUP_OTHER)

        if self.os_name == 'hpux':
            act()
            self.assertTrue(self.filesystem.hasGroup(
                file_segments, TEST_ACCOUNT_GROUP_OTHER))
        else:
            with self.assertRaises(CompatError) as context:
                act()
            self.assertEqual(1017, context.exception.event_id)
            self.assertFalse(self.filesystem.hasGroup(
                file_segments, TEST_ACCOUNT_GROUP_OTHER))

    def test_addGroup_denied_group_folder(self):
        """
        On Unix we can not set the group for a folder that we own to a group
        to which we are not members, with the exception of HPUX.
        """
        folder_name = mk.makeFilename()
        folder_segments = self.filesystem.home_segments
        folder_segments.append(folder_name)
        self.filesystem.createFolder(folder_segments)

        def act():
            self.filesystem.addGroup(folder_segments, TEST_ACCOUNT_GROUP_OTHER)

        if self.os_name == 'hpux':
            act()
            self.assertTrue(self.filesystem.hasGroup(
                folder_segments, TEST_ACCOUNT_GROUP_OTHER))
        else:
            with self.assertRaises(CompatError) as context:
                act()
            self.assertEqual(1017, context.exception.event_id)
            self.assertFalse(self.filesystem.hasGroup(
                folder_segments, TEST_ACCOUNT_GROUP_OTHER))

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


class TestNTFilesystem(FileSystemTestCase):
    """
    Path independent NT tests.
    """

    @classmethod
    @conditionals.onOSFamily('nt')
    def setUpClass(cls):
        super(TestNTFilesystem, cls).setUpClass()

    def test_temp_segments_location(self):
        """
        For elevated accounts temporary folder is not located insider
        user default temp folder but in the hardcoded c:\temp folder..
        """
        self.assertEqual([u'c', u'temp'], self.filesystem.temp_segments)

    def test_removeGroup_good(self):
        """
        Check group removal for a file/folder.
        """
        self.test_segments = self.filesystem.home_segments
        self.test_segments.append(mk.makeFilename())
        self.filesystem.createFolder(self.test_segments)

        self.assertFalse(
            self.filesystem.hasGroup(
                self.test_segments, TEST_ACCOUNT_GROUP_OTHER))

        self.filesystem.addGroup(
            self.test_segments, TEST_ACCOUNT_GROUP_OTHER)

        self.assertTrue(
            self.filesystem.hasGroup(
                self.test_segments, TEST_ACCOUNT_GROUP_OTHER))

        self.filesystem.removeGroup(
            self.test_segments, TEST_ACCOUNT_GROUP_OTHER)

        self.assertFalse(
            self.filesystem.hasGroup(
                self.test_segments, TEST_ACCOUNT_GROUP_OTHER))

        # Try to remove it again.
        self.filesystem.removeGroup(
            self.test_segments, TEST_ACCOUNT_GROUP_OTHER)

        with self.assertRaises(OSError):
            self.filesystem.removeGroup(
                [u'no-such-segments'], TEST_ACCOUNT_GROUP_OTHER)

        with self.assertRaises(CompatError) as context:
            self.filesystem.removeGroup(
                self.test_segments, u'no-such-group')
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

    def test_makeLink_missing_privilege(self):
        """
        It will raise an error if user does not have sufficient privileges
        for creating symbolic links.
        """
        link_segments = self.filesystem.home_segments
        link_segments.append(mk.string())

        with self.assertRaises(OSError) as context:
            self.filesystem.makeLink(
                target_segments=['z', 'no-such', 'target'],
                link_segments=link_segments,
                )

        self.assertContains(
            u'Process does not have', context.exception.strerror)


class TestSymbolicLinks(OSAccountFileSystemTestCase, SymbolicLinksMixin):
    """
    Unit tests for `makeLink` when impersonating a user which has permission
    to create symbolic links.

    User requires SE_CREATE_SYMBOLIC_LINK privilege on Windows OSes
    in order to be able to create symbolic links. We are using a custom
    user for which we make sure the right is present for these tests.
    """

    try:
        import win32security
        rights = (win32security.SE_CREATE_SYMBOLIC_LINK_NAME,)
    except Exception:
        rights = ()

    CREATE_TEST_USER = TestUser(
        name=mk.string(),
        password=mk.string(),
        home_group=TEST_ACCOUNT_GROUP,
        posix_uid=mk.posixID(),
        windows_required_rights=rights,
        )
