# Copyright (c) 2014 Adi Roiban.
# See LICENSE for details.
"""
Filesystem code used by all operating systems, including Windows as
Windows has its layer of POSIX compatibility.
"""
from contextlib import contextmanager
import codecs
import errno
import os
import re
import stat
import struct
import sys

from chevah.compat.constants import (
    DEFAULT_FILE_MODE,
    DEFAULT_FOLDER_MODE,
    )
from chevah.compat.exceptions import (
    ChangeUserException,
    CompatError,
    CompatException,
    )
from chevah.compat.helpers import _, NoOpContext


class PosixFilesystemBase(object):
    '''Base implementation if ILocalFilesystem for
    local Posix filesystems.

    It handles `raw` access to the filesystem.
    Classed using this base should implement path and segment handling
    '''

    OPEN_READ_ONLY = os.O_RDONLY
    OPEN_WRITE_ONLY = os.O_WRONLY
    OPEN_READ_WRITE = os.O_RDWR
    OPEN_CREATE = os.O_CREAT
    OPEN_APPEND = os.O_APPEND
    OPEN_EXCLUSIVE = os.O_EXCL
    OPEN_TRUNCATE = os.O_TRUNC

    INTERNAL_ENCODING = u'utf-8'

    # Windows specific constants, placed here to help with unit testing
    # of Windows specific data.
    #
    # Not defined in winnt.h
    # http://msdn.microsoft.com/en-us/library/windows/
    #   desktop/aa365511(v=vs.85).aspx
    IO_REPARSE_TAG_SYMLINK = 0xA000000C

    @property
    def avatar(self):
        return self._avatar

    @property
    def installation_segments(self):
        """
        See `ILocalFilesystem`.

        We use 'os' module to find where the python is installed, and from
        there we find the base folder.

        * Windows - INSTALL_FOLDER/ lib/ Lib/       os.py
        * Unix    - INSTALL_FOLDER/ lib/ python2.X/ os.py
        """
        path = os.path.dirname(os.__file__)
        segments = self.getSegmentsFromRealPath(path)
        return segments[:-2]

    def _impersonateUser(self):
        """
        Returns an impersonation context for current user.
        """
        if not self._avatar:
            return NoOpContext()

        try:
            return self._avatar.getImpersonationContext()
        except ChangeUserException:
            raise CompatError(
                1006,
                _(u'Could not switch process to local account "%s".' % (
                    self._avatar.name)),
                )

    def _touch(self, segments, times=None):
        '''Update modified time.'''
        path = self.getRealPathFromSegments(segments)
        path_encoded = self.getEncodedPath(path)
        with self._impersonateUser():
            with file(path_encoded, 'a'):
                os.utime(path_encoded, times)

    def _pathSplitRecursive(self, path):
        '''Recursive split of a path.'''
        separators = os.path.sep
        if os.path.altsep:
            separators += os.path.altsep
        segments = re.split('[%r]' % separators, path)

        if len(segments) > 0:
            segments[0] = segments[0].strip(':')
        return [segment for segment in segments if segment != '']

    @classmethod
    def getEncodedPath(cls, path):
        '''Return the encoded representation of the path, use in the lower
        lever API for accessing the filesystem.'''
        return path.encode(u'utf-8')

    @property
    def home_segments(self):
        '''See `ILocalFilesystem`.'''

        if not self._avatar:
            return self._pathSplitRecursive(unicode(os.path.expanduser('~')))

        if self._avatar.root_folder_path is None:
            return self._pathSplitRecursive(self._avatar.home_folder_path)

        home_lower = self._avatar.home_folder_path.lower()
        root_lower = self._avatar.root_folder_path.rstrip('/\\').lower()
        # Check that we have a valid home folder.
        if not home_lower.startswith(root_lower):
            raise CompatError(
                20019,
                _(
                    'User home folder "%s" is not withing the root folder '
                    '"%s".' % (
                        self._avatar.home_folder_path,
                        self._avatar.root_folder_path),
                    ),
                )

        path = self._avatar.home_folder_path[len(root_lower):]
        return self._pathSplitRecursive(path)

    def getPath(self, segments):
        '''See `ILocalFilesystem`.'''
        if segments == []:
            return u'/'
        else:
            normalize_path = os.path.normpath('/'.join(segments))
            return u'/' + '/'.join(self._pathSplitRecursive(normalize_path))

    def getSegments(self, path):
        '''See `ILocalFilesystem`.

        Get segment is the place where segments are created and we make sure
        they are in the internal encoding.
        '''
        if path is None or path == '' or path == '.':
            return self.home_segments

        if not isinstance(path, unicode):
            path = path.decode(self.INTERNAL_ENCODING)

        if not path.startswith('/'):
            # Resolve relative path.
            home_path = u'/' + u'/'.join(self.home_segments) + u'/'
            path = home_path + path

        normalize_path = os.path.normpath(path)
        return self._pathSplitRecursive(normalize_path)

    @property
    def temp_segments(self):
        '''See `ILocalFilesystem`.'''
        import tempfile
        temporary_folder = tempfile.gettempdir()
        return self._pathSplitRecursive(temporary_folder)

    def getRealPathFromSegments(self, segments):
        '''See `ILocalFilesystem`.'''
        raise NotImplementedError('You must implement this method.')

    def getSegmentsFromRealPath(self, path):
        '''See `ILocalFilesystem`.'''
        raise NotImplementedError('You must implement this method.')

    def getAbsoluteRealPath(self, path):
        '''See `ILocalFilesystem`.'''
        if not isinstance(path, unicode):
            path = path.decode(self.INTERNAL_ENCODING)

        absolute_path = os.path.abspath(path)
        if not isinstance(absolute_path, unicode):
            absolute_path = absolute_path.decode(self.INTERNAL_ENCODING)

        return absolute_path

    def isFolder(self, segments):
        '''See `ILocalFilesystem`.'''
        try:
            return self.getAttributes(segments, ('directory',))[0]
        except OSError:
            return False

    def isFile(self, segments):
        '''See `ILocalFilesystem`.'''
        try:
            return self.getAttributes(segments, ('file',))[0]
        except OSError:
            return False

    def isLink(self, segments):
        """
        See `ILocalFilesystem`.
        """
        raise NotImplementedError()

    def exists(self, segments):
        '''See `ILocalFilesystem`.'''
        path = self.getRealPathFromSegments(segments)
        path_encoded = self.getEncodedPath(path)
        with self._impersonateUser():
            return os.path.exists(path_encoded)

    def createFolder(self, segments, recursive=False):
        '''See `ILocalFilesystem`.'''
        path = self.getRealPathFromSegments(segments)
        path_encoded = self.getEncodedPath(path)
        with self._impersonateUser():
            if recursive:
                return os.makedirs(path_encoded, DEFAULT_FOLDER_MODE)
            else:
                return os.mkdir(path_encoded, DEFAULT_FOLDER_MODE)

    def deleteFolder(self, segments, recursive=True):
        """
        See `ILocalFilesystem`.
        """
        raise NotImplementedError()

    def deleteFile(self, segments, ignore_errors=False):
        '''See `ILocalFilesystem`.'''
        path = self.getRealPathFromSegments(segments)
        path_encoded = self.getEncodedPath(path)
        with self._impersonateUser():
            try:
                return os.unlink(path_encoded)
            except:
                if ignore_errors:
                    return
                else:
                    raise

    def rename(self, from_segments, to_segments):
        '''See `ILocalFilesystem`.'''
        from_path = self.getRealPathFromSegments(from_segments)
        from_path_encoded = self.getEncodedPath(from_path)
        to_path = self.getRealPathFromSegments(to_segments)
        to_path_encoded = self.getEncodedPath(to_path)
        with self._impersonateUser():
            return os.rename(from_path_encoded, to_path_encoded)

    @contextmanager
    def _IOToOSError(self, path):
        """
        Convert IOError to OSError.
        """
        try:
            yield
        except IOError, error:
            raise OSError(error.errno, error.message, path)

    def openFile(self, segments, flags, mode):
        '''See `ILocalFilesystem`.'''
        path = self.getRealPathFromSegments(segments)
        path_encoded = self.getEncodedPath(path)

        if self.isFolder(segments):
            raise OSError(errno.EISDIR, 'Is a directory: %s' % path_encoded)

        with self._IOToOSError(path_encoded), self._impersonateUser():
            return os.open(path_encoded, flags, mode)

    def openFileForReading(self, segments, utf8=False):
        '''See `ILocalFilesystem`.'''
        path = self.getRealPathFromSegments(segments)
        path_encoded = self.getEncodedPath(path)
        with self._IOToOSError(path_encoded), self._impersonateUser():
            if utf8:
                return codecs.open(path_encoded, 'r', 'utf-8')
            else:
                fd = os.open(
                    path_encoded,
                    self.OPEN_READ_ONLY,
                    DEFAULT_FILE_MODE)
                return os.fdopen(fd, 'rb')

    def openFileForWriting(self, segments, utf8=False):
        '''See `ILocalFilesystem`.'''
        path = self.getRealPathFromSegments(segments)
        path_encoded = self.getEncodedPath(path)
        with self._IOToOSError(path_encoded), self._impersonateUser():
            if utf8:
                return codecs.open(path_encoded, 'w', 'utf-8')
            else:
                fd = os.open(
                    path_encoded,
                    (self.OPEN_WRITE_ONLY | self.OPEN_CREATE |
                        self.OPEN_TRUNCATE),
                    DEFAULT_FILE_MODE)
                return os.fdopen(fd, 'wb')

    def openFileForAppending(self, segments, utf8=False):
        '''See `ILocalFilesystem`.'''
        def fail_on_read():
            raise AssertionError(
                'File opened for appending. Read is not allowed.')
        path = self.getRealPathFromSegments(segments)
        path_encoded = self.getEncodedPath(path)
        with self._IOToOSError(path_encoded), self._impersonateUser():
            if utf8:
                return codecs.open(path_encoded, 'a+b', 'utf-8')
            else:
                fd = os.open(
                    path_encoded,
                    (self.OPEN_APPEND | self.OPEN_CREATE |
                        self.OPEN_WRITE_ONLY),
                    DEFAULT_FILE_MODE)
                new_file = os.fdopen(fd, 'ab')
                return new_file

    def getFileSize(self, segments):
        '''See `ILocalFilesystem`.'''
        path = self.getRealPathFromSegments(segments)
        path_encoded = self.getEncodedPath(path)
        with self._impersonateUser():
            return os.path.getsize(path_encoded)

    def getFolderContent(self, segments):
        '''See `ILocalFilesystem`.'''
        path = self.getRealPathFromSegments(segments)
        path_encoded = self.getEncodedPath(path)
        result = []
        with self._impersonateUser():
            for entry in os.listdir(path_encoded):
                if not isinstance(entry, unicode):
                    entry = entry.decode(self.INTERNAL_ENCODING)
                result.append(entry)
        return result

    def getStatus(self, segments):
        """
        See `ILocalFilesystem`.
        """
        path = self.getRealPathFromSegments(segments)
        path_encoded = self.getEncodedPath(path)
        with self._impersonateUser():
            return os.stat(path_encoded)

    def getAttributes(self, segments, attributes):
        """
        See `ILocalFilesystem`.
        """
        results = []
        stats = self.getStatus(segments)
        mode = stats.st_mode
        is_directory = bool(stat.S_ISDIR(mode))
        if is_directory and sys.platform.startswith('aix'):
            # On AIX mode contains an extra most significant bit
            # which we don't use.
            mode = mode & 0077777

        is_link = self.isLink(segments)
        mapping = {
            'size': stats.st_size,
            'permissions': mode,
            'hardlinks': stats.st_nlink,
            'modified': stats.st_mtime,
            'owner': str(stats.st_uid),
            'group': str(stats.st_gid),
            'uid': stats.st_uid,
            'gid': stats.st_gid,
            'directory': is_directory,
            'link': is_link,
            'file': bool(stat.S_ISREG(mode))
            }

        for attribute in attributes:
            results.append(mapping[attribute])

        return results

    def setAttributes(self, segments, attributes):
        '''See `ILocalFilesystem`.'''
        path = self.getRealPathFromSegments(segments)
        path_encoded = self.getEncodedPath(path)
        with self._impersonateUser():
            if 'uid' in attributes and 'gid' in attributes:
                os.chown(path_encoded, attributes['uid'], attributes['gid'])
            if 'permissions' in attributes:
                os.chmod(path_encoded, attributes['permissions'])
            if 'atime' in attributes and 'mtime' in attributes:
                os.utime(
                    path_encoded, (attributes['atime'], attributes['mtime']))

    def setGroup(self, segments, group, permissions=None):
        '''Informational method for not using setGroup.'''
        raise AssertionError(u'Use addGroup for setting a group.')

    def raiseFailedToAddGroup(self, group, path, message=u''):
        """
        Helper for raising the exception from a single place.
        """
        raise CompatError(
            1017,
            _(u'Failed to add group "%s" for "%s". %s' % (
                group, path, message)),
            )

    def raiseFailedToSetOwner(self, owner, path, message=u''):
        """
        Helper for raising the exception from a single place.
        """
        raise CompatError(
            1016,
            _(u'Failed to set owner to "%s" for "%s". %s' % (
                owner, path, message)),
            )

    def _checkChildPath(self, root, child):
        """
        Check that child path is inside root path.
        """
        child_strip = os.path.abspath(child)
        root_strip = os.path.abspath(root)

        if not child_strip.startswith(root_strip):
            raise CompatError(
                1018, u'Path "%s" is outside of locked folder "%s"' % (
                    child, root))

    def _parseReparseData(self, raw_reparse_data):
        """
        Parse reparse buffer.

        Return a dict in format:
        {
            'tag': TAG,
            'length': LENGTH,
            'data': actual_payload_as_byte_string,
            ...
            'optional_struct_member_1': VALUE_FOR_STRUCT_MEMBER,
            ...
            }

        When reparse data contains an unknown tag, it will parse the tag
        and length headers and put everything else in data.
        """
        # Size of our types.
        SIZE_ULONG = 4  # sizeof(ULONG)
        SIZE_USHORT = 2  # sizeof(USHORT)
        HEADER_SIZE = 20

        # buffer structure:
        #
        # typedef struct _REPARSE_DATA_BUFFER {
        #     ULONG  ReparseTag;
        #     USHORT ReparseDataLength;
        #     USHORT Reserved;
        #     union {
        #         struct {
        #             USHORT SubstituteNameOffset;
        #             USHORT SubstituteNameLength;
        #             USHORT PrintNameOffset;
        #             USHORT PrintNameLength;
        #             ULONG Flags;
        #             WCHAR PathBuffer[1];
        #         } SymbolicLinkReparseBuffer;
        #         struct {
        #             USHORT SubstituteNameOffset;
        #             USHORT SubstituteNameLength;
        #             USHORT PrintNameOffset;
        #             USHORT PrintNameLength;
        #             WCHAR PathBuffer[1];
        #         } MountPointReparseBuffer;
        #         struct {
        #             UCHAR  DataBuffer[1];
        #         } GenericReparseBuffer;
        #     } DUMMYUNIONNAME;
        # } REPARSE_DATA_BUFFER, *PREPARSE_DATA_BUFFER;

        # Supported formats for reparse data.
        # For now only SymbolicLinkReparseBuffer is supported.
        formats = {
            # http://msdn.microsoft.com/en-us/library/cc232006.aspx
            self.IO_REPARSE_TAG_SYMLINK: [
                ('substitute_name_offset', SIZE_USHORT),
                ('substitute_name_length', SIZE_USHORT),
                ('print_name_offset', SIZE_USHORT),
                ('print_name_length', SIZE_USHORT),
                ('flags', SIZE_ULONG),
                ],
            }

        if len(raw_reparse_data) < HEADER_SIZE:
            raise CompatException('Reparse buffer to small.')

        result = {}
        # Parse header.
        result['tag'] = struct.unpack('<L', raw_reparse_data[:4])[0]
        result['length'] = struct.unpack(
            '<H', raw_reparse_data[4:6])[0]
        # Reserved header member is ignored.
        tail = raw_reparse_data[8:]

        try:
            structure = formats[result['tag']]
        except KeyError:
            structure = []

        for member_name, member_size in structure:
            member_data = tail[:member_size]
            tail = tail[member_size:]

            if member_size == SIZE_USHORT:
                result[member_name] = struct.unpack('<H', member_data)[0]
            else:
                result[member_name] = struct.unpack('<L', member_data)[0]
            # result[member_name] = 0
            # for byte in member_data:
            #     result[member_name] += ord(byte)

        # Remaining tail is set as data.
        result['data'] = tail
        return result

    def _parseSymbolicLinkReparse(self, symbolic_link_data):
        """
        Return a diction with 'name' and 'target' for `symbolic_link_data` as
        Unicode strings.
        """
        result = {
            'name': None,
            'target': None,
            }

        offset = symbolic_link_data['print_name_offset']
        ending = offset + symbolic_link_data['print_name_length']
        result['name'] = (
            symbolic_link_data['data'][offset:ending].decode('utf-16'))

        offset = symbolic_link_data['substitute_name_offset']
        ending = offset + symbolic_link_data['substitute_name_length']
        target_path = (
            symbolic_link_data['data'][offset:ending].decode('utf-16'))
        # Have no idea why we get this magic marker.
        if target_path.startswith('\\??\\'):
            target_path = target_path[4:]
        result['target'] = target_path

        return result
