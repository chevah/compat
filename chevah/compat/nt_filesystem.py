# Copyright (c) 2010-2012 Adi Roiban.
# See LICENSE for details.
'''Module for hosting the Chevah FTP filesystem access.'''
from __future__ import with_statement

import os
import win32api
import win32file
import win32net
import win32security
import ntsecuritycon

from zope.interface import implements

from chevah.compat.exceptions import CompatError, CompatException
from chevah.compat.helpers import _
from chevah.compat.interfaces import ILocalFilesystem
from chevah.compat.nt_capabilities import NTProcessCapabilities
from chevah.compat.nt_users import NTUsers
from chevah.compat.posix_filesystem import PosixFilesystemBase


# cut-and-pasted from MSDN
# 0 Unknown
# 1 No Root Directory
# 2 Removable Disk
# 3 Local Disk
# 4 Network Drive
# 5 Compact Disc
# 6 RAM Disk
LOCAL_DRIVE = 3


def raise_failed_to_set_owner(owner, path, message=u''):
    '''Helper for raising the exception from a single place.'''
    raise CompatError(1016,
        _(u'Failed to set owner to "%s" for "%s". %s' % (
            owner, path, message)))


def raise_failed_to_add_group(group, path, message=u''):
    '''Helper for raising the exception from a single place.'''
    raise CompatError(1017,
        _(u'Failed to add group "%s" for "%s". %s' % (
            group, path, message)))


