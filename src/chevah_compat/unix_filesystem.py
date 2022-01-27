# Copyright (c) 2013 Adi Roiban.
# See LICENSE for details.
"""
Module for hosting the Unix specific filesystem access.
"""
import codecs
import errno
import grp
import os
import pwd
# See: https://github.com/PyCQA/pylint/issues/1565
import stat  # pylint: disable=bad-python3-import

from zope.interface import implements

from chevah_compat.exceptions import CompatError
from chevah_compat.interfaces import ILocalFilesystem
from chevah_compat.posix_filesystem import PosixFilesystemBase
from chevah_compat.unix_users import UnixUsers


class UnixFilesystem(PosixFilesystemBase):
    """
    Implementation if ILocalFilesystem for local Unix filesystems.

    The filesystem absolute root is / and it is the same as the real
    filesystem.

    If avatar is None it will use the current logged in user.
    """

    implements(ILocalFilesystem)
    system_users = UnixUsers()

    def _getRootPath(self):
        if not self._avatar:
            return u'/'

        if self._avatar.lock_in_home_folder:
            return self._avatar.home_folder_path

        if self._avatar.root_folder_path is None:
            return u'/'
        else:
            return self._avatar.root_folder_path

    def getRealPathFromSegments(self, segments, include_virtual=True):
        """
        See `ILocalFilesystem`.
        """
        if segments is None or len(segments) == 0:
            return str(self._root_path)

        result = self._getVirtualPathFromSegments(segments, include_virtual)
        if result is not None:
            return result

        relative_path = u'/' + u'/'.join(segments)
        relative_path = self.getAbsoluteRealPath(relative_path).rstrip('/')
        return str(self._root_path.rstrip('/') + relative_path)

    def getSegmentsFromRealPath(self, path):
        """
        See `ILocalFilesystem`.
        """
        segments = []
        if path is None or path == u'':
            return segments

        head = True
        tail = self.getAbsoluteRealPath(path)

        for virtual_segments, real_path in self._avatar.virtual_folders:
            virtual_root = self.getAbsoluteRealPath(real_path)
            if not tail.startswith(virtual_root):
                # Not a virtual folder.
                continue

            ancestors = tail[len(real_path):].split('/')
            ancestors = [a for a in ancestors if a]
            return virtual_segments + ancestors

        if self._avatar.lock_in_home_folder:
            self._checkChildPath(self._root_path, tail)
            tail = tail[len(self._root_path):]

        while tail and head != u'/':
            head, tail = os.path.split(tail)
            if tail != u'':
                if not isinstance(tail, str):
                    tail = tail.decode('utf-8')
                segments.insert(0, tail)
            tail = head
        return segments

    def readLink(self, segments):
        '''See `ILocalFilesystem`.'''
        path = self.getRealPathFromSegments(segments, include_virtual=False)
        path_encoded = path.encode('utf-8')
        with self._impersonateUser():
            target = os.readlink(path_encoded).decode('utf-8')
        return self.getSegmentsFromRealPath(target)

    def makeLink(self, target_segments, link_segments):
        """
        See `ILocalFilesystem`.
        """
        target_path = self.getRealPathFromSegments(
            target_segments, include_virtual=False)
        target_path_encoded = self.getEncodedPath(target_path)
        link_path = self.getRealPathFromSegments(
            link_segments, include_virtual=False)
        link_path_encoded = self.getEncodedPath(link_path)

        with self._impersonateUser():
            return os.symlink(target_path_encoded, link_path_encoded)

    def setOwner(self, segments, owner):
        '''See `ILocalFilesystem`.'''
        path = self.getRealPathFromSegments(segments, include_virtual=False)
        encoded_owner = owner.encode('utf-8')
        path_encoded = path.encode('utf-8')
        try:
            uid = pwd.getpwnam(encoded_owner).pw_uid
        except KeyError:
            self.raiseFailedToSetOwner(owner, path, u'Owner not found.')

        with self._impersonateUser():
            try:
                return os.chown(path_encoded, uid, -1)
            except Exception as error:
                self.raiseFailedToSetOwner(owner, path, str(error))

    def getOwner(self, segments):
        '''See `ILocalFilesystem`.'''
        attributes = self.getAttributes(segments)
        user_struct = pwd.getpwuid(attributes.uid)
        return user_struct.pw_name.decode('utf-8')

    def addGroup(self, segments, group, permissions=None):
        '''See `ILocalFilesystem`.'''
        path = self.getRealPathFromSegments(segments, include_virtual=False)
        encoded_group = codecs.encode(group, 'utf-8')
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
        '''
        See `ILocalFilesystem`.

        This has no effect on Unix/Linux but raises an error if we are
        touching a virtual root.
        '''
        self.getRealPathFromSegments(segments, include_virtual=False)
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
        if self._isVirtualPath(segments):
            return False

        path = self.getRealPathFromSegments(segments)
        path_encoded = path.encode('utf-8')

        with self._impersonateUser():
            try:
                stats = os.lstat(path_encoded)
                return bool(stat.S_ISLNK(stats.st_mode))
            except OSError:
                return False

    def deleteFolder(self, segments, recursive=True):
        """
        See `ILocalFilesystem`.
        """
        path = self.getRealPathFromSegments(segments, include_virtual=False)
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
        if self._isVirtualPath(segments):
            # Use a placeholder for parts of a virtual path.
            return self._getPlaceholderStatus()

        path = self.getRealPathFromSegments(segments)
        path_encoded = self.getEncodedPath(path)
        with self._impersonateUser():
            return os.stat(path_encoded)
