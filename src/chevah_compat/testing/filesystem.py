# Copyright (c) 2011 Adi Roiban.
# See LICENSE for details.
"""
Filesystem helpers for tests.
"""

import os
import re
import tempfile
import uuid

import six

from chevah_compat import LocalFilesystem
from chevah_compat.testing.constant import TEST_NAME_MARKER


class LocalTestFilesystem(LocalFilesystem):
    """
    A local filesystem designed to support testing.
    """

    __temporary_folders__ = []

    def __init__(self, avatar=None):
        """
        Create an unique temp folder.
        """
        super().__init__(avatar=avatar)
        self._temp_uuid = '{}{}{}'.format(
            'long-name-' * 25,
            uuid.uuid4(),
            TEST_NAME_MARKER,
        )
        # Make sure we keep the directory below 255.
        # This is the limit for a single filename in Windows and ext4.
        # Any file created inside will have a longer path.
        self._temp_uuid = self._temp_uuid[-254:]
        self.__class__.__temporary_folders__.append(self.temp_segments)

    @property
    def temp_segments(self):
        """
        Return the segments for the temporary folder.
        """
        temp_segments = LocalFilesystem.temp_segments.fget(self)[:]
        temp_segments.append(self._temp_uuid)
        return temp_segments

    @classmethod
    def getAllTemporaryFolders(cls):
        """
        Return a list with all created temporary folders.
        """
        return cls.__temporary_folders__[:]

    def checkCleanTemporaryFolders(self):
        """
        Check that no previously created temporary folder exists.
        """
        remaining_folders = []
        for temp in self.getAllTemporaryFolders():
            if self.exists(temp):
                remaining_folders.append(temp)
                self.deleteFolder(temp, recursive=True)

        if remaining_folders:
            raise AssertionError(
                f'Not all temporary folders were cleaned: {remaining_folders}',
            )

    def setUpTemporaryFolder(self):
        """
        Create temporary folder.
        """
        if self.exists(self.temp_segments):
            self.deleteFolder(self.temp_segments, recursive=True)
            raise AssertionError(
                f'Temporary folder already exists at: {self.temp_segments}',
            )

        self.createFolder(self.temp_segments)

    def tearDownTemporaryFolder(self):
        """
        Remove temporary folder.
        """
        if self.exists(self.temp_segments):
            self.deleteFolder(self.temp_segments, recursive=True)

    @property
    def home_path(self):
        """
        Return absolute path to home folder.
        """
        segments = self.home_segments
        return self.getRealPathFromSegments(segments)

    @property
    def temp_path(self):
        """
        Return absolute path to temporary folder.
        """
        segments = self.temp_segments
        return self.getRealPathFromSegments(segments)

    def createFile(
        self,
        segments,
        length=0,
        access_time=None,
        content=None,
        mode=0o666,
    ):
        """Creates a file.

        Raise AssertionError if file already exists or it can not be created.
        """
        if isinstance(content, six.text_type):
            content = content.encode('utf-8')
        assert not self.isFile(segments), 'File already exists.'
        new_file = self.openFileForWriting(segments, mode=mode)
        if content is None:
            value = b'a'
            if length > 0:
                assert length > 10, 'Data length must be greater than 10.'
                length = length - 3
                buffer_size = 1024 * 1024
                new_file.write(b'\r\n')
                while length > 0:
                    length = length - buffer_size
                    if length < 0:
                        buffer_size = buffer_size + length
                    new_file.write(value * buffer_size)
                new_file.write(b'\n')
        else:
            new_file.write(content)

        new_file.close()
        assert self.isFile(segments), 'Could not create file'

    def createFileInTemp(self, content=None, prefix='', suffix='', length=0):
        """
        Create a file in the temporary folder.

        `content` is Unicode str.
        """
        temp_segments = self.temp_segments

        filename = self._makeFilename(prefix=prefix, suffix=suffix)
        temp_segments.append(filename)
        self.createFile(temp_segments, content=content, length=length)
        return temp_segments

    def writeFileContent(self, segments, content):
        """
        Write content into file replacing existing content.
        """
        opened_file = self.openFileForWriting(segments)
        opened_file.write(content.encode('utf-8'))
        opened_file.close()

    def _makeFilename(self, prefix='', suffix=''):
        """
        Return a testing filename.
        """
        # It's required to use a delayed import in order to avoid a
        # circular import reference as factory uses filesystem.
        from chevah_compat.testing import mk

        return mk.makeFilename(prefix=prefix, suffix=suffix)

    def makePathInTemp(self, prefix='', suffix=''):
        """
        Return a (path, segments) that can be created in the temporary folder.
        """
        name = self._makeFilename(prefix=prefix, suffix=suffix)
        segments = self.temp_segments
        segments.append(name)
        path = os.path.join(self.temp_path, name)
        return (path, segments)

    def pathInTemp(self, cleanup, prefix='', suffix=''):
        """
        Return a path and segments pointing to a temp location, which will be
        cleaned up.
        """

        def delete(segments):
            if self.isFolder(segments):
                self.deleteFolder(segments, recursive=True)
            else:
                self.deleteFile(segments)

        path, segments = self.makePathInTemp()
        if cleanup:
            cleanup(delete, segments)
        return path, segments

    def folder(self, segments, cleanup):
        """
        Create a folder and remove it a cleanup.
        """
        self.createFolder(segments)
        cleanup(self.deleteFolder, segments, recursive=True)

    def folderInTemp(self, cleanup, *args, **kwargs):
        """
        Create a folder in the temp folder and add to be removed at cleanup.
        """
        segments = self.createFolderInTemp(*args, **kwargs)
        cleanup(self.deleteFolder, segments, recursive=True)
        return segments

    def fileInTemp(self, cleanup, *args, **kwargs):
        """
        Create a file in the temp folder and add to be removed at cleanup.
        """
        segments = self.createFileInTemp(*args, **kwargs)
        cleanup(self.deleteFile, segments)
        return segments

    def createFolderInTemp(self, foldername=None, prefix='', suffix=''):
        """
        Create a folder in the temporary folder.

        Return the segments to the new folder.
        """
        if foldername is None:
            # We add an unicode to the temp filename.
            foldername = self._makeFilename(prefix=prefix, suffix=suffix)

        temp_segments = self.temp_segments + [foldername]

        self.createFolder(temp_segments)

        return temp_segments

    def createFileInHome(self, segments=None, **args):
        """Create a file in home folder."""
        if segments is None:
            segments = [six.text_type(uuid.uuid1()) + TEST_NAME_MARKER]

        file_segments = self.home_segments[:]
        file_segments.extend(segments)
        self.createFile(file_segments, **args)
        return file_segments

    def createFolderInHome(self, segments, **args):
        """Create a folder in home folder."""
        folder_segments = self.home_segments[:]
        folder_segments.extend(segments)
        self.createFolder(folder_segments, *args)
        return folder_segments

    def cleanFolder(self, segments):
        """
        Delete all folder content.
        """
        path = self.getRealPathFromSegments(segments)

        def have_safe_path(path):
            """
            Return True if path is safe to be cleared.
            """
            if path == '/':
                return False

            if tempfile.tempdir and path.startswith(tempfile.tempdir):
                # Allow cleaning default Python temporary directories.
                return True

            if path.startswith(os.environ.get('RUNNER_WORKSPACE', '/tmp/')):
                # Allow cleaning GitHub Actions work directories.
                return True

            if os.name == 'posix':
                # On Unix it is allowed to clean folder only in these
                # folders.

                if path.startswith(('/srv', '/home', '/tmp')):
                    return True

                return False

            # We are on Windows.
            if path == 'c:\\':
                # Deny direct Windows root folder.
                return False

            # Allow the windows temp.
            if path.lower().startswith('c:\\windows\\temp'):
                return True

            # On Windows deny Windows or Program Files.
            if 'Windows' in path:
                return False

            if 'Program Files' in path:
                return False

            return True

        if not have_safe_path(path):
            message = f'Cleaning the folder "{path}" is not allowed.'
            raise AssertionError(message.encode('utf-8'))

        folder_members = self.getFolderContent(segments)
        for member in folder_members:
            member_segments = segments[:]
            member_segments.append(member)
            try:
                if self.isFolder(member_segments):
                    self.deleteFolder(member_segments, recursive=True)
                else:
                    self.deleteFile(member_segments)
            except Exception:
                # Ignore file permissions errors...
                # Just let them live for now. Hope they will not
                # bite us later.
                pass

    def cleanHomeFolder(self):
        """
        Clean home folder.
        """
        if not self._avatar:
            raise AssertionError(
                'Not cleaning home folder for a Filesystem with no avatar.',
            )

        segments = self.home_segments
        return self.cleanFolder(segments=segments)

    def getFileSizeInHome(self, segments):
        """Get file size relative to home folder."""
        file_segments = self.home_segments[:]
        file_segments.extend(segments)
        return self.getFileSize(file_segments)

    def getFileSizeInTemporary(self, segments):
        """
        Get file size relative to temporary folder.
        """
        file_segments = self.temp_segments[:]
        file_segments.extend(segments)
        return self.getFileSize(file_segments)

    def isFileInHome(self, segments):
        """Get isFile relative to home folder."""
        file_segments = self.home_segments[:]
        file_segments.extend(segments)
        return self.isFile(file_segments)

    def isFolderInHome(self, segments):
        """Get isFolder relative to home folder."""
        file_segments = self.home_segments[:]
        file_segments.extend(segments)
        return self.isFolder(file_segments)

    def existsInHome(self, segments):
        """Get exists relative to home folder."""
        file_segments = self.home_segments[:]
        file_segments.extend(segments)
        return self.exists(file_segments)

    def getFileContent(self, segments, utf8=True):
        """
        Return the content of file.

        By default, the content is returned as Unicode.
        """
        opened_file = self.openFileForReading(segments)
        result = opened_file.read()
        opened_file.close()

        if utf8:
            return result.decode('utf-8')

        return result

    def replaceFileContent(self, segments, rules):
        """
        Replace the file content.

        It takes a list for tuples [(pattern1, substitution1), (pat2, sub2)]
        and applies them in order.
        """
        opened_file = self.openFileForReading(segments)
        altered_lines = []
        for line in opened_file:
            new_line = line
            for rule in rules:
                pattern = rule[0]
                substitution = rule[1]
                new_line = re.sub(
                    pattern.encode('utf-8'),
                    substitution.encode('utf-8'),
                    new_line,
                )
            altered_lines.append(new_line)
        opened_file.close()

        opened_file = self.openFileForWriting(segments)
        for line in altered_lines:
            opened_file.write(line)
        opened_file.close()
