# Copyright (c) 2011 Adi Roiban.
# See LICENSE for details.
"""
Filesystem helpers for tests.
"""
from __future__ import with_statement
import hashlib
import os
import re
import uuid

from chevah.compat import LocalFilesystem
from chevah.empirical.constants import (
    TEST_NAME_MARKER,
    )


class LocalTestFilesystem(LocalFilesystem):
    '''Testing specific methods for local filesystem.'''

    @property
    def home_path(self):
        '''Return absolute path to home folder.'''
        segments = self.home_segments
        return self.getRealPathFromSegments(segments)

    @property
    def temp_path(self):
        '''Return absolute path to temporary folder.'''
        segments = self.temp_segments
        return self.getRealPathFromSegments(segments)

    def createFile(self, segments, length=0, access_time=None, content=None):
        '''Creates a file.

        Raise AssertionError if file already exists or it can not be created.
        '''
        assert not self.isFile(segments), 'File already exists.'
        new_file = self.openFileForWriting(segments)
        if content is None:
            value = 'a'
            content = ''
            if length > 0:
                assert length > 10, (
                    'Data length must be greater than 10.')
                length = length - 3
                buffer_size = 1024 * 1024
                new_file.write('\r\n')
                while length > 0:
                    length = length - buffer_size
                    if length < 0:
                        buffer_size = buffer_size + length
                    new_file.write(value * buffer_size)
                new_file.write('\n')
        else:
            new_file.write(content.encode('utf-8'))

        new_file.close()
        assert self.isFile(segments), 'Could not create file'

    def createFileInTemp(self, content=None, prefix=u'', suffix=u'',
            length=0):
        '''Create a file in the temporary folder.'''
        temp_segments = self.temp_segments
        # We need a standardized way to generate temporary file names.
        # It's required to use a delayed import in order to avoid a
        # circular import reference as factory uses filesystem.
        from chevah.commons.testing.mockup import factory
        filename = factory.makeFilename(prefix=prefix, suffix=suffix)
        temp_segments.append(filename)
        self.createFile(temp_segments, content=content, length=length)
        return temp_segments

    def makePathInTemp(self):
        """
        Return a (path, segments) that can be created in the temporary folder.
        """
        name = unicode(uuid.uuid1()) + TEST_NAME_MARKER
        segments = self.temp_segments
        segments.append(name)
        path = os.path.join(self.temp_path, name)
        return (path, segments)

    def createFolderInTemp(self, foldername=None):
        """
        Create a folder in the temporary folder.

        Return the segments to the new folder.
        """
        if foldername is None:
            # We add an unicode to the temp filename.
            foldername = unicode(uuid.uuid1()) + TEST_NAME_MARKER

        temp_segments = self.temp_segments

        temp_segments.append(foldername)
        self.createFolder(temp_segments)

        return temp_segments

    def createFileInHome(self, segments=None, **args):
        '''Create a file in home folder.'''
        if segments is None:
            segments = [unicode(uuid.uuid1()) + TEST_NAME_MARKER]

        file_segments = self.home_segments[:]
        file_segments.extend(segments)
        self.createFile(file_segments, **args)
        return file_segments

    def createFolderInHome(self, segments, **args):
        '''Create a folder in home folder.'''
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

            if os.name == 'posix':
                # On Unix it is allowd to clean folder only in these
                # folders.
                if (not (
                        path.startswith('/srv') or
                        path.startswith('/home') or
                        path.startswith('/tmp'),
                        )):
                    return False
            if os.name == 'nt':
                if path == 'c:\\':
                    return False
                # On Windows deny Windows or Program Files.
                if 'Windows' in path:
                    return False
                if 'Program Files' in path:
                    return False
            return True

        if not have_safe_path(path):
            raise AssertionError((
                u'Cleaning the folder "%s" is not allowed.' % (path)
                    ).encode('utf-8'))

        folder_members = self.getFolderContent(segments)
        for member in folder_members:
            member_segments = segments[:]
            member_segments.append(member)
            try:
                if self.isFolder(member_segments):
                    self.deleteFolder(member_segments, recursive=True)
                else:
                    self.deleteFile(member_segments)
            except:
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
                'Not cleaning home folder for a Filesystem with no avatar.')

        segments = self.home_segments
        return self.cleanFolder(segments=segments)

    def getFileSizeInHome(self, segments):
        '''Get file size relative to home folder.'''
        file_segments = self.home_segments[:]
        file_segments.extend(segments)
        return self.getFileSize(file_segments)

    def getFileMD5Sum(self, segments):
        '''Get MD5 checksum.'''
        md5_sum = hashlib.md5()
        chunk_size = 8192
        input_file = self.openFileForReading(segments)
        try:
            for chunk in iter(lambda: input_file.read(chunk_size), ''):
                md5_sum.update(chunk)
        finally:
            input_file.close()
        return md5_sum.digest()

    def getFileMD5SumInHome(self, segments):
        '''Get file MD5 sum relative to home folder.'''
        file_segments = self.home_segments[:]
        file_segments.extend(segments)
        return self.getFileMD5Sum(file_segments)

    def isFileInHome(self, segments):
        '''Get isFile relative to home folder.'''
        file_segments = self.home_segments[:]
        file_segments.extend(segments)
        return self.isFile(file_segments)

    def isFolderInHome(self, segments):
        '''Get isFolder relative to home folder.'''
        file_segments = self.home_segments[:]
        file_segments.extend(segments)
        return self.isFolder(file_segments)

    def existsInHome(self, segments):
        '''Get exists relative to home folder.'''
        file_segments = self.home_segments[:]
        file_segments.extend(segments)
        return self.exists(file_segments)

    def getFileContent(self, segments, utf8=True):
        """
        Return a list with all lines from file.

        By default, the content is returned as Unicode.
        """
        opened_file = self.openFileForReading(segments, utf8=utf8)
        content = []
        try:
            for line in opened_file:
                content.append(line.rstrip())
        finally:
            opened_file.close()

        return content

    def replaceFileContent(self, segments, rules):
        """
        Replace the file content.

        It takes a list for tuples [(pattern1, substitution1), (pat2, sub2)]
        and applies them in order.
        """
        opened_file = self.openFileForReading(segments, utf8=True)
        altered_lines = []
        for line in opened_file:
            new_line = line
            for rule in rules:
                pattern = rule[0]
                substitution = rule[1]
                new_line = re.sub(
                    pattern.encode('utf-8'),
                    substitution.encode('utf-8'),
                    new_line)
            altered_lines.append(new_line)
        opened_file.close()

        opened_file = self.openFileForWriting(segments, utf8=True)
        for line in altered_lines:
            opened_file.write(line)
        opened_file.close()
