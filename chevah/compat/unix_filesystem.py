# Copyright (c) 2013 Adi Roiban.
# See LICENSE for details.
"""
Module for hosting the Unix specific filesystem access.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from six import text_type
import codecs
import errno
import grp
import os
import pwd
# See: https://github.com/PyCQA/pylint/issues/1565
import stat  # pylint: disable=bad-python3-import

from zope.interface import implements

from chevah.compat.exceptions import CompatError
from chevah.compat.interfaces import ILocalFilesystem
from chevah.compat.posix_filesystem import PosixFilesystemBase
from chevah.compat.unix_users import UnixUsers


class UnixFilesystem(PosixFilesystemBase):
    """
    Implementation if ILocalFilesystem for local Unix filesystems.

    The filesystem absolute root is / and it is the same as the real
    filesystem.

    If avatar is None it will use the current logged in user.
    """

    implements(ILocalFilesystem)
    system_users = UnixUsers()

    def __init__(self, avatar):
        self._avatar = avatar
        self._root_handler = self._getRootPath()

    def _getRootPath(self):
        if not self._avatar:
            return u'/'

        if self._avatar.lock_in_home_folder:
            return self._avatar.home_folder_path

        if self._avatar.root_folder_path is None:
            return u'/'
        else:
            return self._avatar.root_folder_path

    def getRealPathFromSegments(self, segments):
        '''See `ILocalFilesystem`.'''
        if segments is None or len(segments) == 0:
            return text_type(self._root_handler)
        else:
            relative_path = u'/' + u'/'.join(segments)
            relative_path = os.path.abspath(relative_path).rstrip('/')
            return text_type(self._root_handler.rstrip('/') + relative_path)

    def getSegmentsFromRealPath(self, path):
        """
        See `ILocalFilesystem`.
        """
        segments = []
        if path is None or path is u'':
            return segments

        head = True
        tail = os.path.abspath(path)

        if self._avatar.lock_in_home_folder:
            self._checkChildPath(self._root_handler, tail)
            tail = tail[len(self._root_handler):]

        while tail and head != u'/':
            head, tail = os.path.split(tail)
            if tail != u'':
                if not isinstance(tail, text_type):
                    tail = tail.decode('utf-8')
                segments.insert(0, tail)
            tail = head
        return segments

    def readLink(self, segments):
        '''See `ILocalFilesystem`.'''
        path = self.getRealPathFromSegments(segments)
        path_encoded = path.encode('utf-8')
        with self._impersonateUser():
            target = os.readlink(path_encoded).decode('utf-8')
        return self.getSegmentsFromRealPath(target)

    def makeLink(self, target_segments, link_segments):
        """
        See `ILocalFilesystem`.
        """
        target_path = self.getRealPathFromSegments(target_segments)
        target_path_encoded = self.getEncodedPath(target_path)
        link_path = self.getRealPathFromSegments(link_segments)
        link_path_encoded = self.getEncodedPath(link_path)

        with self._impersonateUser():
            return os.symlink(target_path_encoded, link_path_encoded)

    def setOwner(self, segments, owner):
        '''See `ILocalFilesystem`.'''
        encoded_owner = owner.encode('utf-8')
        path = self.getRealPathFromSegments(segments)
        path_encoded = path.encode('utf-8')
        try:
            uid = pwd.getpwnam(encoded_owner).pw_uid
        except KeyError:
            self.raiseFailedToSetOwner(owner, path, u'Owner not found.')

        with self._impersonateUser():
            try:
                return os.chown(path_encoded, uid, -1)
            except Exception as error:
                self.raiseFailedToSetOwner(owner, path, text_type(error))

    def getOwner(self, segments):
        '''See `ILocalFilesystem`.'''
        attributes = self.getAttributes(segments)
        user_struct = pwd.getpwuid(attributes.uid)
        return user_struct.pw_name.decode('utf-8')

    def addGroup(self, segments, group, permissions=None):
        '''See `ILocalFilesystem`.'''
        encoded_group = codecs.encode(group, 'utf-8')
        path = self.getRealPathFromSegments(segments)
        path_encoded = path.encode('utf-8')
        try:
            gid = grp.getgrnam(encoded_group).gr_gid
        except KeyError:
            self.raiseFailedToAddGroup(group, path, u'No such group.')
        with self._impersonateUser():
            try:
                return os.chown(path_encoded, -1, gid)
            except OSError as error:
                if error.errno == errno.ENOENT:
                    self.raiseFailedToAddGroup(group, path, u'No such path.')
                elif error.errno == errno.EPERM:
                    self.raiseFailedToAddGroup(group, path, u'Not permitted.')

    def removeGroup(self, segments, group):
        '''See `ILocalFilesystem`.'''
        return

    def hasGroup(self, segments, group):
        '''See `ILocalFilesystem`.'''
        attributes = self.getAttributes(segments)
        group_struct = grp.getgrgid(attributes.gid)
        if group_struct.gr_name.decode('utf-8') == group:
            return True
        else:
            return False

    def _getCurrentUmask(self):
        """
        Return current umask.

        This code is not thread safe.
        """
        # Unix specifications for umask are stupid simple and there is only
        # a single method wich does both get/set.
        # We use 0002 since it is de default mask and statistically we should
        # create less side effects.
        current_umask = os.umask(0o002)
        os.umask(current_umask)
        return current_umask

    def isLink(self, segments):
        """
        See `ILocalFilesystem`.
        """
        path = self.getRealPathFromSegments(segments)
        path_encoded = path.encode('utf-8')

        with self._impersonateUser():
            try:
                stats = os.lstat(path_encoded)
                return bool(stat.S_ISLNK(stats.st_mode))
            except OSError:
                return False

    def deleteFolder(self, segments, recursive=True):
        '''See `ILocalFilesystem`.'''
        path = self.getRealPathFromSegments(segments)
        if path == u'/':
            raise CompatError(
                1009, 'Deleting Unix root folder is not allowed.')
        path_encoded = self.getEncodedPath(path)
        with self._impersonateUser():
            if self.isLink(segments):
                self.deleteFile(segments)
            elif recursive:
                return self._rmtree(path_encoded)
            else:
                return os.rmdir(path_encoded)

    def getStatus(self, segments):
        """
        See `ILocalFilesystem`.
        """
        path = self.getRealPathFromSegments(segments)
        path_encoded = self.getEncodedPath(path)
        with self._impersonateUser():
            return os.stat(path_encoded)
