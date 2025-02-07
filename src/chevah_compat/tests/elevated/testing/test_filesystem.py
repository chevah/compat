# Copyright (c) 2012 Adi Roiban.
# See LICENSE for details.
"""
Tests for testing filesystem
"""

from chevah_compat import DefaultAvatar, system_users
from chevah_compat.testing import ChevahTestCase, conditionals, mk
from chevah_compat.testing import mk as compat_mk
from chevah_compat.testing.filesystem import LocalTestFilesystem


class TestElevatedLocalTestFilesystem(ChevahTestCase):
    """
    Test for LocalTestFilesystem using different account.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = compat_mk.getTestUser('normal')
        home_folder_path = system_users.getHomeFolder(
            username=cls.user.name,
            token=cls.user.token,
        )
        cls.avatar = compat_mk.makeFilesystemOSAvatar(
            name=cls.user.name,
            home_folder_path=home_folder_path,
            token=cls.user.token,
        )

    def checkTemporaryFolderInitialization(self, filesystem):
        """
        Check that temporary folder can be initialized.
        """
        # Temporary folder can be initialized and is owned by the dedicate
        # user.
        try:
            filesystem.setUpTemporaryFolder()
            owner = filesystem.getOwner(filesystem.temp_segments)

            self.assertEqual(self.user.name, owner)
        finally:
            filesystem.tearDownTemporaryFolder()

    def test_impersonate_nested(self):
        """
        The user impersonation works for nested calls.

        Once all nested calls exit, the OS process is reset to the previous
        user.
        """
        initial_user = system_users.getCurrentUserName()
        filesystem = LocalTestFilesystem(avatar=self.avatar)
        with filesystem._impersonateUser():
            self.assertEqual(self.user.name, system_users.getCurrentUserName())
            with filesystem._impersonateUser():
                self.assertEqual(
                    self.user.name, system_users.getCurrentUserName()
                )

            # Even though we have exited the context,
            # we still have the impersonated use as this is a nested call.
            self.assertEqual(self.user.name, system_users.getCurrentUserName())

        # Once we exit all context, the previous context is set.
        self.assertEqual(initial_user, system_users.getCurrentUserName())

    def test_nested_no_reset(self):
        """
        The user impersonation is not reset when nesting specific user
        filesystem with the default filesystem
        """
        initial_user = system_users.getCurrentUserName()
        filesystem = LocalTestFilesystem(avatar=self.avatar)
        default_filesystem = LocalTestFilesystem(avatar=DefaultAvatar())

        with default_filesystem._impersonateUser():
            # Previous user is kept
            self.assertEqual(initial_user, system_users.getCurrentUserName())

        with filesystem._impersonateUser():
            self.assertEqual(self.user.name, system_users.getCurrentUserName())

            with default_filesystem._impersonateUser():
                # Still uses the nested user.
                self.assertEqual(
                    self.user.name, system_users.getCurrentUserName()
                )

        # Once we exit all context, the previous context is set.
        self.assertEqual(initial_user, system_users.getCurrentUserName())

    def test_nested_with_reset(self):
        """
        The user impersonation can reset when nesting a specific user
        filesystem with the default filesystem.
        """
        initial_user = system_users.getCurrentUserName()
        filesystem = LocalTestFilesystem(avatar=self.avatar)

        default_filesystem = LocalTestFilesystem(avatar=DefaultAvatar())

        initial_context = DefaultAvatar._NoOpContext
        DefaultAvatar.setupResetEffectivePrivileges()

        def revert_avatar(initial_context):
            DefaultAvatar._NoOpContext = initial_context

        self.addCleanup(revert_avatar, initial_context)

        with default_filesystem._impersonateUser():
            # Previous user is kept
            self.assertEqual(initial_user, system_users.getCurrentUserName())

        with filesystem._impersonateUser():
            self.assertEqual(self.user.name, system_users.getCurrentUserName())

            with default_filesystem._impersonateUser():
                # Reset the user.
                self.assertEqual(
                    initial_user, system_users.getCurrentUserName()
                )

            # Further call to the specific impersonated filesytem will work
            # and will trigger an impersonation.
            with filesystem._impersonateUser():
                self.assertEqual(
                    self.user.name, system_users.getCurrentUserName()
                )

        # Once we exit all context, the previous context is set.
        self.assertEqual(initial_user, system_users.getCurrentUserName())

    @conditionals.onOSFamily('posix')
    def test_temporary_folder_unix(self):
        """
        On Unix the normal temporary folder is used.
        """
        filesystem = LocalTestFilesystem(avatar=self.avatar)

        # We check that the elevated filesystem start with the same
        # path as normal filesystem
        self.assertEqual(
            mk.fs.temp_segments[:-1],
            filesystem.temp_segments[:-1],
        )

        self.checkTemporaryFolderInitialization(filesystem)

    @conditionals.onOSFamily('nt')
    def test_temporary_folder_nt(self):
        """
        For elevated accounts temporary folder is not located insider
        user default tempo folder and we can start and stop the
        temporary folder.
        """
        filesystem = LocalTestFilesystem(avatar=self.avatar)

        temporary = filesystem.temp_segments
        self.assertEqual(['c', 'temp'], temporary[:2])

        self.checkTemporaryFolderInitialization(filesystem)