class NTFilesystem(PosixFilesystemBase):
    """
    Implementation if ILocalFilesystem for local NT filesystems.

    This builds on top of PosixFilesystem.
    """

    implements(ILocalFilesystem)
    system_users = NTUsers()
    process_capabilities = NTProcessCapabilities()

    OPEN_READ_ONLY = os.O_RDONLY | os.O_BINARY
    OPEN_WRITE_ONLY = os.O_WRONLY | os.O_BINARY
    OPEN_READ_WRITE = os.O_RDWR | os.O_BINARY
    OPEN_APPEND = os.O_APPEND | os.O_BINARY

    def __init__(self, avatar=None):
        self._avatar = avatar
        self._root_path = self._getRootPath()

    @property
    def _lock_in_home(self):
        """
        True if filesystem access should be restricted to home folder.
        """
        if not self._avatar:
            return False
        else:
            return self._avatar.lock_in_home_folder

    def _getRootPath(self):
        """
        Return the root path for the filesystem.
        """
        if not self._avatar:
            return u'c:\\'

        if self._lock_in_home:
            path = unicode(self._avatar.home_folder_path)
        else:
            if self._avatar.root_folder_path is None:
                path = u'c:\\'
            else:
                path = unicode(self._avatar.root_folder_path)

        # Fix folder separators.
        path = path.replace('/', '\\')
        return path

    @classmethod
    def getEncodedPath(cls, path):
        '''Return the encoded representation of the path, use in the lower
        lever API for accessing the filesystem.'''
        return path

    def _getLockedPathFromSegments(self, segments):
        '''
        Return a path for segments making sure the resulting path is not
        outside of the chroot.
        '''
        path = os.path.normpath(os.path.join(*segments))
        if path.startswith('..\\'):
            path = path[3:]
        result = os.path.normpath(self._root_path + u'\\' + path)
        if result.lower().startswith(self._root_path.lower()):
            return result.rstrip('\\')
        else:
            return self._root_path

    def getRealPathFromSegments(self, segments):
        '''See `ILocalFilesystem`.
        * []
          * lock : root_path
          * unlock: COMPUTER
        * lock
          * [path1] ->  root_path \ path1
          * [path1, path2] -> root_path \ path1 \ path2
        * unlock
          * [path1] -> path1:\
          * [path1, path2] -> path1 :\ path2
        '''
        if segments is None or len(segments) == 0:
            result = self._root_path
        elif self._lock_in_home:
            result = self._getLockedPathFromSegments(segments)
        else:
            drive = u'%s:\\' % segments[0]
            path_segments = segments[1:]
            if len(path_segments) == 0:
                result = drive
            else:
                result = os.path.normpath(
                    drive + os.path.join(*path_segments))
                # os.path.normpath can result in an 'out of drive' path.
                if result.find(':\\') == -1:
                    if result.find('\\') == -1:
                        result = result + ':\\'
                    else:
                        result = result.replace('\\', ':\\', 1)
        return unicode(result)

    def getSegmentsFromRealPath(self, path):
        '''See `ILocalFilesystem`.'''
        segments = []

        if path is None or path == u'':
            return segments

        path = os.path.abspath(path)
        drive, root_tail = os.path.splitdrive(path)
        if drive == u'':
            segments = [u'c']
        else:
            segments = [drive.strip(u':')]

        head = True
        tail = root_tail
        while head not in [u'\\', u'']:
            head, tail = os.path.split(tail)
            if tail != '':
                segments.insert(1, tail)
            tail = head
        return segments

    def readLink(self, segments):
        '''See `ILocalFilesystem`.'''
        raise NotImplementedError

    def makeLink(self, target_segments, link_segments):
        '''See `ILocalFilesystem`.'''
        raise NotImplementedError

    def getAttributes(self, segments, attributes=None, follow_links=False):
        '''See `ILocalFilesystem`.'''
        try:
            return super(NTFilesystem, self).getAttributes(
                segments, attributes, follow_links)
        except WindowsError, error:
            raise OSError(error.errno, error.strerror)

    def setAttributes(self, segments, attributes):
        '''See `ILocalFilesystem`.'''
        try:
            return super(NTFilesystem, self).setAttributes(
                segments, attributes)
        except WindowsError, error:
            raise OSError(error.errno, error.strerror)

    def getFolderContent(self, segments):
        '''See `ILocalFilesystem`.'''
        try:
            '''If we are locked in home folder just go with the normal way,
            otherwise if empty folder, parent or current folder is requested,
            just show the ROOT.'''
            if self._lock_in_home or segments not in [[], ['.'], ['..']]:
                return super(NTFilesystem, self).getFolderContent(segments)
            else:
                raw_drives = win32api.GetLogicalDriveStrings()
                drives = [drive for drive in raw_drives.split("\000")
                                if drive]
                result = []
                for drive in drives:
                    if win32file.GetDriveType(drive) == LOCAL_DRIVE:
                        drive = drive.strip(':\\')
                        drive = drive.decode(self.INTERNAL_ENCODING)
                        result.append(drive)
                return result
        except WindowsError, error:
            raise OSError(error.errno, error.strerror)

    def createFolder(self, segments, recursive=False):
        '''See `ILocalFilesystem`.'''
        try:
            return super(NTFilesystem, self).createFolder(
                segments, recursive)
        except WindowsError, error:
            raise OSError(error.errno, error.strerror)

    def deleteFolder(self, segments, recursive=True):
        '''See `ILocalFilesystem`.'''
        try:
            return super(NTFilesystem, self).deleteFolder(
                segments, recursive)
        except WindowsError, error:
            raise OSError(error.errno, error.strerror)

    def deleteFile(self, segments, ignore_errors=False):
        '''See `ILocalFilesystem`.'''
        try:
            return super(NTFilesystem, self).deleteFile(
                segments, ignore_errors)
        except WindowsError, error:
            raise OSError(error.errno, error.strerror)

    def rename(self, from_segments, to_segments):
        '''See `ILocalFilesystem`.'''
        try:
            return super(NTFilesystem, self).rename(
                from_segments, to_segments)
        except WindowsError, error:
            raise OSError(error.errno, error.strerror)

    def setOwner(self, segments, owner):
        """
        See `ILocalFilesystem`.
        """
        path = self.getRealPathFromSegments(segments)
        try:
            self._setOwner(path, owner)
        except CompatException, error:
            raise_failed_to_set_owner(owner, path, error.message)

    def _setOwner(self, path, owner):
        """
        Helper for catching exceptions raised by _elevatePrivileges.
        """
        with self.process_capabilities._elevatePrivileges(
                win32security.SE_TAKE_OWNERSHIP_NAME,
                win32security.SE_RESTORE_NAME,
                ):
            try:
                security_descriptor = win32security.GetNamedSecurityInfo(
                    path,
                    win32security.SE_FILE_OBJECT,
                    win32security.DACL_SECURITY_INFORMATION,
                    )
                d_acl = security_descriptor.GetSecurityDescriptorDacl()

                user_sid, user_domain, user_type = (
                    win32security.LookupAccountName(None, owner))
                flags = (
                    win32security.OBJECT_INHERIT_ACE |
                    win32security.CONTAINER_INHERIT_ACE)

                d_acl.AddAccessAllowedAceEx(
                    win32security.ACL_REVISION_DS,
                    flags,
                    win32file.FILE_ALL_ACCESS,
                    user_sid,
                    )
                win32security.SetNamedSecurityInfo(path,
                    win32security.SE_FILE_OBJECT,
                    win32security.OWNER_SECURITY_INFORMATION,
                    user_sid,
                    None,
                    None,
                    None,
                    )
                win32security.SetNamedSecurityInfo(path,
                    win32security.SE_FILE_OBJECT,
                    win32security.DACL_SECURITY_INFORMATION,
                    None,
                    None,
                    d_acl,
                    None,
                    )
            except win32net.error, error:
                if error.winerror == 1332:
                    raise_failed_to_set_owner(owner, path, u'No such owner.')
                if error.winerror == 1307:
                    raise_failed_to_set_owner(owner, path, u'Not permitted.')
                else:
                    raise OSError(error.winerror, error.strerror)

    def getOwner(self, segments):
        '''See `ILocalFilesystem`.'''
        path = self.getRealPathFromSegments(segments)

        with self._impersonateUser():
            try:
                owner_security = win32security.GetFileSecurity(
                    path, win32security.OWNER_SECURITY_INFORMATION)
                owner_sid = owner_security.GetSecurityDescriptorOwner()
                name, domain, type = win32security.LookupAccountSid(
                    None, owner_sid)
                return name
            except win32net.error, error:
                raise OSError(
                    error.winerror, error.strerror)

    def addGroup(self, segments, group, permissions=None):
        '''See `ILocalFilesystem`.'''
        path = self.getRealPathFromSegments(segments)

        try:
            group_sid, group_domain, group_type = (
                win32security.LookupAccountName(None, group))
        except win32net.error:
            raise_failed_to_add_group(group, path, u'Could not get group ID.')

        with self._impersonateUser():
            try:
                security = win32security.GetFileSecurity(
                    path, win32security.DACL_SECURITY_INFORMATION)
                dacl = security.GetSecurityDescriptorDacl()
                dacl.AddAccessAllowedAce(
                    win32security.ACL_REVISION,
                    ntsecuritycon.FILE_ALL_ACCESS,
                    group_sid)
                security.SetDacl(True, dacl, False)
                win32security.SetFileSecurity(
                    path, win32security.DACL_SECURITY_INFORMATION, security)
            except win32net.error, error:
                raise_failed_to_add_group(
                    group, path, u'%s: %s' % (error.winerror, error.strerror))

    def removeGroup(self, segments, group):
        '''See `ILocalFilesystem`.'''
        path = self.getRealPathFromSegments(segments)

        try:
            group_sid, group_domain, group_type = (
                win32security.LookupAccountName(None, group))
        except win32net.error:
            raise CompatError(1013, _(
                u'Failed to remove group "%s" from "%s". %s' % (
                    group, path, u'Group does not exists.')))

        with self._impersonateUser():
            try:
                security = win32security.GetFileSecurity(
                    path, win32security.DACL_SECURITY_INFORMATION)
            except win32net.error, error:
                raise OSError(
                    error.winerror, error.strerror)

            dacl = security.GetSecurityDescriptorDacl()
            ace_count = dacl.GetAceCount()
            if ace_count < 1:
                # Nothing in the list, nothing to remove.
                return
            index_ace_to_remove = -1
            for index in xrange(ace_count):
                ((ace_type, ace_flag), mask, sid) = dacl.GetAce(index)
                if group_sid == sid:
                    index_ace_to_remove = index
                    break

            if index_ace_to_remove == -1:
                # Group not found in the list.
                return

            dacl.DeleteAce(index_ace_to_remove)
            security.SetDacl(True, dacl, False)
            win32security.SetFileSecurity(
                path, win32security.DACL_SECURITY_INFORMATION, security)
        return False

    def hasGroup(self, segments, group):
        '''See `ILocalFilesystem`.'''
        path = self.getRealPathFromSegments(segments)

        try:
            group_sid, group_domain, group_type = (
                win32security.LookupAccountName(None, group))
        except win32net.error:
            return False

        with self._impersonateUser():
            try:
                security = win32security.GetFileSecurity(
                    path, win32security.DACL_SECURITY_INFORMATION)
            except win32net.error, error:
                raise OSError(
                    error.winerror, error.strerror)

            dacl = security.GetSecurityDescriptorDacl()
            ace_count = dacl.GetAceCount()
            if ace_count < 1:
                # Nothing in the list.
                return False
            for index in xrange(ace_count):
                ((ace_type, ace_flag), mask, sid) = dacl.GetAce(index)
                if group_sid == sid:
                    return True
        return False
