# Copyright (c) 2014 Adi Roiban.
# See LICENSE for details.
"""
Filesystem code used by all operating systems, including Windows as
Windows has its layer of POSIX compatibility.
"""
from contextlib import contextmanager
from datetime import date
import errno
import os
import posixpath
import re
import shutil
import stat
import struct
import sys
import time
import unicodedata
import six
from os import scandir

from zope.interface import implementer

from chevah_compat.exceptions import (
    ChangeUserException,
    CompatError,
    CompatException,
    )
from chevah_compat.interfaces import IFileAttributes
from chevah_compat.helpers import _, NoOpContext


_DEFAULT_FOLDER_MODE = 0o777
_DEFAULT_FILE_MODE = 0o600


class PosixFilesystemBase(object):
    """
    Base implementation of ILocalFilesystem for
    local Posix filesystems.

    It handles `raw` access to the filesystem.
    Classed using this base should implement path and segment handling
    """

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

    def __init__(self, avatar):
        self._avatar = avatar
        self._root_path = self._getRootPath()
        self._validateVirtualFolders()

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

    def _pathSplitRecursive(self, path):
        """
        Recursive split of a path.
        """
        if os.path.sep == '\\':
            # We are on Windows.
            # Also handle Unix separators and escape the regex.
            separators = r'[\\/]'
        else:
            separators = '[/]'

        segments = re.split(separators, path)

        if len(segments) > 0:
            segments[0] = segments[0].strip(':')
        return [segment for segment in segments if segment != '']

    @classmethod
    def getEncodedPath(cls, path):
        """
        Return the encoded representation of the path, use in the lower
        lever API for accessing the filesystem.

        This is here from py2 and should be removed in the future.
        On Python 3 the low level API can handle unicode.
        """
        return path

    @property
    def home_segments(self):
        '''See `ILocalFilesystem`.'''

        if not self._avatar:
            return self._pathSplitRecursive(
                six.text_type(os.path.expanduser('~')))

        if self._avatar.root_folder_path is None:
            return self._pathSplitRecursive(self._avatar.home_folder_path)

        home_lower = self._avatar.home_folder_path.lower()
        root_lower = self._avatar.root_folder_path.rstrip('/\\').lower()
        # Check that we have a valid home folder.
        if not home_lower.startswith(root_lower):
            raise CompatError(
                20019,
                _(
                    'User home folder "%s" is not within the root folder '
                    '"%s".' % (
                        self._avatar.home_folder_path,
                        self._avatar.root_folder_path),
                    ),
                )

        path = self._avatar.home_folder_path[len(root_lower):]
        return self._pathSplitRecursive(path)

    def getPath(self, segments):
        """
        See `ILocalFilesystem`.
        """
        if segments == []:
            return u'/'

        normalized_path = posixpath.normpath(u'/'.join(segments))
        return u'/' + u'/'.join(self._pathSplitRecursive(normalized_path))

    def getSegments(self, path):
        """
        See `ILocalFilesystem`.

        Get segment is the place where segments are created and we make sure
        they are in the internal encoding.
        """
        if path is None or path == '' or path == '.':
            return self.home_segments

        if not isinstance(path, six.text_type):
            path = path.decode(self.INTERNAL_ENCODING)

        if not path.startswith('/'):
            # Resolve relative path.
            home_path = u'/' + u'/'.join(self.home_segments) + u'/'
            path = home_path + path

        normalize_path = posixpath.normpath(path)
        return self._pathSplitRecursive(normalize_path)

    @property
    def temp_segments(self):
        '''See `ILocalFilesystem`.'''
        if self.avatar.lock_in_home_folder:
            temporary_folder = os.path.join(
                self.avatar.home_folder_path, '__chevah_test_temp__')
        else:
            # Go with general temporary directory.
            import tempfile
            temporary_folder = tempfile.gettempdir()
        return self.getSegmentsFromRealPath(temporary_folder)

    def getRealPathFromSegments(self, segments, include_virtual=True):
        '''See `ILocalFilesystem`.'''
        raise NotImplementedError('You must implement this method.')

    def _areEqual(self, first, second):
        """
        Return true if first and second segments are for the same path.
        """
        if first == second:
            return True

        from chevah_compat import process_capabilities
        if process_capabilities.os_name not in ['windows', 'osx']:
            # On Linux and Unix we do strict case.
            return False

        # On Windows paths are case insensitive, so we compare based on
        # lowercase.
        # But first try with the same case, in case we have strange
        first = [s.lower() for s in first]
        second = [s.lower() for s in second]
        return first == second

    def _validateVirtualFolders(self):
        """
        Check that virtual folders don't overlap with existing real folders.
        """
        for virtual_segments, real_path in self._avatar.virtual_folders:
            target_segments = virtual_segments[:]
            # Check for the virtual segments, but also for any ancestor.
            while target_segments:
                inside_path = os.path.join(self._root_path, *target_segments)
                encoded_path = self.getEncodedPath(inside_path)
                if not os.path.lexists(encoded_path):
                    target_segments.pop()
                    continue
                virtual_path = '/' + '/'.join(virtual_segments)
                raise CompatError(
                    1005,
                    'Virtual path "%s" overlaps an existing file or '
                    'folder at "%s".' % (virtual_path, inside_path,))

    def _getVirtualPathFromSegments(self, segments, include_virtual):
        """
        Return the virtual path associated with `segments`

        Return None if not found.
        Raise CompatError when `include_virtual` is False and the segments
        are for a virtual path (root or part of it).
        """
        segments_length = len(segments)
        for virtual_segments, real_path in self._avatar.virtual_folders:
            if segments_length < len(virtual_segments):
                # Not the virtual folder of a descended of it.
                if (
                    not include_virtual and
                    self._areEqual(
                        segments, virtual_segments[:segments_length])
                        ):
                    # But this is a parent of a virtual segment and we
                    # don't allow that.
                    raise CompatError(
                        1007, 'Modifying a virtual path is not allowed.')

                continue

            if (
                not include_virtual and
                self._areEqual(segments, virtual_segments)
                    ):
                # This is a virtual root, but we don't allow it.
                raise CompatError(
                    1007, 'Modifying a virtual path is not allowed.')

            base_segments = segments[:len(virtual_segments)]
            if not self._areEqual(base_segments, virtual_segments):
                # Base does not match
                continue

            tail_segments = segments[len(virtual_segments):]
            return os.path.join(real_path, *tail_segments)

        # At this point we don't have a match for a virtual folder, but
        # we should check that ancestors are not virtual as we don't
        # want to create files in the middle of a virtual path.
        parent = segments[:-1]
        if not include_virtual and parent:
            # Make sure parent is not a virtual path.
            self._getVirtualPathFromSegments(parent, include_virtual=False)

        # No virtual path found for segments.
        return None

    def _isVirtualPath(self, segments):
        """
        Return True if segments are a part or a full virtual folder.

        Return False when they are a descendant of a virtual folder.
        """
        if not segments:
            return False

        partial_virtual = False
        segments_length = len(segments)

        # Part of virtual paths, virtually exists.
        for virtual_segments, real_path in self._avatar.virtual_folders:
            # Any segment which does start the same way as a virtual path is
            # normal path
            if not self._areEqual(segments[0:1], virtual_segments[0:1]):
                # No match
                continue

            if self._areEqual(segments, virtual_segments[:segments_length]):
                # This is the root of a virtual path or a sub-part of it.
                return True

            # If it looks like a virtual path, but is not a full match, then
            # this is a broken path.
            partial_virtual = True

            if not self._areEqual(
                    virtual_segments, segments[:len(virtual_segments)]):
                # This is not a mapping for this virtual path.
                continue

            # Segments are the direct
            partial_virtual = False

            if segments_length > len(virtual_segments):
                # Is longer than the virtual path so it can't be part of the
                # full virtual path.
                return False

            # This is a virtual path which has a mapping.
            return True

        if partial_virtual:
            raise CompatError(1004, 'Broken virtual path.')

        return False

    def getSegmentsFromRealPath(self, path):
        '''See `ILocalFilesystem`.'''
        raise NotImplementedError('You must implement this method.')

    def getAbsoluteRealPath(self, path):
        """
        See `ILocalFilesystem`.
        """
        absolute_path = os.path.abspath(self.getEncodedPath(path))
        if not isinstance(absolute_path, six.text_type):
            absolute_path = absolute_path.decode(self.INTERNAL_ENCODING)

        return absolute_path

    def isAbsolutePath(self, path):
        """
        See `ILocalFilesystem`.
        """
        return os.path.isabs(path)

    def isFolder(self, segments):
        """
        See `ILocalFilesystem`.
        """
        try:
            return self.getAttributes(segments).is_folder
        except OSError:
            # On any error, we consider it not a folder.
            return False

    def isFile(self, segments):
        '''See `ILocalFilesystem`.'''
        try:
            return self.getAttributes(segments).is_file
        except OSError:
            return False

    def isLink(self, segments):
        """
        See `ILocalFilesystem`.
        """
        raise NotImplementedError()

    def exists(self, segments):
        '''See `ILocalFilesystem`.'''

        try:
            if self._isVirtualPath(segments):
                return True
            else:
                """
                Let the normal code to check the existence.
                """
        except CompatError:
            # A broken virtual path does not exits.
            return False

        path = self.getRealPathFromSegments(segments)
        path_encoded = self.getEncodedPath(path)
        with self._impersonateUser():
            return os.path.lexists(path_encoded)

    def createFolder(self, segments, recursive=False):
        '''See `ILocalFilesystem`.'''
        path = self.getRealPathFromSegments(segments, include_virtual=False)
        path_encoded = self.getEncodedPath(path)
        with self._impersonateUser():
            if recursive:
                return os.makedirs(path_encoded, _DEFAULT_FOLDER_MODE)
            else:
                return os.mkdir(path_encoded, _DEFAULT_FOLDER_MODE)

    def deleteFolder(self, segments, recursive=True):
        """
        See `ILocalFilesystem`.
        """
        raise NotImplementedError('deleteFolder not implemented.')

    def _rmtree(self, path):
        """
        Remove whole directory tree.
        """
        def on_error(func, path, exception_info):
            """
            Error handler for ``shutil.rmtree``.

            If the error is due to an access error on Windows (ex,
            read only file) it attempts to add write permission and then
            retries.

            If the error is for another reason it re-raises the error.
            """
            if os.name != 'nt':
                raise

            if (
                func in (os.rmdir, os.remove) and
                exception_info[1].errno == errno.EACCES
                    ):
                os.chmod(
                    path,
                    stat.S_IWUSR | stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO,
                    )
                func(path)
            else:
                raise

        shutil.rmtree(path, ignore_errors=False, onerror=on_error)

    def deleteFile(self, segments, ignore_errors=False):
        """
        See: `ILocalFilesystem`.
        """
        path = self.getRealPathFromSegments(segments, include_virtual=False)
        path_encoded = self.getEncodedPath(path)
        with self._impersonateUser():
            try:
                try:
                    return os.unlink(path_encoded)
                except OSError as error:
                    # This is done to allow lazy initialization of this module.
                    from chevah_compat import process_capabilities

                    # On Unix (AIX, Solaris) when segments is a folder,
                    # we get EPERM, so we force a EISDIR.
                    # For now, Unix is everything else, other than Linux.
                    if process_capabilities.os_name != 'linux':
                        self._requireFile(segments)

                    # On Windows we might get an permissions error when
                    # file is ready-only.
                    if (
                        process_capabilities.os_name == 'windows' and
                        error.errno == errno.EACCES
                            ):
                        os.chmod(path_encoded, stat.S_IWRITE)
                        return os.unlink(path_encoded)

                    raise error
            except Exception:
                if ignore_errors:
                    return
                raise

    def rename(self, from_segments, to_segments):
        '''See `ILocalFilesystem`.'''
        from_path = self.getRealPathFromSegments(
            from_segments, include_virtual=False)
        to_path = self.getRealPathFromSegments(
            to_segments, include_virtual=False)

        from_path_encoded = self.getEncodedPath(from_path)
        to_path_encoded = self.getEncodedPath(to_path)
        with self._impersonateUser():
            return os.rename(from_path_encoded, to_path_encoded)

    @contextmanager
    def _convertToOSError(self, path):
        """
        Convert the errors raised to OSError... if possible.
        """
        try:
            yield
        except EnvironmentError as error:
            if not error.filename:
                error.filename = self.getEncodedPath(path)
            raise OSError(
                error.errno,
                error.strerror,
                error.filename,
                )

    def _requireFile(self, segments):
        """
        Raise an OSError when segments is not a file.
        """
        path = self.getRealPathFromSegments(segments)
        if self.isFolder(segments):
            raise OSError(
                errno.EISDIR,
                'Is a directory: %s' % path,
                path,
                )

    def openFile(self, segments, flags, mode):
        '''See `ILocalFilesystem`.'''
        path = self.getRealPathFromSegments(segments, include_virtual=False)
        path_encoded = self.getEncodedPath(path)

        self._requireFile(segments)
        with self._convertToOSError(path), self._impersonateUser():
            return os.open(path_encoded, flags, mode)

    def openFileForReading(self, segments):
        '''See `ILocalFilesystem`.'''
        path = self.getRealPathFromSegments(segments, include_virtual=False)
        path_encoded = self.getEncodedPath(path)

        self._requireFile(segments)
        with self._convertToOSError(path), self._impersonateUser():
            fd = os.open(
                path_encoded,
                self.OPEN_READ_ONLY,
                )
            return os.fdopen(fd, 'rb')

    def openFileForWriting(self, segments, mode=_DEFAULT_FILE_MODE):
        """
        See `ILocalFilesystem`.

        For security reasons, the file is only opened with read/write for
        owner.
        """
        path = self.getRealPathFromSegments(segments, include_virtual=False)
        path_encoded = self.getEncodedPath(path)

        self._requireFile(segments)
        with self._convertToOSError(path), self._impersonateUser():
            fd = os.open(
                path_encoded,
                (self.OPEN_WRITE_ONLY | self.OPEN_CREATE |
                    self.OPEN_TRUNCATE),
                mode)
            return os.fdopen(fd, 'wb')

    def openFileForAppending(self, segments, mode=_DEFAULT_FILE_MODE):
        '''See `ILocalFilesystem`.'''
        def fail_on_read():
            raise AssertionError(
                'File opened for appending. Read is not allowed.')
        path = self.getRealPathFromSegments(segments, include_virtual=False)
        path_encoded = self.getEncodedPath(path)

        self._requireFile(segments)
        with self._convertToOSError(path), self._impersonateUser():
            fd = os.open(
                path_encoded,
                (self.OPEN_APPEND | self.OPEN_CREATE |
                    self.OPEN_WRITE_ONLY),
                mode)
            new_file = os.fdopen(fd, 'ab')
            return new_file

    def getFileSize(self, segments):
        '''See `ILocalFilesystem`.'''
        if self._isVirtualPath(segments):
            # Virtual path are non-existent in real filesystem but we return
            # a value instead of file not found.
            return 0

        path = self.getRealPathFromSegments(segments)
        path_encoded = self.getEncodedPath(path)
        with self._impersonateUser():
            return os.path.getsize(path_encoded)

    def _getVirtualMembers(self, segments):
        """
        Return a list with virtual folders which are children of `segments`.
        """
        result = []
        segments_length = len(segments)
        for virtual_segments, real_path in self._avatar.virtual_folders:
            if segments_length >= len(virtual_segments):
                # Not something that might look like the parent of a
                # virtual folder.
                continue

            if not self._areEqual(
                    virtual_segments[:segments_length], segments):
                continue

            child_segments = virtual_segments[segments_length:]

            result.append(child_segments[0])

        # Reduce duplicates and convert to attributes..
        return [
            self._getPlaceholderAttributes(segments + [m])
            for m in set(result)
            ]

    def getFolderContent(self, segments):
        """
        See `ILocalFilesystem`.
        """
        result = [m.name for m in self._getVirtualMembers(segments)]
        if segments and result:
            # We only support mixing virtual folder names with real names
            # for the root folder.
            # For all the other paths, we ignore the real folders if they
            # overlay a virtual path.
            return result

        path = self.getRealPathFromSegments(segments)
        path_encoded = self.getEncodedPath(path)

        try:
            with self._impersonateUser():
                for entry in os.listdir(path_encoded):
                    name = self._decodeFilename(entry)
                    if name in result:
                        continue
                    result.append(name)
        except Exception as error:
            if not result:
                raise error

        return result

    def iterateFolderContent(self, segments):
        """
        See `ILocalFilesystem`.
        """
        path = self.getRealPathFromSegments(segments)
        path_encoded = self.getEncodedPath(path)

        virtual_members = self._getVirtualMembers(segments)
        if segments and virtual_members:
            # We only support mixing virtual folder names with real names
            # for the root folder.
            # For all the other paths, we ignore the real folders if they
            # overlay a virtual path.
            return iter(virtual_members)

        # We start with possible virtual folders as they should shadow the
        # real folders.
        firsts = virtual_members
        try:
            with self._impersonateUser():
                folder_iterator = scandir(path_encoded)

            # On Windows we need to iterate over the first element to get the
            # errors.
            # Otherwise just by opening the directory, we don't get any errors.
            # This is why we try to extract the first element, and yield it
            # later.
            try:
                first_member = next(folder_iterator)
            except StopIteration:
                # The folder is empty so just return an iterator with possible
                # virtual members.
                return iter(virtual_members)

            real_first_attributes = self._dirEntryToFileAttributes(
                first_member)
            first_names = [m.name for m in firsts]
            if real_first_attributes.name not in first_names:
                firsts.append(real_first_attributes)

        except Exception as error:
            # We fail to list the actual folder.
            if not virtual_members:
                # Since there are no virtual folder, we just raise the error.
                raise error

            # We have virtual folders.
            # No direct listing.
            folder_iterator = iter([])

        return self._iterateScandir(set(firsts), folder_iterator)

    def _iterateScandir(self, firsts, folder_iterator):
        """
        This generator wrapper needs to be delegated to this method as
        otherwise we get a GeneratorExit error.

        `firsts` is a list of FileAttributes.
        `folder_iterators` is the iterator resulted from scandir.
        """
        first_names = []
        for member in firsts:
            first_names.append(member.name)
            yield member

        for entry in folder_iterator:
            attributes = self._dirEntryToFileAttributes(entry)
            if attributes.name in first_names:
                # Make sure we don't add duplicate from previous
                # virtual folders.
                continue
            yield attributes

    def _dirEntryToFileAttributes(self, entry):
        """
        Convert the result from scandir to FileAttributes.
        """
        name = self._decodeFilename(entry.name)
        path = self._decodeFilename(entry.path)

        with self._impersonateUser():
            stats = entry.stat(follow_symlinks=False)
            is_link = entry.is_symlink()

        mode = stats.st_mode
        is_directory = bool(stat.S_ISDIR(mode))
        if is_directory and sys.platform.startswith('aix'):
            # On AIX mode contains an extra most significant bit
            # which we don't use.
            mode = mode & 0o077777

        # We use the INODE from stats, as on Windows getting INODE from
        # scandir result is slow.
        inode = stats.st_ino

        modified = stats.st_mtime
        if os.name == 'nt':
            # On Windows, scandir gets float precision while
            # getAttributes only integer.
            modified = int(modified)
            # On Windows, path might have long names for local drives.
            # For compat, we keep the simple format as the end user format.
            if path.startswith('\\\\?\\') and path[5] == ':':
                path = path[4:]

        hardlinks = stats.st_nlink
        if not hardlinks and os.name == 'nt':
            # I don't know why on Windows we doing scandir.
            hardlinks = 1

        return FileAttributes(
            name=name,
            path=path,
            size=stats.st_size,
            is_file=bool(stat.S_ISREG(mode)),
            is_folder=is_directory,
            is_link=is_link,
            modified=modified,
            mode=mode,
            hardlinks=hardlinks,
            uid=stats.st_uid,
            gid=stats.st_gid,
            node_id=inode,
            )

    def _decodeFilename(self, name):
        """
        Return the Unicode representation of file from `name`.

        `name` is in the encoded format stored on the filesystem.
        """
        # This is done to allow lazy initialization of process_capabilities.
        from chevah_compat import process_capabilities
        if not isinstance(name, six.text_type):
            name = name.decode(self.INTERNAL_ENCODING)

        # OSX HFS+ store file as Unicode, but in normalized format.
        # On OSX we might also read files from other filesystems, not only
        # HFS+, but we are lucky here as normalize will not raise errors
        # if input is already normalized.
        if process_capabilities.os_name == 'osx':
            name = unicodedata.normalize('NFC', name)

        return name

    def getAttributes(self, segments):
        """
        See `ILocalFilesystem`.
        """
        if self._isVirtualPath(segments):
            return self._getPlaceholderAttributes(segments)

        stats = self.getStatus(segments)
        mode = stats.st_mode
        is_directory = bool(stat.S_ISDIR(mode))
        if is_directory and sys.platform.startswith('aix'):
            # On AIX mode contains an extra most significant bit
            # which we don't use.
            mode = mode & 0o077777

        try:
            name = segments[-1]
        except Exception:
            name = None
        path = self.getRealPathFromSegments(segments)

        return FileAttributes(
            name=name,
            path=path,
            size=stats.st_size,
            is_file=bool(stat.S_ISREG(mode)),
            is_folder=is_directory,
            is_link=self.isLink(segments),
            modified=stats.st_mtime,
            mode=mode,
            hardlinks=stats.st_nlink,
            uid=stats.st_uid,
            gid=stats.st_gid,
            node_id=stats.st_ino,
            )

    def _getPlaceholderAttributes(self, segments):
        """
        Return the attributes which can be used for the case when a real
        attribute don't exists for `segments`.
        """
        modified = time.mktime((
            date.today().year,
            1,
            1,
            0,
            0,
            0,
            0,
            0,
            -1,
            ))
        return FileAttributes(
            name=segments[-1],
            path=self.getRealPathFromSegments(segments),
            size=0,
            is_file=False,
            is_folder=True,
            is_link=False,
            modified=modified,
            mode=0o40555,
            hardlinks=1,
            uid=1,
            gid=1,
            node_id=None,
            )

    def _getPlaceholderStatus(self):
        """
        Return a placeholder status result.
        """
        modified = time.mktime((
            date.today().year,
            1,
            1,
            0,
            0,
            0,
            0,
            0,
            -1,
            ))

        return os.stat_result([
            0o40555, 0, 0, 0, 1, 1, 0, 1, modified, 0])

    def setAttributes(self, segments, attributes):
        '''See `ILocalFilesystem`.'''
        path = self.getRealPathFromSegments(segments, include_virtual=False)
        path_encoded = self.getEncodedPath(path)
        with self._impersonateUser():
            if 'uid' in attributes and 'gid' in attributes:
                os.chown(path_encoded, attributes['uid'], attributes['gid'])
            if 'mode' in attributes:
                os.chmod(path_encoded, attributes['mode'])
            if 'atime' in attributes and 'mtime' in attributes:
                os.utime(
                    path_encoded, (attributes['atime'], attributes['mtime']))

    def touch(self, segments):
        """
        See: ILocalFilesystem.
        """
        path = self.getRealPathFromSegments(segments, include_virtual=False)
        path_encoded = self.getEncodedPath(path)
        with self._impersonateUser():
            with open(path_encoded, 'a'):
                os.utime(path_encoded, None)

    def copyFile(self, source_segments, destination_segments, overwrite=False):
        """
        See: ILocalFilesystem.
        """
        if self.isFolder(destination_segments):
            destination_segments = destination_segments[:]
            destination_segments.append(source_segments[-1])

        destination_path = self.getRealPathFromSegments(
            destination_segments, include_virtual=False)
        destination_path_encoded = self.getEncodedPath(destination_path)

        if not overwrite and self.exists(destination_segments):
            raise OSError(
                errno.EEXIST, 'Destination exists', destination_path_encoded)

        source_path = self.getRealPathFromSegments(
            source_segments, include_virtual=False)
        source_path_encoded = self.getEncodedPath(source_path)

        with self._impersonateUser():
            shutil.copyfile(
                source_path_encoded, destination_path_encoded)

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
        child_strip = self.getAbsoluteRealPath(child)
        root_strip = self.getAbsoluteRealPath(root)

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

        # Have no idea why we get this marker, but we convert it to
        # long UNC.
        if target_path.startswith('\\??\\'):
            target_path = '\\\\?' + target_path[3:]
        result['target'] = target_path

        return result


@implementer(IFileAttributes)
class FileAttributes(object):
    """
    See: IFileAttributes.
    """

    def __init__(
            self, name, path, size=0,
            is_file=False, is_folder=False, is_link=False,
            modified=0,
            mode=0, hardlinks=1,
            uid=None, gid=None,
            owner=None, group=None,
            node_id=None,
            ):
        self.name = name
        self.path = path
        self.size = size
        self.is_folder = is_folder
        self.is_file = is_file
        self.is_link = is_link
        self.modified = modified

        self.mode = mode
        self.hardlinks = hardlinks
        self.uid = uid
        self.gid = gid
        self.node_id = node_id
        self.owner = owner
        self.group = group

    def __hash__(self):
        return hash((
            self.name,
            self.path,
            self.size,
            self.is_folder,
            self.is_file,
            self.is_link,
            self.modified,
            self.mode,
            self.hardlinks,
            self.uid,
            self.gid,
            self.node_id,
            self.owner,
            self.group,
            ))

    def __eq__(self, other):
        return (
            isinstance(other, self.__class__) and
            self.__dict__ == other.__dict__
            )

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return u"%s:%s:%s" % (self.__class__, id(self), self.__dict__)
