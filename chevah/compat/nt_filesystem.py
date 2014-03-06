# Copyright (c) 2010-2012 Adi Roiban.
# See LICENSE for details.
"""
Windows specific implementation of filesystem access.
"""
import errno
import ntsecuritycon
import os
import pywintypes
import shutil
import win32api
import win32file
import win32net
import win32security

from zope.interface import implements

from chevah.compat.exceptions import CompatError, CompatException
from chevah.compat.helpers import _
from chevah.compat.interfaces import ILocalFilesystem
from chevah.compat.nt_capabilities import NTProcessCapabilities
from chevah.compat.nt_users import NTDefaultAvatar, NTUsers
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

# Not defined in win32api.
# (0x400)
FILE_ATTRIBUTE_REPARSE_POINT = 1024
# Not defined in winnt.h
# http://msdn.microsoft.com/en-us/library/windows/
#   desktop/aa365511(v=vs.85).aspx
IO_REPARSE_TAG_SYMLINK = 0xA000000C


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

    @property
    def temp_segments(self):
        """
        Segments to temporary folder.
        """
        # FIXME:930:
        # For impersonated account we can not return the default temporary
        # folder, which is located in default account temp folder, since
        # impersonated account don't have access to it.
        if not isinstance(self._avatar, NTDefaultAvatar):
            return [u'c', u'temp']
        else:
            # Default tempfile.gettempdir() return path with short names,
            # due to win32api.GetTempPath().
            return self._pathSplitRecursive(
                win32api.GetLongPathName(win32api.GetTempPath()))

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
        """
        See `ILocalFilesystem`.
        """
        segments = []

        if path is None or path == u'':
            return segments

        head = True
        path = os.path.abspath(path)

        if self._avatar.lock_in_home_folder:
            # Locked filesystem have no drive.
            tail = path[len(self._getRootPath()):]
            drive = ''
        else:
            # For unlocked filesystem, we use 'c' as default drive.
            drive, root_tail = os.path.splitdrive(path)
            if not drive:
                drive = u'c'
            else:
                drive = drive.strip(u':')
            tail = root_tail

        while head not in [u'\\', u'']:
            head, tail = os.path.split(tail)
            if tail == '':
                break
            segments.insert(0, tail)
            tail = head

        # Prepend drive at the end, due to the way os.path.split works.
        if drive:
            segments.insert(0, drive)

        return segments

    def readLink(self, segments):
        '''See `ILocalFilesystem`.'''
        # FIXME:2023:
        # Add implementation.
        raise NotImplementedError

    def makeLink(self, target_segments, link_segments):
        """
        See `ILocalFilesystem`.

        It only supports symbolic links.

        Code example for handling reparse points:
        http://www.codeproject.com/Articles/21202/Reparse-Points-in-Vista
        """
        # FIXME:2025:
        # Add support for junctions.
        if not self.process_capabilities.symbolic_link:
            raise NotImplementedError

        target_path = self.getRealPathFromSegments(target_segments)
        link_path = self.getRealPathFromSegments(link_segments)

        if self.isFolder(target_segments):
            flags = win32file.SYMBOLIC_LINK_FLAG_DIRECTORY
        else:
            flags = 0

        with self._impersonateUser():
            with self.process_capabilities.elevatePrivileges(
                    win32security.SE_CREATE_SYMBOLIC_LINK_NAME):
                try:
                    win32file.CreateSymbolicLink(
                        link_path, target_path, flags)
                except WindowsError, error:
                    raise OSError(error.errno, error.strerror)
                except pywintypes.error, error:
                    raise OSError(error.winerror, error.strerror)

    def getStatus(self, segments):
        '''See `ILocalFilesystem`.'''
        try:
            return super(NTFilesystem, self).getStatus(segments)
        except WindowsError, error:
            raise OSError(error.errno, error.strerror)

    def getAttributes(self, segments, attributes):
        '''See `ILocalFilesystem`.'''
        try:
            return super(NTFilesystem, self).getAttributes(
                segments, attributes)
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
                drives = [
                    drive for drive in raw_drives.split("\000") if drive]
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

    def _getFileData(self, segments):
        """
        Return a dict with resolved WIN32_FIND_DATA structure for segments.

        Raise OSError if path does not exists or path is invalid.

        Available attributes:
        http://msdn.microsoft.com/en-us/library/windows/
            desktop/gg258117(v=vs.85).aspx
        """
        path = self.getEncodedPath(self.getRealPathFromSegments(segments))

        try:
            with self._impersonateUser():
                search = win32file.FindFilesW(path)
                if len(search) != 1:
                    message = 'Could not find %s' % path
                    raise OSError(errno.ENOENT, message.encode('utf-8'))
                data = search[0]
        except pywintypes.error, error:
            message = u'%s %s %s' % (error.winerror, error.strerror, path)
            raise OSError(errno.EINVAL, message.encode('utf-8'))

        # Raw data:
        # [0] int : attributes
        # [1] PyTime : createTime
        # [2] PyTime : accessTime
        # [3] PyTime : writeTime
        # [4] int : nFileSizeHigh
        # [5] int : nFileSizeLow
        # [6] int : reserved0
        #           Contains reparse tag if path is a reparse point
        # [7] int : reserved1 - Reserved.
        # [8] str/unicode : fileName
        # [9] str/unicode : alternateFilename

        size_high = data[4]
        size_low = data[5]
        size = (size_high << 32) + size_low
        # size_low is SIGNED int.
        if size_low < 0:
            size += 0x100000000

        return {
            'attributes': data[0],
            'create_time': data[1],
            'access_time': data[2],
            'write_time': data[3],
            'size': size,
            'tag': data[6],
            'name': data[8],
            'alternate_name': data[9],
            }

    def isLink(self, segments):
        """
        See `ILocalFilesystem`.
        """
        try:
            data = self._getFileData(segments)
            is_reparse_point = bool(
                data['attributes'] & FILE_ATTRIBUTE_REPARSE_POINT)
            has_symlink_tag = (data['tag'] == IO_REPARSE_TAG_SYMLINK)
            return is_reparse_point and has_symlink_tag
        except OSError:
            return False

    def deleteFolder(self, segments, recursive=True):
        """
        See `ILocalFilesystem`.

        For symbolic links we always force non-recursive behaviour.
        """
        path = self.getRealPathFromSegments(segments)
        path_encoded = self.getEncodedPath(path)

        try:
            with self._impersonateUser():
                if self.isLink(segments):
                    recursive = False

                if recursive:
                    return shutil.rmtree(path_encoded)
                else:
                    return os.rmdir(path_encoded)
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
            self.raiseFailedToSetOwner(owner, path, error.message)

    def _setOwner(self, path, owner):
        """
        Helper for catching exceptions raised by elevatePrivileges.
        """
        with self.process_capabilities.elevatePrivileges(
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
                win32security.SetNamedSecurityInfo(
                    path,
                    win32security.SE_FILE_OBJECT,
                    win32security.OWNER_SECURITY_INFORMATION,
                    user_sid,
                    None,
                    None,
                    None,
                    )
                win32security.SetNamedSecurityInfo(
                    path,
                    win32security.SE_FILE_OBJECT,
                    win32security.DACL_SECURITY_INFORMATION,
                    None,
                    None,
                    d_acl,
                    None,
                    )
            except win32net.error, error:
                if error.winerror == 1332:
                    self.raiseFailedToSetOwner(owner, path, u'No such owner.')
                if error.winerror == 1307:
                    self.raiseFailedToSetOwner(owner, path, u'Not permitted.')
                else:
                    self.raiseFailedToSetOwner(owner, path, unicode(error))

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
            self.raiseFailedToAddGroup(
                group, path, u'Could not get group ID.')

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
                self.raiseFailedToAddGroup(
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
