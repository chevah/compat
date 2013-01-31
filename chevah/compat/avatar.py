# Copyright (c) 2010-2012 Adi Roiban.
# See LICENSE for details.
"""
An account as used by Chevah services.
"""
from copy import copy

from zope.interface import implements

from chevah.compat import HasImpersonatedAvatar
from chevah.compat.interfaces import IFilesystemAvatar


class FilesystemAvatar(HasImpersonatedAvatar):
    '''
    See `IFilesystemAvatar`.
    '''

    implements(IFilesystemAvatar)

    def __init__(self, name, home_folder_path, root_folder_path=None,
            lock_in_home_folder=True, token=None):
        self._name = name
        self._home_folder_path = home_folder_path
        self._root_folder_path = root_folder_path
        self._token = token
        self._lock_in_home_folder = lock_in_home_folder

        assert type(self._home_folder_path) is unicode
        if self._root_folder_path:
            assert type(self._root_folder_path) is unicode

    def getCopy(self):
        """
        See: :class:`IFilesystemAvatar`
        """
        result = copy(self)
        return result

    @property
    def token(self):
        """
        See: :class:`IFilesystemAvatar`

        A token is only used for Windows accounts.
        """
        return self._token

    @property
    def home_folder_path(self):
        """
        See: :class:`IFilesystemAvatar`
        """
        return self._home_folder_path

    @property
    def root_folder_path(self):
        """
        See: :class:`IFilesystemAvatar`
        """
        return self._root_folder_path

    @property
    def lock_in_home_folder(self):
        """
        See: :class:`IFilesystemAvatar`
        """
        return self._lock_in_home_folder

    @property
    def name(self):
        '''Return avatar's name.'''
        return self._name


class FilesystemOSAvatar(FilesystemAvatar):
    """
    Operating system avatar interacting with the filesystem.
    """

    @property
    def use_impersonation(self):
        """
        See: :class:`IFilesystemAvatar`

        For now OSAvatar is always be impersonated.
        """
        return True


class FilesystemApplicationAvatar(FilesystemAvatar):
    """
    Application avatar interacting with thefilesystem.
    """

    @property
    def use_impersonation(self):
        """
        See: :class:`IAvatarBase`

        ApplicationAvatar can not be impersoanted.
        """
        return False