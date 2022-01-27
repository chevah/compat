# Copyright (c) 2010-2012 Adi Roiban.
# See LICENSE for details.
"""
An account as used by Chevah services.
"""
from zope.interface import implements

from chevah_compat import HasImpersonatedAvatar
from chevah_compat.interfaces import IFileSystemAvatar


class FilesystemAvatar(HasImpersonatedAvatar):
    '''
    See `IFileSystemAvatar`.
    '''

    implements(IFileSystemAvatar)

    def __init__(
        self, name, home_folder_path, root_folder_path=None,
        lock_in_home_folder=True, token=None,
        virtual_folders=(),
            ):
        self._name = name
        self._home_folder_path = home_folder_path
        self._root_folder_path = root_folder_path
        self._token = token
        self._lock_in_home_folder = lock_in_home_folder
        self._virtual_folders = virtual_folders

        if not isinstance(self._home_folder_path, str):
            raise RuntimeError('home_folder_path should be text.')

        if self._root_folder_path:
            if not isinstance(self._root_folder_path, str):
                raise RuntimeError('root_folder_path should be text.')

    @property
    def token(self):
        """
        See: :class:`IFileSystemAvatar`

        A token is only used for Windows accounts.
        """
        return self._token

    @property
    def home_folder_path(self):
        """
        See: :class:`IFileSystemAvatar`
        """
        return self._home_folder_path

    @property
    def root_folder_path(self):
        """
        See: :class:`IFileSystemAvatar`
        """
        return self._root_folder_path

    @property
    def lock_in_home_folder(self):
        """
        See: :class:`IFileSystemAvatar`
        """
        return self._lock_in_home_folder

    @property
    def name(self):
        '''Return avatar's name.'''
        return self._name

    @property
    def virtual_folders(self):
        """
        See: :class:`IFileSystemAvatar`
        """
        return self._virtual_folders


class FilesystemOSAvatar(FilesystemAvatar):
    """
    Operating system avatar interacting with the filesystem.
    """

    @property
    def use_impersonation(self):
        """
        See: :class:`IFileSystemAvatar`

        For now OSAvatar is always be impersonated.
        """
        return True


class FilesystemApplicationAvatar(FilesystemAvatar):
    """
    Application avatar interacting with the filesystem.
    """

    @property
    def use_impersonation(self):
        """
        See: :class:`IAvatarBase`

        ApplicationAvatar can not be impersonated.
        """
        return False
