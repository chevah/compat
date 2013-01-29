'''Module for hosting the Chevah FTP filesystem access.'''
from __future__ import with_statement
__metaclass__ = type

import errno
import os
import pwd
import grp

from zope.interface import implements
from twisted.python.filepath import FilePath

from chevah.compat.helpers import (
    raise_failed_to_add_group,
    raise_failed_to_set_owner,
    )
from chevah.compat.interfaces import ILocalFilesystem
from chevah.compat.posix_filesystem import PosixFilesystemBase
from chevah.compat.unix_users import UnixUsers


class UnixFilesystem(PosixFilesystemBase):
    '''Implementation if ILocalFilesystem for local Unix filesystems.

    The filesystem absolute root is / and it is the same as the real
    filesystem.

    If avatar is None it will use the current logged in user.
    '''

    implements(ILocalFilesystem)
    system_users = UnixUsers()
    avatar = None

    def __init__(self, avatar):
        self._avatar = avatar
        self._root_handler = self._getRootPath()

    def _getRootPath(self):
        if not self._avatar:
            return FilePath('/')

        if self._avatar.lock_in_home_folder:
            return FilePath(self._avatar.home_folder_path)

        if self._avatar.root_folder_path is None:
            return FilePath('/')
        else:
            return FilePath(self._avatar.root_folder_path)

    def getRealPathFromSegments(self, segments):
        '''See `ILocalFilesystem`.'''
        if segments is None or len(segments) == 0:
            return unicode(self._root_handler.path)
        else:
            relative_path = u'/' + u'/'.join(segments)
            relative_path = os.path.abspath(relative_path).rstrip('/')
            return unicode(
                self._root_handler.path.rstrip('/') + relative_path)

    def getSegmentsFromRealPath(self, real_path):
        '''See `ILocalFilesystem`.'''
        segments = []
        if real_path is None or real_path is u'':
            return segments

        head = True
        tail = os.path.abspath(real_path)
        while tail and head != u'/':
            head, tail = os.path.split(tail)
            if tail != u'':
                if not isinstance(tail, unicode):
                    tail = tail.decode('utf-8')
                segments.insert(0, tail)
            tail = head
        return segments

    def readLink(self, segments):
        '''See `ILocalFilesystem`.'''
        path = self.getRealPathFromSegments(segments)
        path_encoded = path.encode('utf-8')
        with self._impersonateUser():
            return os.readlink(path_encoded)

    def makeLink(self, target_segments, link_segments):
        '''See `ILocalFilesystem`.'''
        target_path = self.getRealPathFromSegments(target_segments)
        target_path_encoded = target_path.encode('utf-8')
        link_path = self.getRealPathFromSegments(link_segments)
        link_path_encoded = link_path.encode('utf-8')
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
            raise_failed_to_set_owner(owner, path)
        with self._impersonateUser():
            return os.chown(path_encoded, uid, -1)

    def getOwner(self, segments):
        '''See `ILocalFilesystem`.'''
        attributes = self.getAttributes(segments, attributes=('owner',))
        uid = attributes[0]
        user_struct = pwd.getpwuid(int(uid))
        return user_struct.pw_name.decode('utf-8')

    def addGroup(self, segments, group, permissions=None):
        '''See `ILocalFilesystem`.'''
        encoded_group = group.encode('utf-8')
        path = self.getRealPathFromSegments(segments)
        path_encoded = path.encode('utf-8')
        try:
            gid = grp.getgrnam(encoded_group).gr_gid
        except KeyError:
            raise_failed_to_add_group(group, path, u'No such group.')
        with self._impersonateUser():
            try:
                return os.chown(path_encoded, -1, gid)
            except OSError, error:
                if error.errno == errno.ENOENT:
                    raise_failed_to_add_group(group, path, u'No such path.')
                elif error.errno == errno.EPERM:
                    raise_failed_to_add_group(group, path, u'Not permitted.')

    def removeGroup(self, segments, group):
        '''See `ILocalFilesystem`.'''
        return

    def hasGroup(self, segments, group):
        '''See `ILocalFilesystem`.'''
        attributes = self.getAttributes(segments, attributes=('group',))
        gid = int(attributes[0])
        group_struct = grp.getgrgid(gid)
        if group_struct.gr_name.decode('utf-8') == group:
            return True
        else:
            return False
