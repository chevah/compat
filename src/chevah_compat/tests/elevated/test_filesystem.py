# Copyright (c) 2010 Adi Roiban.
# See LICENSE for details.
"""
Tests for portable filesystem access.
"""

import errno
import os

from chevah_compat import (
    DefaultAvatar,
    LocalFilesystem,
    SuperAvatar,
    system_users,
)
from chevah_compat.exceptions import CompatError, CompatException
from chevah_compat.interfaces import IFileAttributes
from chevah_compat.testing import (
    TEST_ACCOUNT_GROUP,
    TEST_ACCOUNT_GROUP_OTHER,
    TEST_ACCOUNT_USERNAME,
    TEST_ACCOUNT_USERNAME_OTHER,
    TEST_USERS,
    TestUser,
    conditionals,
    mk,
)
from chevah_compat.testing.testcase import (
    FileSystemTestCase,
    OSAccountFileSystemTestCase,
)
from chevah_compat.tests.mixin.filesystem import SymbolicLinksMixin


class TestPosixFilesystem(FileSystemTestCase):
    """
    Path independent, OS independent tests.
    """

    def test_getOwner_path_not_found(self):
        """
        It raises an exception when the requested path is not found.
        """
        with self.assertRaises(OSError):
            self.filesystem.getOwner(['non-existent-segment'])

    @conditionals.onOSFamily('posix')
    def test_getOwner_ok_posix(self):
        """
        Returns the owner as string.
        """
        owner = self.filesystem.getOwner(self.filesystem.home_segments)
        self.assertEqual(self.avatar.name, owner)

    def test_setOwner_bad_segments(self):
        """
        An error is raised when trying to set owner for an bad path.
        """
        segments = ['c', 'non-existent-segment']
        with self.assertRaises(CompatError) as context:
            self.filesystem.setOwner(segments, self.avatar.name)

        self.assertCompatError(1016, context.exception)

        self.assertContains('Failed to set owner to', context.exception.message)

        if self.os_family == 'posix':
            self.assertContains(
                'No such file or directory',
                context.exception.message,
            )
        elif self.TEST_LANGUAGE == 'FR':
            self.assertContains(
                '[2] Le fichier sp\xe9cifi\xe9 est introuvable.',
                context.exception.message,
            )
        else:
            self.assertContains(
                'The system cannot find the file specified',
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
            self.filesystem.setOwner(file_segments, 'non-existent-owner')
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
            self.filesystem.setOwner(folder_segments, 'non-existent-owner')
        self.assertEqual(1016, context.exception.event_id)

    def test_setGroup(self):
        """
        setGroup is not yet supported.
        """
        segments = ['dont-care']
        with self.assertRaises(AssertionError):
            self.filesystem.setGroup(segments, TEST_ACCOUNT_USERNAME_OTHER)

    def test_addGroup_unknown_segments(self):
        """
        Changing the groups for an unknown file will raise an
        CompatError.
        """
        segments = ['c', 'no-such-segments']

        with self.assertRaises(CompatError) as context:
            self.filesystem.addGroup(segments, TEST_ACCOUNT_USERNAME_OTHER)

        self.assertEqual(1017, context.exception.event_id)

    def test_addGroup_unknown_group(self):
        """
        An error is raised when adding an unknown group.
        """
        with self.assertRaises(CompatError) as context:
            self.filesystem.addGroup(
                self.filesystem.home_segments,
                'non-existent-group',
            )
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
            self.filesystem.hasGroup(file_segments, TEST_ACCOUNT_GROUP_OTHER),
        )
        root_filesystem.addGroup(file_segments, TEST_ACCOUNT_GROUP_OTHER)
        self.assertTrue(
            self.filesystem.hasGroup(file_segments, TEST_ACCOUNT_GROUP_OTHER),
        )

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
            self.filesystem.hasGroup(folder_segments, TEST_ACCOUNT_GROUP_OTHER),
        )
        root_filesystem.addGroup(folder_segments, TEST_ACCOUNT_GROUP_OTHER)
        self.assertTrue(
            self.filesystem.hasGroup(folder_segments, TEST_ACCOUNT_GROUP_OTHER),
        )

    def test_hasGroup(self):
        """
        Check hasGroup.
        """
        with self.assertRaises(OSError):
            self.filesystem.hasGroup(['no-such-segment'], TEST_ACCOUNT_USERNAME)

        self.assertFalse(
            self.filesystem.hasGroup(
                self.filesystem.home_segments,
                TEST_ACCOUNT_GROUP_OTHER,
            ),
        )

        # TODO: Update this test after the Windows issues is fixed.
        # 928
        if self.os_family == 'posix':
            self.assertTrue(
                self.filesystem.hasGroup(
                    self.filesystem.home_segments,
                    TEST_ACCOUNT_GROUP,
                ),
            )

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

        try:
            user_fs.setAttributes(user_fs.temp_segments, {'mode': 0o000})

            error = self.assertRaises(
                OSError,
                user_fs.iterateFolderContent,
                user_fs.temp_segments,
            )
        finally:
            # Make sure we revert the permissions so that we can cleanup.
            user_fs.setAttributes(user_fs.temp_segments, {'mode': 0o700})

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

        user_fs.createFile(file_segments, content='12345678901')
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
        self.assertIsInstance(str, file_attributes.name)

    def test_impersonate_nested(self):
        """
        The user impersonation works for nested calls.

        Once all nested calls exit, the OS process is reset to the previous
        user.
        """
        user = TEST_USERS['normal']
        avatar = mk.FilesystemOsAvatar(
            user=user,
            home_folder_path=mk.fs.temp_path,
        )

        initial_user = system_users.getCurrentUserName()
        filesystem = LocalFilesystem(avatar=avatar)
        with filesystem._impersonateUser():
            self.assertEqual(user.name, system_users.getCurrentUserName())
            with filesystem._impersonateUser():
                self.assertEqual(user.name, system_users.getCurrentUserName())

            # On Windows, nested calls are not supported.
            # I don't know how to implement nested support in Windows.
            if self.os_family != 'nt':
                # Even though we have exited the context,
                # we still have the impersonated use as this is a nested call.
                self.assertEqual(user.name, system_users.getCurrentUserName())

        # Once we exit all context, the previous context is set.
        self.assertEqual(initial_user, system_users.getCurrentUserName())

    def test_nested_no_reset(self):
        """
        The user impersonation is not reset when nesting specific user
        filesystem with the default filesystem
        """
        user = TEST_USERS['normal']
        avatar = mk.FilesystemOsAvatar(
            user=user,
            home_folder_path=mk.fs.temp_path,
        )
        initial_user = system_users.getCurrentUserName()
        filesystem = LocalFilesystem(avatar=avatar)
        default_filesystem = LocalFilesystem(avatar=DefaultAvatar())

        with default_filesystem._impersonateUser():
            # Previous user is kept
            self.assertEqual(initial_user, system_users.getCurrentUserName())

        with filesystem._impersonateUser():
            self.assertEqual(user.name, system_users.getCurrentUserName())

            with default_filesystem._impersonateUser():
                # Still uses the nested user.
                self.assertEqual(user.name, system_users.getCurrentUserName())

        # Once we exit all context, the previous context is set.
        self.assertEqual(initial_user, system_users.getCurrentUserName())

    def test_nested_with_reset(self):
        """
        The user impersonation can reset when nesting a specific user
        filesystem with the default filesystem.
        """
        user = TEST_USERS['normal']
        avatar = mk.FilesystemOsAvatar(
            user=user,
            home_folder_path=mk.fs.temp_path,
        )
        initial_user = system_users.getCurrentUserName()
        filesystem = LocalFilesystem(avatar=avatar)

        default_filesystem = LocalFilesystem(avatar=DefaultAvatar())

        initial_context = DefaultAvatar._NoOpContext
        DefaultAvatar.setupResetEffectivePrivileges()

        def revert_avatar(initial_context):
            DefaultAvatar._NoOpContext = initial_context

        self.addCleanup(revert_avatar, initial_context)

        with default_filesystem._impersonateUser():
            # Previous user is kept
            self.assertEqual(initial_user, system_users.getCurrentUserName())

        with filesystem._impersonateUser():
            self.assertEqual(user.name, system_users.getCurrentUserName())

            with default_filesystem._impersonateUser():
                # Reset the user.
                self.assertEqual(
                    initial_user, system_users.getCurrentUserName()
                )

            # Further call to the specific impersonated filesystem will work
            # and will trigger an impersonation.
            with filesystem._impersonateUser():
                self.assertEqual(user.name, system_users.getCurrentUserName())

        # Once we exit all context, the previous context is set.
        self.assertEqual(initial_user, system_users.getCurrentUserName())


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
        self.assertEqual(['tmp'], self.filesystem.temp_segments)

    def test_addGroup_denied_group_file(self):
        """
        On Unix we can not set the group for a file that we own to a group
        to which we are not members.
        """
        file_name = mk.makeFilename()
        file_segments = self.filesystem.home_segments
        file_segments.append(file_name)
        file_object = self.filesystem.openFileForWriting(file_segments)
        file_object.close()

        def act():
            self.filesystem.addGroup(file_segments, TEST_ACCOUNT_GROUP_OTHER)

        with self.assertRaises(CompatError) as context:
            act()
        self.assertEqual(1017, context.exception.event_id)
        self.assertFalse(
            self.filesystem.hasGroup(
                file_segments,
                TEST_ACCOUNT_GROUP_OTHER,
            ),
        )

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

        with self.assertRaises(CompatError) as context:
            act()
        self.assertEqual(1017, context.exception.event_id)
        self.assertFalse(
            self.filesystem.hasGroup(
                folder_segments,
                TEST_ACCOUNT_GROUP_OTHER,
            ),
        )

    def test_removeGroup(self):
        """
        Check removeGroup.
        """
        # Right now, on Unix it does nothing.
        self.filesystem.removeGroup(
            self.filesystem.home_segments,
            TEST_ACCOUNT_GROUP_OTHER,
        )

        self.filesystem.removeGroup(
            self.filesystem.home_segments,
            'no-such-group',
        )


