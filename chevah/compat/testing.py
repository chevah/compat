# Copyright (c) 2012 Adi Roiban.
# See LICENSE for details.
"""
Helpers for testing.
"""
import os

from chevah.empirical.testcase import ChevahTestCase
from chevah.empirical.mockup import ChevahCommonsFactory

from chevah.compat import system_users
from chevah.compat.avatar import (
    FilesystemApplicationAvatar,
    FilesystemOSAvatar,
    )


class CompatManufacture(ChevahCommonsFactory):
    """
    Generator of testing helpers for chevah.compat package.
    """

    def makeFilesystemOSAvatar(self, name=None,
            home_folder_path=None, root_folder_path=None,
            lock_in_home_folder=False,
            token=None,
            ):
        """
        Creates a valid FilesystemOSAvatar.
        """
        if name is None:
            name = self.username

        if home_folder_path is None:
            home_folder_path = self.fs.temp_path

        return FilesystemOSAvatar(
            name=name,
            home_folder_path=home_folder_path,
            root_folder_path=root_folder_path,
            lock_in_home_folder=lock_in_home_folder,
            token=token,
            )

    def makeFilesystemApplicationAvatar(self, name=None,
            home_folder_path=None, root_folder_path=None,
            ):
        """
        Creates a valid FilesystemApplicationAvatar.
        """
        if name is None:
            name = self.getUniqueString()

        if home_folder_path is None:
            home_folder_path = self.fs.temp_path

        # Application avatars are locked inside home folders.
        if root_folder_path is None:
            root_folder_path = home_folder_path

        return FilesystemApplicationAvatar(
            name=name,
            home_folder_path=home_folder_path,
            root_folder_path=root_folder_path,
            )

    def makeToken(self, username, password):
        """
        Generate the Windows token for username and password.

        Only useful on WIndows.
        On Unix it should return None.
        """
        if os.name != 'nt':
            return None

        result, token = system_users.authenticateWithUsernameAndPassword(
            username=username,
            password=password,
            )
        if not result:
            raise AssertionError(
                u'Failed to get a valid token for "%s" with "%s".' % (
                    username, password))
        return token

ChevahTestCase
manufacture = CompatManufacture()
