# Copyright (c) 2010 Adi Roiban.
# See LICENSE for details.
"""
Tests for portable filesystem access.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from six import text_type

import errno
import os
import platform
import stat
import sys
import tempfile
import time

from chevah.compat import DefaultAvatar, FileAttributes, LocalFilesystem
from chevah.compat.exceptions import CompatError
from chevah.compat.interfaces import IFileAttributes, ILocalFilesystem
from chevah.compat.testing import CompatTestCase, conditionals, mk


class FilesystemTestMixin(object):
    """
    Common code for filesystem tests.
    """

    def makeLink(self, segments, cleanup=True):
        """
        Create a symbolic link to `segments` and return the segments for it.
        """
        link_segments = segments[:]
        link_segments[-1] = '%s-link' % segments[-1]
        mk.fs.makeLink(
            target_segments=segments,
            link_segments=link_segments,
            )
        if cleanup:
            self.addCleanup(mk.fs.deleteFile, link_segments)
        return link_segments

    def test_getSegments_upper_paths(self):
        """
        It will properly remove parent folder (..) and root folder (.) in
        relative and absolute paths.
        """
        segments = self.filesystem.getSegments(u'../a/b')
        self.assertEqual([u'a', u'b'], segments)

        segments = self.filesystem.getSegments(u'/../a/b')
        self.assertEqual([u'a', u'b'], segments)

        segments = self.filesystem.getSegments(u'//../a/b')
        self.assertEqual([u'a', u'b'], segments)

        segments = self.filesystem.getSegments(u'./a/b')
        self.assertEqual([u'a', u'b'], segments)

        segments = self.filesystem.getSegments(u'/./a/b')
        self.assertEqual([u'a', u'b'], segments)

        segments = self.filesystem.getSegments(u'//./a/b')
        self.assertEqual([u'a', u'b'], segments)

    def test_getPath_empty(self):
        """
        It will return `/` when segments are empty.
        """
        result = self.filesystem.getPath([])
        self.assertEqual(u'/', result)

    def test_getPath(self):
        """
        It will convert the segments to a `ChevahPath`.
        """
        path = self.filesystem.getPath([u'a', u'b'])
        self.assertEqual(u'/a/b', path)

        path = self.filesystem.getPath([u'.', 'a', u'b'])
        self.assertEqual(u'/a/b', path)

    def test_getPath_upper_paths(self):
        """
        It will convert segments that have root and parent folder references to
        a `ChevahPath`.
        """
        path = self.filesystem.getPath([u'a', u'.', u'b'])
        self.assertEqual(u'/a/b', path)

        path = self.filesystem.getPath([u'..', u'..', 'a', u'b'])
        self.assertEqual(u'/../../a/b', path)

        # Fix relative segments handling when multiple parent folder references
        # are present.
        path = self.filesystem.getPath([u'a', u'..', u'..', u'b', u'c'])
        self.assertEqual(u'/../b/c', path)

        path = self.filesystem.getPath([u'a', u'..', u'b', u'..', u'c'])
        self.assertEqual(u'/c', path)


class TestLocalFilesystem(CompatTestCase, FilesystemTestMixin):
    """
    Test for default local filesystem which does not depend on attached
    avatar or operating system.
    """

    @classmethod
    def setUpClass(cls):
        super(TestLocalFilesystem, cls).setUpClass()
        cls.filesystem = LocalFilesystem(avatar=DefaultAvatar())

    def createFolderWithChild(self):
        """
        Create a folder with a child returning a tuple with segment for new
        folder and name of child.
        """
        child_name = mk.makeFilename()
        segments = mk.fs.createFolderInTemp()
        child_segments = segments[:]
        child_segments.append(child_name)
        mk.fs.createFolder(child_segments)
        return (segments, child_name)

    def test_interface_implementation(self):
        """
        Checks that it implements the interface.
        """
        self.assertProvides(ILocalFilesystem, self.filesystem)

    def test_home_segments(self):
        """
        Check that home_segment property is defined.
        """
        segments = self.filesystem.home_segments
        self.assertIsNotNone(segments)

    def test_temp_segments(self):
        """
        Check that temp segment is a folder.
        """
        segments = self.filesystem.temp_segments
        self.assertTrue(self.filesystem.isFolder(segments))

    @conditionals.onOSFamily('posix')
    def test_temp_segments_location_unix(self):
        """
        On unix the temporary folders are located inside the temp folder.
        """
        if self.os_name == 'osx':
            expected = self.filesystem.getSegmentsFromRealPath(
                tempfile.gettempdir())
        else:
            expected = [u'tmp']
        self.assertEqual(expected, self.filesystem.temp_segments)

    def test_temp_segments_location_nt(self):
        """
        On Windows for non impersonated account, the temporary folder
        is located inside the user temporary folder and not on c:\temp.
        """
        if os.name != 'nt':
            raise self.skipTest()

        self.assertNotEqual(
            [u'c', u'temp'], self.filesystem.temp_segments[0:2])

    def test_temp_segments_writeable(self):
        """
        The temporary folder must allow creation of any files with writeable
        permissions.
        """
        segments = self.filesystem.temp_segments
        filename = mk.makeFilename()
        segments.append(filename)

        test_content = mk.getUniqueString()
        mk.fs.createFile(segments, content=test_content)

        self.assertIsTrue(self.filesystem.isFile(segments))
        mk.fs.deleteFile(segments)

    def test_installation_segments(self):
        """
        Installation segments is the base installation path.
        """
        segments = self.filesystem.installation_segments
        self.assertTrue(mk.fs.isFolder(segments))
        folder_name = segments[-1]
        self.assertTrue(folder_name.startswith('build-'))

    def test_IOToOSError(self):
        """
        Convert IOError to OSError using a context.
        """
        path = mk.string()
        message = mk.string()

        with self.assertRaises(OSError) as context:
            with self.filesystem._IOToOSError(path):
                raise IOError(3, message)

        self.assertEqual(3, context.exception.errno)
        self.assertEqual(path.encode('utf-8'), context.exception.filename)
        self.assertEqual(message.encode('utf-8'), context.exception.strerror)

    def test_deleteFile_folder(self):
        """
        Raise OSError when trying to delete a folder as a file.
        """
        self.test_segments = mk.fs.createFolderInTemp()
        path = mk.fs.getRealPathFromSegments(self.test_segments)
        self.assertTrue(self.filesystem.exists(self.test_segments))

        with self.assertRaises(OSError) as context:
            self.filesystem.deleteFile(self.test_segments)

        self.assertEqual(errno.EISDIR, context.exception.errno)
        self.assertEqual(path.encode('utf-8'), context.exception.filename)
        self.assertTrue(self.filesystem.exists(self.test_segments))

    def test_deleteFile_regular(self):
        """
        It can delete a regular file.
        """
        segments = mk.fs.createFileInTemp()
        self.assertTrue(self.filesystem.exists(segments))

        self.filesystem.deleteFile(segments)

        self.assertFalse(self.filesystem.exists(segments))

    def test_deleteFile_not_found(self):
        """
        Return OSError with errno.ENOENT.
        """
        segments = ['c', mk.string()]

        with self.assertRaises(OSError) as context:
            self.filesystem.deleteFile(segments)

        self.assertEqual(errno.ENOENT, context.exception.errno)

    @conditionals.onCapability('symbolic_link', True)
    def test_deleteFile_file_link(self):
        """
        It can delete a symlink to a file and original file is not removed.
        """
        self.test_segments = mk.fs.createFileInTemp()
        link_segments = self.makeLink(self.test_segments, cleanup=False)
        self.assertTrue(self.filesystem.exists(self.test_segments))
        self.assertTrue(self.filesystem.exists(link_segments))

        self.filesystem.deleteFile(link_segments)

        self.assertTrue(self.filesystem.exists(self.test_segments))
        self.assertFalse(self.filesystem.exists(link_segments))

    @conditionals.onOSFamily('nt')
    def test_deleteFile_read_only(self):
        """
        On Windows, it will delete the file even if it has the read only
        attribute.
        """
        segments = mk.fs.createFileInTemp()
        path = self.filesystem.getRealPathFromSegments(segments)
        os.chmod(path, stat.S_IREAD)
        self.assertTrue(self.filesystem.exists(segments))

        self.filesystem.deleteFile(segments)

        self.assertFalse(self.filesystem.exists(segments))

    def test_deleteFolder_file_non_recursive(self):
        """
        Raise an OS error when trying to delete a file using folder API.
        """
        self.test_segments = mk.fs.createFileInTemp()
        self.assertTrue(self.filesystem.exists(self.test_segments))

        with self.assertRaises(OSError) as context:
            self.filesystem.deleteFolder(self.test_segments, recursive=False)

        self.assertEqual(errno.ENOTDIR, context.exception.errno)
        self.assertTrue(self.filesystem.exists(self.test_segments))

    def test_deleteFolder_file_recursive(self):
        """
        Raise an OS error when trying to delete a file using folder API,
        event when doing recursive delete.
        """
        self.test_segments = mk.fs.createFileInTemp()
        self.assertTrue(self.filesystem.exists(self.test_segments))

        with self.assertRaises(OSError) as context:
            self.filesystem.deleteFolder(self.test_segments, recursive=True)

        self.assertEqual(errno.ENOTDIR, context.exception.errno)
        self.assertTrue(self.filesystem.exists(self.test_segments))

    def test_deleteFolder_non_recursive_empty(self):
        """
        It can delete a folder non-recursive if folder is empty.
        """
        segments = mk.fs.createFolderInTemp()
        self.assertTrue(self.filesystem.exists(segments))

        self.filesystem.deleteFolder(segments, recursive=False)

        self.assertFalse(self.filesystem.exists(segments))

    def test_deleteFolder_non_recursive_non_empty(self):
        """
        It raise an error if folder is not empty.
        """
        self.test_segments, child_name = self.createFolderWithChild()
        self.assertTrue(self.filesystem.exists(self.test_segments))

        with self.assertRaises(OSError):
            self.filesystem.deleteFolder(self.test_segments, recursive=False)

        self.assertTrue(self.filesystem.exists(self.test_segments))
        self.assertEqual(
            [child_name],
            self.filesystem.getFolderContent(self.test_segments),
            )

    def test_deleteFolder_recursive_empty(self):
        """
        It can delete a folder recursive if folder is empty.
        """
        segments = mk.fs.createFolderInTemp()
        self.assertTrue(self.filesystem.exists(segments))

        self.filesystem.deleteFolder(segments, recursive=True)

        self.assertFalse(self.filesystem.exists(segments))

    def test_deleteFolder_recursive_non_empty(self):
        """
        It can delete folder even if it is not empty.
        """
        segments, child_name = self.createFolderWithChild()
        self.assertTrue(self.filesystem.exists(segments))

        self.filesystem.deleteFolder(segments, recursive=True)

        self.assertFalse(self.filesystem.exists(segments))

    @conditionals.onOSFamily('nt')
    def test_deleteFolder_recursive_read_only_members(self):
        """
        On Windows, it will also delete the folders, even if it contains
        files with read only attributes.
        """
        segments, child_name = self.createFolderWithChild()
        # Create and make sure we have a read only child.
        child_segments = segments[:]
        child_segments.append(child_name)
        path = self.filesystem.getRealPathFromSegments(child_segments)
        os.chmod(path, stat.S_IREAD)

        self.filesystem.deleteFolder(segments, recursive=True)

        self.assertFalse(self.filesystem.exists(segments))

    def test_deleteFolder_non_found(self):
        """
        Raise OSError when folder is not found.
        """
        segments = ['c', 'no-such', mk.string()]
        self.assertFalse(self.filesystem.exists(segments))

        with self.assertRaises(OSError) as context:
            self.filesystem.deleteFolder(segments, recursive=False)

        self.assertEqual(errno.ENOENT, context.exception.errno)

    @conditionals.onCapability('symbolic_link', True)
    def test_deleteFolder_link(self):
        """
        It can delete a symlink to a folder and original folder and its
        content is not removed.
        """
        self.test_segments, child_name = self.createFolderWithChild()
        link_segments = self.makeLink(self.test_segments, cleanup=False)
        self.assertTrue(self.filesystem.exists(self.test_segments))
        self.assertTrue(self.filesystem.exists(link_segments))
        # Check that link has same content as target.
        self.assertEqual(
            [child_name], self.filesystem.getFolderContent(link_segments))

        self.filesystem.deleteFolder(link_segments)

        self.assertTrue(self.filesystem.exists(self.test_segments))
        self.assertFalse(self.filesystem.exists(link_segments))
        # Check that target content was not removed
        self.assertEqual(
            [child_name],
            self.filesystem.getFolderContent(self.test_segments))

    @conditionals.onCapability('symbolic_link', True)
    def test_makeLink_file(self):
        """
        Can be used for linking a file.
        """
        content = mk.string()
        self.test_segments = mk.fs.createFileInTemp(content=content)
        link_segments = self.test_segments[:]
        link_segments[-1] = '%s-link' % self.test_segments[-1]

        mk.fs.makeLink(
            target_segments=self.test_segments,
            link_segments=link_segments,
            )

        self.assertTrue(mk.fs.exists(link_segments))
        self.assertTrue(mk.fs.isLink(link_segments))
        # Will point to the same content.
        link_content = mk.fs.getFileContent(self.test_segments)
        self.assertEqual(content, link_content)
        # Can be removed as a simple file and target file is not removed.
        mk.fs.deleteFile(link_segments)
        self.assertFalse(mk.fs.exists(link_segments))
        self.assertTrue(mk.fs.exists(self.test_segments))

    @conditionals.onCapability('symbolic_link', True)
    def test_makeLink_folder(self):
        """
        Can be used for linking a folder.
        """
        self.test_segments, child_name = self.createFolderWithChild()
        link_segments = self.test_segments[:]
        link_segments[-1] = '%s-link' % self.test_segments[-1]

        mk.fs.makeLink(
            target_segments=self.test_segments,
            link_segments=link_segments,
            )

        self.assertTrue(mk.fs.exists(link_segments))
        # Will have the same content.
        content = mk.fs.getFolderContent(link_segments)
        self.assertEqual([child_name], content)
        # Can be removed as a normal folder and target folder is not removed.
        mk.fs.deleteFolder(link_segments)
        self.assertFalse(mk.fs.exists(link_segments))
        self.assertTrue(mk.fs.exists(self.test_segments))
        # Will have the same content.
        content = mk.fs.getFolderContent(self.test_segments)
        self.assertEqual([child_name], content)

    @conditionals.onCapability('symbolic_link', True)
    def test_makeLink_invalid_link(self):
        """
        Raise an error if link can not be created.
        """
        self.test_segments = mk.fs.createFileInTemp()

        with self.assertRaises(OSError):
            mk.fs.makeLink(
                target_segments=self.test_segments,
                link_segments=['no-such', 'link'],
                )

    @conditionals.onCapability('symbolic_link', True)
    def test_makeLink_invalid_target(self):
        """
        Will create a valid link to an invalid target.
        """
        _, self.test_segments = mk.fs.makePathInTemp()

        self.filesystem.makeLink(
            target_segments=['c', 'no-such-target'],
            link_segments=self.test_segments,
            )

        self.assertTrue(self.filesystem.isLink(self.test_segments))
        # Path does not exists, since it will check for target.
        self.assertFalse(self.filesystem.exists(self.test_segments))

    @conditionals.onCapability('symbolic_link', True)
    @conditionals.onOSFamily('nt')
    def test_makeLink_bad_root_target(self):
        """
        For unlocked accounts, will not create a valid link to a target
        which does not have a valid drive letter.

        This is a API inconsistency in Windows where CreateSymbolicLink will
        consider bad:\\path as a relative path named `bad:` and not 'bad:'
        as drive letter.
        """
        with self.assertRaises(OSError):
            target_segments = ['bad', 'no-such', 'target']
            _, test_segments = mk.fs.makePathInTemp()
            self.filesystem.makeLink(
                target_segments=target_segments,
                link_segments=test_segments,
                )

    # Raw data returned from reparse point.
    # print_name and target_name is  u'c:\\temp\\str1593-cp\u021b'
    raw_reparse_buffer = (
        '\x0c\x00\x00\xa0`\x00\x00\x00&\x00.\x00\x00\x00&\x00\x00\x00\x00'
        '\x00c\x00:\x00\\\x00t\x00e\x00m\x00p\x00\\\x00s\x00t\x00r\x001\x005'
        '\x009\x003\x00-\x00c\x00p\x00\x1b\x02\\\x00?\x00?\x00\\\x00c\x00:'
        '\x00\\\x00t\x00e\x00m\x00p\x00\\\x00s\x00t\x00r\x001\x005\x009\x003'
        '\x00-\x00c\x00p\x00\x1b\x02'
        )

    def test_parseReparseData(self):
        """
        It parse raw reparse data buffer into a dict.
        """
        result = self.filesystem._parseReparseData(self.raw_reparse_buffer)

        self.assertEqual(
            self.filesystem.IO_REPARSE_TAG_SYMLINK, result['tag'])
        # Encoded as UTF-16 so length is doubled.. but without UTF-16 BOM.
        utf_16_length = (
            len(u'c:\\temp\\str1593-cp\u021b'.encode('utf-16')) - 2)
        self.assertEqual(0, result['print_name_offset'])
        self.assertEqual(utf_16_length, result['print_name_length'])
        # Target name has 4 extra UTF-16 characters.
        self.assertEqual(utf_16_length, result['substitute_name_offset'])
        self.assertEqual(
            utf_16_length + 4 * 2, result['substitute_name_length'])

    def test_parseSymbolicLinkReparse(self):
        """
        Parse target and print name for symlink reparse data.
        """
        if (
            self.os_name == 'hpux' or
            platform.processor() in ['powerpc', 'sparc']
                ):
            # FIXME:2027:
            # This test fails on AIX and HPUX with a strange encoding error,
            # most probably due to CPU bit order.
            # It also fails on Solaris SPARC, but pass on Solaris x86.
            # platform.processor() is empty on HPUX.
            raise self.skipTest()

        symbolic_link_data = self.filesystem._parseReparseData(
            self.raw_reparse_buffer)

        result = self.filesystem._parseSymbolicLinkReparse(symbolic_link_data)

        self.assertEqual(u'c:\\temp\\str1593-cp\u021b', result['name'])
        self.assertEqual(u'c:\\temp\\str1593-cp\u021b', result['target'])

    @conditionals.onCapability('symbolic_link', True)
    def test_readLink_ok(self):
        """
        Can be used for reading target for a link.
        """
        self.test_segments = mk.fs.createFileInTemp()
        link_segments = self.makeLink(self.test_segments)

        result = self.filesystem.readLink(link_segments)

        self.assertEqual(self.test_segments, result)

    @conditionals.onCapability('symbolic_link', True)
    def test_readLink_link_to_link(self):
        """
        Will only resolve link at first level.
        """
        self.test_segments = mk.fs.createFileInTemp()
        link_segments = self.makeLink(self.test_segments)
        link_link_segments = self.makeLink(link_segments)

        result = self.filesystem.readLink(link_link_segments)

        self.assertEqual(link_segments, result)

    @conditionals.onCapability('symbolic_link', True)
    def test_readLink_bad_path(self):
        """
        Raise an error when path was not found.
        """
        with self.assertRaises(OSError) as context:
            self.filesystem.readLink(['c', 'no-such-segments'])

        self.assertEqual(errno.ENOENT, context.exception.errno)

    @conditionals.onCapability('symbolic_link', True)
    def test_readLink_not_link(self):
        """
        Raise an error when path is not a link.
        """
        self.test_segments = mk.fs.createFileInTemp()

        with self.assertRaises(OSError) as context:
            self.filesystem.readLink(self.test_segments)

        self.assertEqual(errno.EINVAL, context.exception.errno)

    @conditionals.onCapability('symbolic_link', True)
    def test_readLink_bad_target(self):
        """
        Can be used for reading target for a link, event when target
        does not exist.
        """
        target_segments = ['z', 'no-such', 'target']
        _, self.test_segments = mk.fs.makePathInTemp()
        self.filesystem.makeLink(
            target_segments=target_segments,
            link_segments=self.test_segments,
            )

        result = self.filesystem.readLink(self.test_segments)

        self.assertEqual(target_segments, result)

    def test_isFile(self):
        """
        Check isFile.
        """
        self.test_segments = mk.fs.createFileInTemp()
        _, non_existent_segments = mk.fs.makePathInTemp()

        self.assertTrue(self.filesystem.isFile(self.test_segments))
        # Non existent paths are not files.
        self.assertFalse(self.filesystem.isFile(non_existent_segments))
        # Folders are not files.
        self.assertFalse(self.filesystem.isFile(mk.fs.temp_segments))

    def test_isFolder(self):
        """
        Check isFolder.
        """
        self.test_segments = mk.fs.createFileInTemp()
        _, non_existent_segments = mk.fs.makePathInTemp()

        self.assertTrue(
            self.filesystem.isFolder(mk.fs.temp_segments))
        # Non existent folders are not files.
        self.assertFalse(
            self.filesystem.isFolder(non_existent_segments))
        # Files are not folders.
        self.assertFalse(
            self.filesystem.isFolder(self.test_segments))

    @conditionals.onOSFamily('nt')
    def test_getFileData(self):
        """
        Return a dict with file data.
        """
        content = mk.string()
        self.test_segments = mk.fs.createFileInTemp(content=content)
        name = self.test_segments[-1]

        result = self.filesystem._getFileData(self.test_segments)

        self.assertEqual(len(content.encode('utf-8')), result['size'])
        self.assertEqual(name, result['name'])
        self.assertEqual(0, result['tag'])

    @conditionals.onCapability('symbolic_link', True)
    def test_isLink(self):
        """
        Check isLink.
        """
        self.test_segments = mk.fs.createFileInTemp()
        _, non_existent_segments = mk.fs.makePathInTemp()
        file_link_segments = self.makeLink(self.test_segments)
        folder_link_segments = self.test_segments[:]
        folder_link_segments[-1] = '%s-folder-link' % folder_link_segments[-1]
        mk.fs.makeLink(
            target_segments=mk.fs.temp_segments,
            link_segments=folder_link_segments,
            )
        self.addCleanup(
            mk.fs.deleteFolder, folder_link_segments)

        self.assertTrue(self.filesystem.isLink(file_link_segments))
        self.assertTrue(self.filesystem.isLink(folder_link_segments))
        self.assertFalse(self.filesystem.isLink(mk.fs.temp_segments))
        self.assertFalse(self.filesystem.isLink(self.test_segments))
        self.assertFalse(self.filesystem.isLink(non_existent_segments))
        self.assertFalse(self.filesystem.isLink(['invalid-drive-or-path']))

    @conditionals.onCapability('symbolic_link', False)
    def test_isLink_not_supported(self):
        """
        Raise NotImplementedError if not supported.
        """
        with self.assertRaises(NotImplementedError):
            self.filesystem.makeLink(['some-target'], ['some-link'])

    def test_getAttributes_file(self):
        """
        Check attributes for a file.
        """
        size = mk.number()
        self.test_segments = mk.fs.createFileInTemp(length=size)

        attributes = self.filesystem.getAttributes(self.test_segments)

        self.assertEqual(size, attributes.size)
        self.assertFalse(attributes.is_folder)
        self.assertTrue(attributes.is_file)
        self.assertFalse(attributes.is_link)
        self.assertNotEqual(0, attributes.node_id)
        self.assertIsNotNone(attributes.node_id)
        if self.os_family == 'posix':
            current_umask = mk.fs._getCurrentUmask()
            expected_mode = 0o100666 ^ current_umask
            self.assertEqual(expected_mode, attributes.mode)

    def test_getAttributes_folder(self):
        """
        Check attributes for a folder.
        """
        self.test_segments = mk.fs.createFolderInTemp()

        attributes = self.filesystem.getAttributes(self.test_segments)

        self.assertTrue(attributes.is_folder)
        self.assertFalse(attributes.is_file)
        self.assertFalse(attributes.is_link)
        self.assertNotEqual(0, attributes.node_id)
        self.assertIsNotNone(attributes.node_id)
        if self.os_family == 'posix':
            current_umask = mk.fs._getCurrentUmask()
            expected_mode = 0o40777 ^ current_umask
            self.assertEqual(expected_mode, attributes.mode)

    @conditionals.onCapability('symbolic_link', True)
    def test_getAttributes_link_file(self):
        """
        A link to a file is recognized as both a link and a file.
        """
        self.test_segments = mk.fs.createFileInTemp()
        link_segments = self.makeLink(self.test_segments)

        attributes = self.filesystem.getAttributes(link_segments)

        self.assertTrue(attributes.is_file)
        self.assertTrue(attributes.is_link)
        self.assertFalse(attributes.is_folder)

    @conditionals.onCapability('symbolic_link', True)
    def test_getAttributes_link_folder(self):
        """
        A link to a folder is recognized as both a link and a folder.
        """
        _, link_segments = mk.fs.makePathInTemp()
        mk.fs.makeLink(
            target_segments=mk.fs.temp_segments,
            link_segments=link_segments,
            )
        self.addCleanup(mk.fs.deleteFolder, link_segments)

        attributes = self.filesystem.getAttributes(link_segments)

        self.assertFalse(attributes.is_file)
        self.assertTrue(attributes.is_link)
        self.assertTrue(attributes.is_folder)

    @conditionals.onCapability('symbolic_link', True)
    def test_getAttributes_link_not_found(self):
        """
        Raise an OSError not found when target does not exists.
        """
        path, link_segments = mk.fs.makePathInTemp()
        target_segments = ['c', 'no-such-parent', 'no-child', 'target']
        mk.fs.makeLink(
            target_segments=target_segments,
            link_segments=link_segments,
            )
        self.addCleanup(mk.fs.deleteFile, link_segments)

        error = self.assertRaises(
            OSError,
            self.filesystem.getAttributes, link_segments,
            )

        if self.os_family == 'nt':
            expected_path = path
        else:
            expected_path = path.encode('utf-8')
        self.assertEqual(errno.ENOENT, error.errno)
        self.assertEqual(expected_path, error.filename)
        self.assertEqual('No such file or directory', error.strerror)

    def test_getStatus_file(self):
        """
        Will return the os.stat result for a file.
        """
        self.test_segments = mk.fs.createFileInTemp()

        status = self.filesystem.getStatus(self.test_segments)

        # We can not test to much here, but getStatus is used by other
        # high level method and we should have specific tests there.
        self.assertTrue(stat.S_ISREG(status.st_mode))
        self.assertFalse(stat.S_ISDIR(status.st_mode))
        self.assertFalse(stat.S_ISLNK(status.st_mode))
        self.assertNotEqual(0, status.st_ino)

    def test_getStatus_directory(self):
        """
        Will return the os.stat result for a directory.
        """
        self.test_segments = mk.fs.createFolderInTemp()

        status = self.filesystem.getStatus(self.test_segments)

        # We can not test to much here, but getStatus is used by other
        # high level method and we should have specific tests there.
        self.assertFalse(stat.S_ISREG(status.st_mode))
        self.assertTrue(stat.S_ISDIR(status.st_mode))
        self.assertFalse(stat.S_ISLNK(status.st_mode))
        self.assertNotEqual(0, status.st_ino)

    def test_getStatus_not_found(self):
        """
        Will raise an error if path does not exists.
        """
        segments = mk.fs.temp_segments + [mk.string()]

        with self.assertRaises(OSError):
            self.filesystem.getStatus(segments)

    @conditionals.onOSFamily('nt')
    def test_getStatus_already_opened(self):
        """
        It will get status for file even if it's opened for writing.
        """
        self.test_segments = mk.fs.createFileInTemp()
        handle = self.filesystem.openFileForWriting(self.test_segments)
        handle.write(mk.ascii())
        handle.flush()
        self.addCleanup(lambda: handle.close())

        status = self.filesystem.getStatus(self.test_segments)

        self.assertTrue(stat.S_ISREG(status.st_mode))
        self.assertFalse(stat.S_ISDIR(status.st_mode))
        self.assertFalse(stat.S_ISLNK(status.st_mode))
        self.assertNotEqual(0, status.st_ino)

    @conditionals.onOSFamily('posix')
    def test_checkChildPath_unix(self):
        """
        Will raise an error if child is outside of root, or do nothing if
        child is is root.
        """
        self.filesystem._checkChildPath(u'/root/path', '/root/path')
        self.filesystem._checkChildPath(u'/root/path/', '/root/path')
        self.filesystem._checkChildPath(u'/root/path', '/root/path/')
        self.filesystem._checkChildPath(u'/root/path', '/root/path/../path/')

        with self.assertRaises(CompatError):
            self.filesystem._checkChildPath(u'/root/path', '/')

        with self.assertRaises(CompatError):
            self.filesystem._checkChildPath(u'/root/path', '/root/path/..')

    @conditionals.onOSFamily('nt')
    def test_checkChildPath_nt(self):
        """
        See: test_checkChildPath_unix
        """
        self.filesystem._checkChildPath(u'c:\\root\\path', 'c:\\root\\path')
        self.filesystem._checkChildPath(u'c:\\root\\path\\', 'c:\\root\\path')
        self.filesystem._checkChildPath(u'c:\\root\\path', 'c:\\root\\path\\')
        self.filesystem._checkChildPath(
            u'c:\\root\\path', 'c:\\root\\path\\..\\path')

        with self.assertRaises(CompatError):
            self.filesystem._checkChildPath(u'c:\\root\\path', 'c:\\')

        with self.assertRaises(CompatError):
            self.filesystem._checkChildPath(
                u'c:\\root\\path', 'c:\\root\\path\\..')

    def test_getFolderContent_not_found(self):
        """
        Raise OSError when trying to get folder for a non existent path.
        """
        segments = ['c', mk.string()]

        with self.assertRaises(OSError) as context:
            self.filesystem.getFolderContent(segments)

        self.assertEqual(errno.ENOENT, context.exception.errno)

    def test_getFolderContent_file(self):
        """
        Raise OSError when trying to get folder content for a file.
        """
        self.test_segments = mk.fs.createFileInTemp()

        with self.assertRaises(OSError) as context:
            self.filesystem.getFolderContent(self.test_segments)

        self.assertEqual(errno.ENOTDIR, context.exception.errno)

    def test_getFolderContent_empty(self):
        """
        Return empty list for empty folders.
        """
        self.test_segments = mk.fs.createFolderInTemp()

        content = self.filesystem.getFolderContent(self.test_segments)

        self.assertIsEmpty(content)

    def test_getFolderContent_non_empty(self):
        """
        Return folder content as list of Unicode names.
        """
        self.test_segments = mk.fs.createFolderInTemp()
        file_name = mk.makeFilename()
        folder_name = mk.makeFilename()
        file_segments = self.test_segments[:]
        file_segments.append(file_name)
        folder_segments = self.test_segments[:]
        folder_segments.append(folder_name)
        mk.fs.createFile(file_segments)
        mk.fs.createFolder(folder_segments)

        content = self.filesystem.getFolderContent(self.test_segments)

        self.assertIsNotEmpty(content)
        self.assertTrue(isinstance(content[0], text_type))
        self.assertItemsEqual([folder_name, file_name], content)

    @conditionals.skipOnPY3()
    def test_iterateFolderContent_not_found(self):
        """
        Raise OSError when trying to get folder for a non existent path.
        """
        segments = ['c', mk.string(), mk.string()]

        with self.assertRaises(OSError) as context:
            self.filesystem.iterateFolderContent(segments)

        self.assertEqual(errno.ENOENT, context.exception.errno)

    @conditionals.skipOnPY3()
    def test_iterateFolderContent_file(self):
        """
        Raise OSError when trying to get folder content for a file.
        """
        segments = self.fileInTemp()

        with self.assertRaises(OSError) as context:
            self.filesystem.iterateFolderContent(segments)

        if self.os_family == 'nt':
            # On Windows, we get a different error.
            expected_error = errno.EINVAL
        else:
            expected_error = errno.ENOTDIR

        self.assertEqual(expected_error, context.exception.errno)

    @conditionals.skipOnPY3()
    def test_iterateFolderContent_empty(self):
        """
        Return empty iterator for empty folders.
        """
        segments = self.folderInTemp()

        result = self.filesystem.iterateFolderContent(segments)

        self.assertIteratorEqual([], result)

    @conditionals.skipOnPY3()
    def test_iterateFolderContent_non_empty(self):
        """
        Return folder content as list of Unicode names.
        """
        base_segments = self.folderInTemp()
        file_name = mk.makeFilename()
        folder_name = mk.makeFilename()
        file_segments = base_segments + [file_name]
        folder_segments = base_segments + [folder_name]
        mk.fs.createFile(file_segments)
        mk.fs.createFolder(folder_segments)

        content = self.filesystem.iterateFolderContent(base_segments)

        result = list(content)
        self.assertIsNotEmpty(result)
        self.assertIsInstance(text_type, result[0])
        self.assertItemsEqual([folder_name, file_name], result)

    @conditionals.skipOnPY3()
    def test_iterateFolderContent_big(self):
        """
        It will not block on listing folders with many members.

        On some systems, this test takes more than 1 minute.
        """
        for _ in range(3):  # pragma: no branch
            try:
                self._iterateFolderContent_big()
                # All good. Stop trying.
                return
            except AssertionError as error:
                # Run cleanup and try again.
                self.callCleanup()

        # We tried 3 times and still got a failure.
        raise error  # noqa:cover

    def _iterateFolderContent_big(self):
        """
        Main code for running the test
        """
        # FIXME:4036:
        # Enable full test once we have fast filesystem access.
        if self.os_name == 'aix':
            count = 3000
            base_timeout = 0.02
        elif self.os_name in ['hpux', 'freebsd', 'openbsd']:
            # Some OS/FS does not allow more than 32765 members in a folder
            # and the slave is generally slow.
            count = 32000
            base_timeout = 0.15
        else:
            count = 45000
            base_timeout = 0.1

        if self.os_name == 'windows':
            # On windows, some iteration operation might be very slow.
            bias = 0.7
        else:
            bias = 0

        base_segments = self.folderInTemp()

        for i in range(count):
            mk.fs.createFolder(base_segments + ['some-member-%s' % (i,)])
            if i % 1000 == 0:
                # This is slow, so keep the CI informed that we are doing
                # stuff.
                sys.stdout.write('+')
                sys.stdout.flush()

        # We check that doing a direct listing will take a long time.
        with self.assertRaises(AssertionError):
            with self.assertExecutionTime(base_timeout):
                result = self.filesystem.getFolderContent(base_segments)
        self.assertEqual(count, len(result))

        # Show progress.
        sys.stdout.write('+')
        sys.stdout.flush()

        # Getting the iterator will not take long.
        with self.assertExecutionTime(base_timeout + bias):
            iterator = self.filesystem.iterateFolderContent(base_segments)

        # Iterating at any step will not take long.
        result = []
        result.append(next(iterator))
        try:
            i = 0
            while True:
                with self.assertExecutionTime(base_timeout + bias):
                    result.append(next(iterator))
                i += 1
                if i % 1000 == 0:
                    # This is slow, so keep the CI informed that we are doing
                    # stuff.
                    sys.stdout.write('+')
                    sys.stdout.flush()
        except StopIteration:
            """
            We are at the end. All good.
            """
        self.assertEqual(count, len(result))

    def test_openFile_folder(self):
        """
        Raise OSError when trying to open a folder as file.
        """
        self.test_segments = mk.fs.createFolderInTemp()
        path = mk.fs.getRealPathFromSegments(self.test_segments)

        with self.assertRaises(OSError) as context:
            self.filesystem.openFile(self.test_segments, os.O_RDONLY, 0o777)

        self.assertEqual(errno.EISDIR, context.exception.errno)
        self.assertEqual(path.encode('utf-8'), context.exception.filename)

    def test_openFileForReading_folder(self):
        """
        Raise OSError when trying to open a folder as file for reading.
        """
        self.test_segments = mk.fs.createFolderInTemp()
        path = mk.fs.getRealPathFromSegments(self.test_segments)

        with self.assertRaises(OSError) as context:
            self.filesystem.openFileForReading(self.test_segments, utf8=False)

        self.assertEqual(errno.EISDIR, context.exception.errno)
        self.assertEqual(path.encode('utf-8'), context.exception.filename)

        with self.assertRaises(OSError) as context:
            self.filesystem.openFileForReading(self.test_segments, utf8=True)

        self.assertEqual(errno.EISDIR, context.exception.errno)
        self.assertEqual(path.encode('utf-8'), context.exception.filename)

    def test_openFileForWriting_folder(self):
        """
        Raise OSError when trying to open a folder as file for writing.
        """
        self.test_segments = mk.fs.createFolderInTemp()
        path = mk.fs.getRealPathFromSegments(self.test_segments)

        with self.assertRaises(OSError) as context:
            self.filesystem.openFileForWriting(self.test_segments, utf8=False)

        self.assertEqual(errno.EISDIR, context.exception.errno)
        self.assertEqual(path.encode('utf-8'), context.exception.filename)

        with self.assertRaises(OSError) as context:
            self.filesystem.openFileForWriting(self.test_segments, utf8=True)

        self.assertEqual(errno.EISDIR, context.exception.errno)
        self.assertEqual(path.encode('utf-8'), context.exception.filename)

    def test_openFileForAppending_folder(self):
        """
        Raise OSError when trying to open a folder as file for appending.
        """
        self.test_segments = mk.fs.createFolderInTemp()
        path = mk.fs.getRealPathFromSegments(self.test_segments)

        with self.assertRaises(OSError) as context:
            self.filesystem.openFileForAppending(
                self.test_segments, utf8=False)

        self.assertEqual(errno.EISDIR, context.exception.errno)
        self.assertEqual(path.encode('utf-8'), context.exception.filename)

        with self.assertRaises(OSError) as context:
            self.filesystem.openFileForAppending(self.test_segments, utf8=True)

        self.assertEqual(errno.EISDIR, context.exception.errno)
        self.assertEqual(path.encode('utf-8'), context.exception.filename)

    def test_openFileForUpdating_folder(self):
        """
        Raise OSError when trying to open a folder as file for updating.
        """
        self.test_segments = mk.fs.createFolderInTemp()
        path = mk.fs.getRealPathFromSegments(self.test_segments)

        with self.assertRaises(OSError) as context:
            self.filesystem.openFileForUpdating(
                self.test_segments, utf8=False)

        self.assertEqual(errno.EISDIR, context.exception.errno)
        self.assertEqual(path.encode('utf-8'), context.exception.filename)

        with self.assertRaises(OSError) as context:
            self.filesystem.openFileForUpdating(self.test_segments, utf8=True)

        self.assertEqual(errno.EISDIR, context.exception.errno)
        self.assertEqual(path.encode('utf-8'), context.exception.filename)

    def test_touch_no_parent(self):
        """
        Raise an error when path does not exists and can not be created.
        """
        with self.assertRaises(IOError) as context:
            self.filesystem.touch(['c', 'no-such', 'path'])

        self.assertEqual(errno.ENOENT, context.exception.errno)

    def test_touch_dont_exists(self):
        """
        A file is created if it does not exists.
        """
        _, self.test_segments = mk.fs.makePathInTemp()
        self.assertFalse(mk.fs.exists(self.test_segments))

        self.filesystem.touch(self.test_segments)

        self.assertTrue(mk.fs.exists(self.test_segments))

    def test_touch_already_exists(self):
        """
        The modified time is updated path already exists.
        """
        self.test_segments = mk.fs.createFileInTemp()
        now = time.time()
        mk.fs.setAttributes(
            self.test_segments, {'atime': now - 10, 'mtime': now - 10})

        self.filesystem.touch(self.test_segments)

        self.assertTrue(mk.fs.exists(self.test_segments))
        attributes = mk.fs.getAttributes(self.test_segments)
        self.assertAlmostEqual(now, attributes.modified, delta=1.5)

    def test_copyFile_destination_no_parent(self):
        """
        Raises an exception when destination does not exists, and it can not
        be created
        """
        self.test_segments = mk.fs.createFileInTemp(content=mk.string())
        destination_segments = ['c', 'no-parent', 'path']

        with self.assertRaises(IOError) as context:
            self.filesystem.copyFile(self.test_segments, destination_segments)

        self.assertEqual(errno.ENOENT, context.exception.errno)

    def test_copyFile_file_destination_exists_no_overwrite(self):
        """
        Raise an error when destination exists and it was not instructed to
        overwrite existing files.
        """
        source_segments = ['ignore', 'source']
        self.test_segments = mk.fs.createFileInTemp()

        with self.assertRaises(OSError) as context:
            self.filesystem.copyFile(source_segments, self.test_segments)

        self.assertEqual(errno.EEXIST, context.exception.errno)

    def test_copyFile_file_destination_exists_overwrite(self):
        """
        Copy file without errors when overwrite was asked.
        """
        content = mk.string()
        self.test_segments = mk.fs.createFileInTemp(content=content)
        destination_segments = mk.fs.createFileInTemp()

        self.filesystem.copyFile(
            self.test_segments, destination_segments, overwrite=True)

        destination_content = mk.fs.getFileContent(destination_segments)
        self.assertEqual(content, destination_content)
        mk.fs.deleteFile(destination_segments)

    def test_copyFile_folder_destination_exists_no_overwrite(self):
        """
        Raise an error when destination exists in destination folder
        and it was not instructed to overwrite existing files.
        """
        self.test_segments = mk.fs.createFileInTemp()
        destination_segments = self.test_segments[:-1]
        source_segments = ['bla', self.test_segments[-1]]

        with self.assertRaises(OSError) as context:
            self.filesystem.copyFile(source_segments, destination_segments)

        self.assertEqual(errno.EEXIST, context.exception.errno)

    def test_copyFile_folder_destination_exists_overwrite(self):
        """
        Replace file when destination exists in destination folder
        and it was instructed to overwrite existing files.
        """
        content = mk.string()
        self.test_segments = mk.fs.createFileInTemp(content=content)
        destination_segments = mk.fs.createFolderInTemp()
        destination_file_segments = destination_segments[:]
        destination_file_segments.append(self.test_segments[-1])
        mk.fs.touch(destination_file_segments)

        self.filesystem.copyFile(
            self.test_segments, destination_segments, overwrite=True)

        destination_content = mk.fs.getFileContent(destination_file_segments)
        self.assertEqual(content, destination_content)
        mk.fs.deleteFolder(destination_segments, recursive=True)

    def test_copyFile_file_destination_no_exists(self):
        """
        Copy file in destination when destination does not exists, but
        can be created.
        """
        content = mk.string()
        _, destination_segments = mk.fs.makePathInTemp()
        source_segments = mk.fs.createFileInTemp(content=content)

        self.filesystem.copyFile(source_segments, destination_segments)

        self.assertTrue(self.filesystem.exists(destination_segments))
        destination_content = mk.fs.getFileContent(destination_segments)
        self.assertEqual(content, destination_content)
        # Clean new files.
        self.filesystem.deleteFile(source_segments)
        self.filesystem.deleteFile(destination_segments)

    def test_copyFile_folder_destination_no_exists(self):
        """
        When destination is a folder the file will be copied using the same
        filename as the source, if the folder does not already contain
        a member with the same name.
        """
        content = mk.string()
        source_segments = mk.fs.createFileInTemp(content=content)
        self.test_segments = mk.fs.createFolderInTemp()
        destination_segments = self.test_segments[:]
        destination_segments.append(source_segments[-1])

        self.filesystem.copyFile(source_segments, self.test_segments)

        self.assertTrue(self.filesystem.exists(destination_segments))
        destination_content = mk.fs.getFileContent(destination_segments)
        self.assertEqual(content, destination_content)
        self.filesystem.deleteFile(source_segments)

    def test_makeFolder(self):
        """
        Check makeFolder.
        """
        folder_name = mk.makeFilename(length=10)
        self.test_segments = mk.fs.temp_segments[:]
        self.test_segments.append(folder_name)

        self.filesystem.createFolder(self.test_segments)

        self.assertTrue(self.filesystem.isFolder(self.test_segments))

    def test_rename_file(self):
        """
        System test for file renaming.
        """
        _, initial_segments = mk.fs.makePathInTemp()
        _, self.test_segments = mk.fs.makePathInTemp()
        self.assertFalse(self.filesystem.exists(initial_segments))
        self.assertFalse(self.filesystem.exists(self.test_segments))
        self.filesystem.touch(initial_segments)

        self.filesystem.rename(initial_segments, self.test_segments)

        self.assertFalse(self.filesystem.exists(initial_segments))
        self.assertTrue(self.filesystem.exists(self.test_segments))

    @conditionals.onOSFamily('nt')
    def test_rename_file_read_only(self):
        """
        On Windows, it will rename the file even if it has the read only
        attribute.
        """
        _, initial_segments = mk.fs.makePathInTemp()
        _, self.test_segments = mk.fs.makePathInTemp()
        self.assertFalse(self.filesystem.exists(initial_segments))
        self.assertFalse(self.filesystem.exists(self.test_segments))
        self.filesystem.touch(initial_segments)
        path = self.filesystem.getRealPathFromSegments(initial_segments)
        os.chmod(path, stat.S_IREAD)

        self.filesystem.rename(initial_segments, self.test_segments)

        self.assertFalse(self.filesystem.exists(initial_segments))
        self.assertTrue(self.filesystem.exists(self.test_segments))

    def test_rename_folder(self):
        """
        System test for folder renaming.
        """
        _, initial_segments = mk.fs.makePathInTemp()
        _, self.test_segments = mk.fs.makePathInTemp()
        self.assertFalse(self.filesystem.exists(initial_segments))
        self.assertFalse(self.filesystem.exists(self.test_segments))
        self.filesystem.createFolder(initial_segments)

        self.filesystem.rename(initial_segments, self.test_segments)

        self.assertFalse(self.filesystem.exists(initial_segments))
        self.assertTrue(self.filesystem.exists(self.test_segments))

    def test_exists_false(self):
        """
        exists will return `False` if file or folder does not exists.
        """
        segments = self.filesystem.temp_segments[:]
        segments.append(mk.makeFilename())

        self.assertFalse(self.filesystem.exists(segments))

    def test_exists_file_true(self):
        """
        exists will return `True` if file exists.
        """
        self.test_segments = self.filesystem.temp_segments[:]
        self.test_segments.append(mk.makeFilename())
        with (self.filesystem.openFileForWriting(
                self.test_segments)) as new_file:
            new_file.write(mk.getUniqueString().encode('utf8'))

        self.assertTrue(self.filesystem.exists(self.test_segments))

    def test_exists_folder_true(self):
        """
        exists will return `True` if folder exists.
        """
        self.test_segments = self.filesystem.temp_segments[:]
        self.test_segments.append(mk.makeFilename())
        self.filesystem.createFolder(self.test_segments)

        self.assertTrue(self.filesystem.exists(self.test_segments))

    def test_getFileSize(self):
        """
        Check retrieving the size for a file.
        """
        test_size = 1345
        self.test_segments = mk.fs.createFileInTemp(length=test_size)

        size = self.filesystem.getFileSize(self.test_segments)

        self.assertEqual(test_size, size)

    def test_getFileSize_empty_file(self):
        """
        Check getting file size for an empty file.
        """
        test_size = 0
        self.test_segments = mk.fs.createFileInTemp(length=0)

        size = self.filesystem.getFileSize(self.test_segments)

        self.assertEqual(test_size, size)

    def test_openFileForReading_unicode(self):
        """
        Check reading in Unicode.
        """
        content = mk.getUniqueString()
        self.test_segments = mk.fs.createFileInTemp(content=content)
        a_file = None
        try:

            a_file = self.filesystem.openFileForReading(
                self.test_segments, utf8=True)

            self.assertEqual(content, a_file.read())
        finally:
            if a_file:
                a_file.close()

    def test_openFileForReading_empty(self):
        """
        An empty file can be opened for reading.
        """
        self.test_segments = mk.fs.createFileInTemp(length=0)
        a_file = None
        try:

            a_file = self.filesystem.openFileForReading(
                self.test_segments)

            self.assertEqual('', a_file.read())
        finally:
            if a_file:
                a_file.close()

    def test_openFileForReading_no_write(self):
        """
        A file opened only for reading will not be able to write into.
        """
        self.test_segments = mk.fs.createFileInTemp(length=0)
        a_file = None
        try:
            a_file = self.filesystem.openFileForReading(
                self.test_segments)

            with self.assertRaises(IOError):
                a_file.write('something')
        finally:
            if a_file:
                a_file.close()

    def test_openFileForWriting_ascii(self):
        """
        Check opening a file for writing in plain/ascii/str mode.
        """
        content = 'some ascii text'
        self.test_segments = mk.fs.createFileInTemp(length=0)
        a_file = None
        try:

            a_file = self.filesystem.openFileForWriting(self.test_segments)
            a_file.write(content)
            a_file.close()

            a_file = self.filesystem.openFileForReading(self.test_segments)
            test_content = a_file.read()
            self.assertEqual(test_content, content)
        finally:
            if a_file:
                a_file.close()

    def test_openFileForWriting_unicode(self):
        """
        Check opening a file for writing in Unicode mode.
        """
        content = mk.getUniqueString()
        self.test_segments = mk.fs.createFileInTemp(length=0)
        a_file = None
        try:

            a_file = self.filesystem.openFileForWriting(
                self.test_segments, utf8=True)
            a_file.write(content)
            a_file.close()

            a_file = self.filesystem.openFileForReading(
                self.test_segments, utf8=True)
            test_content = a_file.read()
            self.assertEqual(test_content, content)
        finally:
            if a_file:
                a_file.close()

    def test_openFileForWriting_no_read(self):
        """
        When a file is opened for writing, we can not read from it.
        """
        self.test_segments = mk.fs.createFileInTemp(length=0)
        a_file = None
        try:
            a_file = self.filesystem.openFileForWriting(
                self.test_segments)

            # We should not be able to read.
            with self.assertRaises(IOError):
                a_file.read()

        finally:
            if a_file:
                a_file.close()

    def test_openFileForWriting_truncate(self):
        """
        When a file is opened for writing, the previous file is truncated
        to 0 length and we write as a fresh file.
        """
        content = mk.getUniqueString(100)
        new_content = mk.getUniqueString(50)
        # Create initial content.
        self.test_segments = mk.fs.createFileInTemp(content=content)

        # Write new content into file.
        test_file = self.filesystem.openFileForWriting(
            self.test_segments)
        test_file.write(new_content.encode('utf-8'))
        test_file.close()

        file_content = mk.fs.getFileContent(self.test_segments)
        self.assertEqual(new_content, file_content)

    def test_openFileForUpdating_non_existing(self):
        """
        An error is raised when trying to open a file which does not
        exists for updating.
        """
        path, segments = mk.fs.makePathInTemp()

        with self.assertRaises(OSError) as context:
            self.filesystem.openFileForUpdating(segments, utf8=False)

        self.assertEqual(errno.ENOENT, context.exception.errno)
        if self.os_family == 'posix':
            # On Windows, the path is not set to the exception.
            self.assertEqual(path.encode('utf-8'), context.exception.filename)

        with self.assertRaises(OSError) as context:
            self.filesystem.openFileForUpdating(segments, utf8=True)

        self.assertEqual(errno.ENOENT, context.exception.errno)
        self.assertEqual(path.encode('utf-8'), context.exception.filename)

    def test_openFileForUpdating_existing_binary(self):
        """
        When a file is opened for updating the previous content is kept and
        it will allow writing at arbitrary offsets.
        """
        content = b'some existing content'
        new_content = b'more here'
        # Create initial content.
        self.test_segments = mk.fs.createFileInTemp(content=content)

        # Write new content into file.
        test_file = self.filesystem.openFileForUpdating(
            self.test_segments, utf8=False)
        test_file.seek(10, 0)
        test_file.write(new_content.encode('utf-8'))
        test_file.close()

        file_content = mk.fs.getFileContent(self.test_segments)
        self.assertEqual(u'some existmore herent', file_content)

    def test_openFileForUpdating_existing_utf8(self):
        """
        When a file is opened for updating the previous content is kept and
        it will allow writing at arbitrary offsets.
        """
        content = b'some existing content'
        # Snowman Unicode has 3 bytes.
        new_content = u'more \N{snowman}'
        # Create initial content.
        self.test_segments = mk.fs.createFileInTemp(content=content)

        # Write new content into file.
        test_file = self.filesystem.openFileForUpdating(
            self.test_segments, utf8=True)
        test_file.seek(10, 0)
        test_file.write(new_content)
        test_file.close()

        file_content = mk.fs.getFileContent(self.test_segments)
        self.assertEqual(u'some existmore \N{snowman}ent', file_content)

    def test_openFileForUpdating_read_binary(self):
        """
        Will not allow reading the file.
        """
        content = b'some existing content'
        # Create initial content.
        self.test_segments = mk.fs.createFileInTemp(content=content)

        # Write new content into file.
        test_file = self.filesystem.openFileForUpdating(
            self.test_segments, utf8=False)
        test_file.seek(10, 0)
        with self.assertRaises(IOError) as context:
            test_file.read()

        error_message = context.exception.args[0]
        self.assertEqual('File not open for reading', error_message)

        # Even if we go for the low level FD, we can't read it.
        with self.assertRaises(OSError) as context:
            os.read(test_file.fileno(), 1)

        test_file.close()

    def test_openFileForUpdating_read_utf8(self):
        """
        Will not allow reading the file.
        """
        content = b'some existing content'
        # Create initial content.
        self.test_segments = mk.fs.createFileInTemp(content=content)

        # Write new content into file.
        test_file = self.filesystem.openFileForUpdating(
            self.test_segments, utf8=True)
        test_file.seek(10, 0)
        with self.assertRaises(IOError) as context:
            test_file.read()

        error_message = context.exception.args[0]
        self.assertEqual('File not open for reading', error_message)

        # We can read it if we go to the low level API.
        # This is a known issue.
        os.read(test_file.fileno(), 1)

        test_file.close()

    def test_openFileForAppending(self):
        """
        System test for openFileForAppending.
        """
        content = mk.getUniqueString()
        new_content = mk.getUniqueString()
        self.test_segments = mk.fs.createFileInTemp(content=content)
        a_file = None
        try:
            a_file = self.filesystem.openFileForAppending(
                self.test_segments, utf8=True)

            a_file.write(new_content)
            a_file.close()

            a_file = self.filesystem.openFileForReading(
                self.test_segments, utf8=True)
            new_test_content = a_file.read()
            self.assertEqual(new_test_content, content + new_content)
        finally:
            if a_file:
                a_file.close()

    def test_openFileForReading_ascii(self):
        """
        Check opening file for reading in ascii mode.
        """
        content = u'ceva nou'
        content_str = 'ceva nou'
        self.test_segments = mk.fs.createFileInTemp(content=content)
        a_file = None
        try:

            a_file = self.filesystem.openFileForReading(
                self.test_segments)

            self.assertEqual(content_str, a_file.read())
        finally:
            if a_file:
                a_file.close()


class TestLocalFilesystemUnlocked(CompatTestCase, FilesystemTestMixin):
    """
    Commons tests for non chrooted filesystem.

    The setup is identical with TestLocalFilesystem, but these are path
    specific test and we isolate them to help detect low level path handling
    regressions.

    # FIXME:1013:
    # This test case need a lot of cleaning.
    """

    @classmethod
    def setUpClass(cls):
        super(TestLocalFilesystemUnlocked, cls).setUpClass()
        cls.unlocked_filesystem = LocalFilesystem(avatar=DefaultAvatar())
        cls.filesystem = cls.unlocked_filesystem

    def test_getSegments(self):
        """
        Check getSegments.
        """
        home_segments = self.unlocked_filesystem.home_segments
        home_path = u'/' + u'/'.join(home_segments)

        segments = self.unlocked_filesystem.getSegments(None)
        self.assertEqual(home_segments, segments)

        segments = self.unlocked_filesystem.getSegments(u'')
        self.assertEqual(home_segments, segments)

        segments = self.unlocked_filesystem.getSegments(u'.')
        self.assertEqual(home_segments, segments)

        segments = self.unlocked_filesystem.getSegments(home_path)
        self.assertEqual(home_segments, segments)

        segments = self.unlocked_filesystem.getSegments(u'..')
        self.assertEqual(home_segments[:-1], segments)

        segments = self.unlocked_filesystem.getSegments(u'/a/../../../B')
        self.assertEqual([u'B'], segments)

        segments = self.unlocked_filesystem.getSegments(u'/Aa/././bB')
        self.assertEqual([u'Aa', u'bB'], segments)

        bubu_segments = home_segments[:]
        bubu_segments.append(u'Bubu')
        segments = self.unlocked_filesystem.getSegments(u'./Bubu')
        self.assertEqual(bubu_segments, segments)

    def test_getSegments_deep_upper(self):
        """
        Going deep in the root will block at root folder.
        """
        segments = self.unlocked_filesystem.getSegments(
            u'../../../../../../B')
        self.assertEqual([u'B'], segments)

    def test_getRealPathFromSegments_unix(self):
        """
        Check getting real path for Unix.
        """
        if os.name != 'posix':
            raise self.skipTest()

        path = self.unlocked_filesystem.getRealPathFromSegments([])
        self.assertEqual(u'/', path)

        path = self.unlocked_filesystem.getRealPathFromSegments([u'caca'])
        self.assertEqual(u'/caca', path)

        path = self.unlocked_filesystem.getRealPathFromSegments(
            [u'caca', u'maca raca'])
        self.assertEqual(u'/caca/maca raca', path)

        path = self.unlocked_filesystem.getRealPathFromSegments(None)
        self.assertEqual(u'/', path)

        segments = [u'ceva', u'..', u'altceva']
        path = self.unlocked_filesystem.getRealPathFromSegments(segments)
        self.assertEqual(u'/altceva', path)

        segments = [u'ceva', u'.', u'altceva']
        path = self.unlocked_filesystem.getRealPathFromSegments(segments)
        self.assertEqual(u'/ceva/altceva', path)

        segments = [u'..', u'..', u'altceva']
        path = self.unlocked_filesystem.getRealPathFromSegments(segments)
        self.assertEqual(u'/altceva', path)

    @conditionals.onOSFamily('nt')
    def test_getRealPathFromSegments_nt(self):
        """
        Check getting real path for Windows.
        """
        path = self.unlocked_filesystem.getRealPathFromSegments([])
        self.assertEqual(u'c:\\', path)

        path = self.unlocked_filesystem.getRealPathFromSegments([u'c'])
        self.assertEqual(u'c:\\', path)

        path = self.unlocked_filesystem.getRealPathFromSegments(
            [u'o', u'maca raca'])
        self.assertEqual(u'o:\\maca raca', path)

        path = self.unlocked_filesystem.getRealPathFromSegments(None)
        self.assertEqual(u'c:\\', path)

        # Path is resolved to absolute path.
        segments = [u'ceva', u'..', u'd', u'altceva']
        path = self.unlocked_filesystem.getRealPathFromSegments(segments)
        self.assertEqual(u'd:\\altceva', path)

        # When path starts with a valid driver, it is kept.
        segments = [u'c', u'..', u'..', u'dad']
        path = self.unlocked_filesystem.getRealPathFromSegments(segments)
        self.assertEqual(u'c:\\dad', path)

        segments = [u'g', u'.', u'altceva']
        path = self.unlocked_filesystem.getRealPathFromSegments(segments)
        self.assertEqual(u'g:\\altceva', path)

        segments = [u'..', u'..', u'd']
        path = self.unlocked_filesystem.getRealPathFromSegments(segments)
        self.assertEqual(u'd:\\', path)

        segments = [u'..', u'..', u't', u'dad']
        path = self.unlocked_filesystem.getRealPathFromSegments(segments)
        self.assertEqual(u't:\\dad', path)

    @conditionals.onOSFamily('nt')
    def test_getRealPathFromSegments_nt_invalid_drive(self):
        """
        An error is raised when trying to get an path with invalid drive.
        """
        with self.assertRaises(OSError):
            segments = [u'..', u'..', u'bad']
            self.unlocked_filesystem.getRealPathFromSegments(segments)

        with self.assertRaises(OSError):
            segments = [u'bad']
            self.unlocked_filesystem.getRealPathFromSegments(segments)

        with self.assertRaises(OSError):
            segments = [u'bad', u'drive']
            self.unlocked_filesystem.getRealPathFromSegments(segments)

    def test_root_segments(self):
        """
        Does not allow creating new things into root.
        """
        with self.assertRaises(OSError):
            self.unlocked_filesystem.createFolder(['new-root-element'])

    def test_getFolderContent_root_nt(self):
        """
        When listing the content for Windows _root_ folder, all local drives
        are listed.

        For us on Windows, _root_ folder is something similar to
        "My Computer".
        """
        # This test applies only for windows as the root folder is a meta
        # folder containing the Local drives.
        if os.name != 'nt':
            raise self.skipTest()
        content = self.unlocked_filesystem.getFolderContent([])
        self.assertTrue(len(content) > 0)
        self.assertContains(u'C', content)

        parent_content = self.unlocked_filesystem.getFolderContent(['..'])
        self.assertEqual(content, parent_content)

        parent_content = self.unlocked_filesystem.getFolderContent(['.'])
        self.assertEqual(content, parent_content)

    def test_getFolderContent_root_child_nt(self):
        """
        Check getting folder content for a drive on Windows.
        """
        if os.name != 'nt':
            raise self.skipTest()
        content = self.unlocked_filesystem.getFolderContent(['c'])
        self.assertTrue(len(content) > 0)
        self.assertTrue(u'Program Files' in content)
        self.assertTrue(isinstance(content[0], text_type))

    def test_getSegmentsFromRealPath_none(self):
        """
        The empty segments is return if path is None.
        """
        path = None
        segments = self.unlocked_filesystem.getSegmentsFromRealPath(path)
        self.assertEqual([], segments)

    def test_getSegmentsFromRealPath_relative(self):
        """
        Relative segments can be used for obtaining real path.
        """
        path = u'some_path'
        relative_segments = (
            self.unlocked_filesystem.getSegmentsFromRealPath(path))
        absolute_path = os.path.abspath(path)
        absolute_segments = (
            self.unlocked_filesystem.getSegmentsFromRealPath(absolute_path))
        self.assertEqual(absolute_segments, relative_segments)

    def test_getSegmentsFromRealPath_unix(self):
        """
        Check getting real OS path for Unix.
        """
        if os.name != 'posix':
            raise self.skipTest()

        path = u''
        segments = self.unlocked_filesystem.getSegmentsFromRealPath(path)
        self.assertEqual([], segments)

        path = u'/'
        segments = self.unlocked_filesystem.getSegmentsFromRealPath(path)
        self.assertEqual([], segments)

        path = u'/some/thing'
        segments = self.unlocked_filesystem.getSegmentsFromRealPath(path)
        self.assertEqual([u'some', u'thing'], segments)

        path = u'/some/thing/'
        segments = self.unlocked_filesystem.getSegmentsFromRealPath(path)
        self.assertEqual([u'some', u'thing'], segments)

    def test_getSegmentsFromRealPath_nt(self):
        """
        Check getting real OS path for Windows.
        """
        if os.name != 'nt':
            raise self.skipTest()
        path = u''
        segments = self.unlocked_filesystem.getSegmentsFromRealPath(path)
        self.assertEqual([], segments)

        path = u'c:\\'
        segments = self.unlocked_filesystem.getSegmentsFromRealPath(path)
        self.assertEqual([u'c'], segments)

        path = u'c:\\Temp'
        segments = self.unlocked_filesystem.getSegmentsFromRealPath(path)
        self.assertEqual([u'c', u'Temp'], segments)

        path = u'c:\\Temp\\'
        segments = self.unlocked_filesystem.getSegmentsFromRealPath(path)
        self.assertEqual([u'c', u'Temp'], segments)

        path = u'c:\\Temp\\Other path'
        segments = self.unlocked_filesystem.getSegmentsFromRealPath(path)
        self.assertEqual([u'c', u'Temp', u'Other path'], segments)

    def test_getRealPathFromSegments_fix_bad_path_nt(self):
        """
        When Unix folder separators are used for Windows path, the
        filesystem will convert them without any errors or warnings.
        """
        if os.name != 'nt':
            raise self.skipTest()

        avatar = DefaultAvatar()
        avatar.home_folder_path = 'c:/Temp/some/path'
        avatar.root_folder_path = None
        avatar.lock_in_home_folder = False

        filesystem = LocalFilesystem(avatar=avatar)

        self.assertEqual(
            u'c:\\', filesystem.getRealPathFromSegments([]))
        self.assertEqual(
            u'c:\\Temp', filesystem.getRealPathFromSegments([u'c', u'Temp']))
        self.assertEqual(
            [u'c', u'Temp', u'some', u'path'], filesystem.home_segments)

    @conditionals.onCapability('symbolic_link', True)
    def test_exists_broken_link(self):
        """
        Will return false when link target does not exists.
        """
        _, self.test_segments = mk.fs.makePathInTemp()
        self.unlocked_filesystem.makeLink(
            target_segments=['z', 'no-such', 'target'],
            link_segments=self.test_segments,
            )

        self.assertFalse(self.unlocked_filesystem.exists(self.test_segments))
        # Link still exists.
        self.assertTrue(self.unlocked_filesystem.isLink(self.test_segments))

    @conditionals.onCapability('symbolic_link', True)
    def test_exists_link_broken_link(self):
        """
        Resolve recursive links to links.
        """
        _, self.test_segments = mk.fs.makePathInTemp()
        self.unlocked_filesystem.makeLink(
            target_segments=['z', 'no-such', 'target'],
            link_segments=self.test_segments,
            )
        link_to_broken_link = self.makeLink(self.test_segments)

        self.assertFalse(self.unlocked_filesystem.exists(link_to_broken_link))
        # Link still exists.
        self.assertTrue(self.unlocked_filesystem.isLink(link_to_broken_link))


class TestLocalFilesystemLocked(CompatTestCase, FilesystemTestMixin):
    """
    Tests for locked filesystem.
    """

    @classmethod
    def setUpClass(cls):
        cls.locked_avatar = DefaultAvatar()
        cls.locked_avatar.root_folder_path = mk.fs.temp_path
        cls.locked_avatar.home_folder_path = mk.fs.temp_path
        cls.locked_avatar.lock_in_home_folder = True
        cls.locked_filesystem = LocalFilesystem(avatar=cls.locked_avatar)
        cls.filesystem = cls.locked_filesystem

    def test_getSegments_locked(self):
        """
        Check getSegments for a locked filesystem.
        """
        segments = self.locked_filesystem.getSegments(None)
        self.assertEqual([], segments)

        segments = self.locked_filesystem.getSegments('')
        self.assertEqual([], segments)

        segments = self.locked_filesystem.getSegments('.')
        self.assertEqual([], segments)

        segments = self.locked_filesystem.getSegments('..')
        self.assertEqual([], segments)

        segments = self.locked_filesystem.getSegments(u'Caca')
        self.assertEqual([u'Caca'], segments)

        segments = self.locked_filesystem.getSegments(u'/cAca')
        self.assertEqual([u'cAca'], segments)

        segments = self.locked_filesystem.getSegments(u'One/other Folder')
        self.assertEqual([u'One', u'other Folder'], segments)

        segments = self.locked_filesystem.getSegments(u'/One/other Folder')
        self.assertEqual([u'One', u'other Folder'], segments)

        segments = self.locked_filesystem.getSegments(u'/One/other Folder/')
        self.assertEqual([u'One', u'other Folder'], segments)

        segments = self.locked_filesystem.getSegments(u'onE/../tWo')
        self.assertEqual([u'tWo'], segments)

        segments = self.locked_filesystem.getSegments(u'/onE/../tWo')
        self.assertEqual([u'tWo'], segments)

        segments = self.locked_filesystem.getSegments(u'../././b')
        self.assertEqual([u'b'], segments)

        segments = self.locked_filesystem.getSegments(u'./././b')
        self.assertEqual([u'b'], segments)

        segments = self.locked_filesystem.getSegments(u'/././b')
        self.assertEqual([u'b'], segments)

        # Non unicode text will be converted to unicode
        segments = self.locked_filesystem.getSegments('/cAca')
        self.assertEqual([u'cAca'], segments)

        segments = self.locked_filesystem.getSegments('m\xc8\x9b')
        self.assertEqual([u'm\u021b'], segments)

    def test_getRealPathFromSegments(self):
        """
        Test conversion of segments to a real path.
        """
        def _p(*path):
            return text_type(
                os.path.join(self.locked_avatar.root_folder_path, *path))

        path = self.locked_filesystem.getRealPathFromSegments([])
        self.assertEqual(_p(), path)

        path = self.locked_filesystem.getRealPathFromSegments(None)
        self.assertEqual(_p(), path)

        path = self.locked_filesystem.getRealPathFromSegments([u'.caca'])
        self.assertEqual(_p(u'.caca'), path)

        path = self.locked_filesystem.getRealPathFromSegments([u'..caca'])
        self.assertEqual(_p(u'..caca'), path)

        path = self.locked_filesystem.getRealPathFromSegments([u'ca.ca'])
        self.assertEqual(_p(u'ca.ca'), path)

        path = self.locked_filesystem.getRealPathFromSegments([u'ca..ca'])
        self.assertEqual(_p(u'ca..ca'), path)

        path = self.locked_filesystem.getRealPathFromSegments([u'caca.'])
        self.assertEqual(_p(u'caca.'), path)

        path = self.locked_filesystem.getRealPathFromSegments([u'caca..'])
        self.assertEqual(_p(u'caca..'), path)

        path = self.locked_filesystem.getRealPathFromSegments([u'ca', u'a r'])
        self.assertEqual(_p(u'ca', u'a r'), path)

        path = self.locked_filesystem.getRealPathFromSegments([u'..'])
        self.assertEqual(_p(), path)

        path = self.locked_filesystem.getRealPathFromSegments([u'.'])
        self.assertEqual(_p(), path)

        path = self.locked_filesystem.getRealPathFromSegments([u'..', u'a'])
        self.assertEqual(_p(u'a'), path)

        path = self.locked_filesystem.getRealPathFromSegments(
            [u'..', u'a', u'..', u'b'])
        self.assertEqual(_p(u'b'), path)

    def test_getRealPathFromSegments_fix_bad_path_nt(self):
        """
        When Unix folder separators are used for Windows path, the
        filesystem will convert them without any errors or warnings.
        """
        if os.name != 'nt':
            raise self.skipTest()
        avatar = DefaultAvatar()
        avatar.home_folder_path = 'c:/Temp'
        avatar.root_folder_path = avatar.home_folder_path
        avatar.lock_in_home_folder = True

        filesystem = LocalFilesystem(avatar=avatar)

        self.assertEqual(u'c:\\Temp', filesystem.getRealPathFromSegments([]))
        self.assertEqual([], filesystem.home_segments)

    def test_getSegmentsFromRealPath(self):
        """
        Return locked segments for a real path.
        """
        separator = os.sep
        root_path = self.locked_avatar.root_folder_path

        result = self.locked_filesystem.getSegmentsFromRealPath(root_path)
        self.assertEqual([], result)

        result = self.locked_filesystem.getSegmentsFromRealPath(
            root_path + separator)
        self.assertEqual([], result)

        name = mk.string()
        result = self.locked_filesystem.getSegmentsFromRealPath(
            root_path + separator + name)
        self.assertEqual([name], result)

        name = mk.string()
        child = mk.string()
        result = self.locked_filesystem.getSegmentsFromRealPath(
            root_path + separator + name + separator + child + separator)
        self.assertEqual([name, child], result)

    @conditionals.onOSFamily('posix')
    def test_getSegmentsFromRealPath_outside_home_unix(self):
        """
        Raise CompatError when path is outside of home.
        """
        with self.assertRaises(CompatError):
            self.locked_filesystem.getSegmentsFromRealPath('/outside/path')

        with self.assertRaises(CompatError):
            self.locked_filesystem.getSegmentsFromRealPath('../../outside')

    @conditionals.onOSFamily('nt')
    def test_getSegmentsFromRealPath_outside_home_nt(self):
        """
        Raise CompatError when path is outside of home.
        """
        with self.assertRaises(CompatError):
            self.locked_filesystem.getSegmentsFromRealPath('c:\\outside\\home')

        with self.assertRaises(CompatError):
            self.locked_filesystem.getSegmentsFromRealPath('..\\..\\outside')

    @conditionals.onCapability('symbolic_link', True)
    def test_exists_outside_link(self):
        """
        Will return false when link target is outside of home folder.
        """
        _, self.test_segments = mk.fs.makePathInTemp()
        link_segments = [self.test_segments[-1]]
        mk.fs.makeLink(
            target_segments=['z', 'no', 'such'],
            link_segments=self.test_segments,
            )
        # Make sure link was created.
        self.assertTrue(self.locked_filesystem.isLink(link_segments))

        self.assertFalse(self.locked_filesystem.exists(link_segments))

    @conditionals.onCapability('symbolic_link', True)
    def test_readLink_outside_home(self):
        """
        Raise an error when target is outside of locked folder.
        """
        _, self.test_segments = mk.fs.makePathInTemp()
        link_segments = [self.test_segments[-1]]
        mk.fs.makeLink(
            target_segments=['z', 'no', 'such'],
            link_segments=self.test_segments,
            )
        # Make sure link was created.
        self.assertTrue(self.locked_filesystem.isLink(link_segments))

        with self.assertRaises(CompatError):
            self.locked_filesystem.readLink(link_segments)


class TestFileAttributes(CompatTestCase):
    """
    Unit test for the FileAttributes.
    """

    def test_init(self):
        """
        Check initialization with minimum arguments.
        """
        name = mk.string()
        path = os.path.join(mk.string(), name)

        sut = FileAttributes(name=name, path=path)

        self.assertProvides(IFileAttributes, sut)
        self.assertEqual(name, sut.name)
        self.assertEqual(path, sut.path)
        self.assertEqual(0, sut.size)
        self.assertIsFalse(sut.is_file)
        self.assertIsFalse(sut.is_folder)
        self.assertIsFalse(sut.is_link)
        self.assertEqual(0, sut.modified)
        self.assertEqual(0, sut.mode)
        self.assertEqual(1, sut.hardlinks)
        self.assertIsNone(sut.uid)
        self.assertIsNone(sut.gid)
        self.assertIsNone(sut.owner)
        self.assertIsNone(sut.group)
        self.assertIsNone(sut.node_id)

    def test_init_all_arguments(self):
        """
        Check initialization with all arguments.
        """
        name = mk.string()
        path = os.path.join(mk.string(), name)

        sut = FileAttributes(
            name=name,
            path=path,
            size=990,
            is_file=True,
            is_folder=True,
            is_link=True,
            modified=1234,
            mode=0x640,
            hardlinks=2,
            uid=12,
            gid=42,
            owner=u'john',
            group=u'adm',
            node_id=12345678910,
            )

        self.assertProvides(IFileAttributes, sut)
        self.assertEqual(name, sut.name)
        self.assertEqual(path, sut.path)
        self.assertEqual(990, sut.size)
        self.assertIsTrue(sut.is_file)
        self.assertIsTrue(sut.is_folder)
        self.assertIsTrue(sut.is_link)
        self.assertEqual(1234, sut.modified)
        self.assertEqual(0x640, sut.mode)
        self.assertEqual(2, sut.hardlinks)
        self.assertEqual(12, sut.uid)
        self.assertEqual(42, sut.gid)
        self.assertEqual(u'john', sut.owner)
        self.assertEqual(u'adm', sut.group)
        self.assertEqual(12345678910, sut.node_id)

    def test_equality(self):
        """
        Objects with same attributes are equal.
        """
        name = mk.string()
        path = os.path.join(mk.string(), name)

        sut1 = FileAttributes(name=name, path=path)
        sut2 = FileAttributes(name=name, path=path)

        self.assertEqual(sut1, sut2)

    def test_inequality(self):
        """
        Objects with different attributes are not equal.
        """
        name = mk.string()
        path = os.path.join(mk.string(), name)

        sut1 = FileAttributes(name=name, path=path)
        sut2 = FileAttributes(name=name, path='other-path')

        self.assertNotEqual(sut1, sut2)
        self.assertNotEqual(None, sut1)
        self.assertNotEqual(sut1, None)
        self.assertNotEqual(object(), sut1)
        self.assertNotEqual(sut1, object())