class TestNTFilesystem(FileSystemTestCase):
    """
    Path independent NT tests.
    """

    @classmethod
    @conditionals.onOSFamily('nt')
    def setUpClass(cls):
        super().setUpClass()

    def test_temp_segments_location(self):
        """
        For elevated accounts temporary folder is not located insider
        user default temp folder but in the hardcoded c:\temp folder..
        """
        self.assertEqual(['c', 'temp'], self.filesystem.temp_segments)

    def test_removeGroup_good(self):
        """
        Check group removal for a file/folder.
        """
        self.test_segments = self.filesystem.home_segments
        self.test_segments.append(mk.makeFilename())
        self.filesystem.createFolder(self.test_segments)

        self.assertFalse(
            self.filesystem.hasGroup(
                self.test_segments,
                TEST_ACCOUNT_GROUP_OTHER,
            ),
        )

        self.filesystem.addGroup(self.test_segments, TEST_ACCOUNT_GROUP_OTHER)

        self.assertTrue(
            self.filesystem.hasGroup(
                self.test_segments,
                TEST_ACCOUNT_GROUP_OTHER,
            ),
        )

        self.filesystem.removeGroup(
            self.test_segments,
            TEST_ACCOUNT_GROUP_OTHER,
        )

        self.assertFalse(
            self.filesystem.hasGroup(
                self.test_segments,
                TEST_ACCOUNT_GROUP_OTHER,
            ),
        )

        # Try to remove it again.
        self.filesystem.removeGroup(
            self.test_segments,
            TEST_ACCOUNT_GROUP_OTHER,
        )

        with self.assertRaises(OSError):
            self.filesystem.removeGroup(
                ['no-such-segments'],
                TEST_ACCOUNT_GROUP_OTHER,
            )

        with self.assertRaises(CompatError) as context:
            self.filesystem.removeGroup(self.test_segments, 'no-such-group')
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

        self.assertContains('Process does not have', context.exception.strerror)


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
