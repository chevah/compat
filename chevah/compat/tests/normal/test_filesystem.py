# Copyright (c) 2010 Adi Roiban.
# See LICENSE for details.
"""
Tests for portable filesystem access.
"""
from __future__ import absolute_import, division, unicode_literals
from six import text_type

from datetime import date
import errno
import os
import platform
import stat
import subprocess
import sys
import tempfile
import time

from nose.plugins.attrib import attr

from chevah.compat import DefaultAvatar, FileAttributes, LocalFilesystem
from chevah.compat.avatar import FilesystemApplicationAvatar
from chevah.compat.exceptions import CompatError
from chevah.compat.helpers import force_unicode
from chevah.compat.interfaces import IFileAttributes, ILocalFilesystem
from chevah.compat.testing import CompatTestCase, conditionals, mk

start_of_year = time.mktime((
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


class FilesystemTestingHelpers(object):
    """
    Common code for running filesystem tests.
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

    @classmethod
    def addWindowsShare(cls, path, name):
        """
        Export that `path` on local server as a Windows share without password
        and with full access.
        """
        import win32net
        import win32netcon

        # See: https://msdn.microsoft.com/
        #   en-us/library/windows/desktop/bb525408.aspx
        share_info_2 = {
            'netname': name,
            'type': win32netcon.STYPE_DISKTREE,
            'remark': 'created by chevah.compat tests',
            'permissions': 0,  # Ignored as Windows run in user-permissions.
            'max_uses': -1,  # No limits.
            'current_uses': 0,  # Ignored here.
            'path': path,
            'password': '',  # Ignored as Win has no share-level permissions.
            }
        win32net.NetShareAdd(None, 2, share_info_2)

    @classmethod
    def removeWindowsShare(cls, name):
        """
        Stop export the Windows share with `name` from local system.
        """
        import win32net
        win32net.NetShareDel(None, name)

    def makeWindowsShare(self, path, name):
        """
        Export that `path` on local server as a Windows share without password
        and with full access.

        Will remote the share at the end of the test.
        """
        self.addWindowsShare(path, name)
        self.addCleanup(self.removeWindowsShare, name)


class FilesystemTestMixin(FilesystemTestingHelpers):
    """
    Common tests for filesystem for all OSes.
    """

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

        segments = self.filesystem.getSegments("//./a/b'c/d")
        self.assertEqual(['a', "b'c", 'd'], segments)

        segments = self.filesystem.getSegments("/a/b - c/d")
        self.assertEqual(['a', "b - c", 'd'], segments)

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

        path = self.filesystem.getPath(['.', 'a', "B'Quote"])
        self.assertEqual("/a/B'Quote", path)

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


class DefaultFilesystemTestCase(CompatTestCase, FilesystemTestMixin):
    """
    Test with the default filesystem.
    """
    @classmethod
    def setUpClass(cls):
        super(DefaultFilesystemTestCase, cls).setUpClass()
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


class TestLocalFilesystem(DefaultFilesystemTestCase):
    """
    Test for default local filesystem which does not depend on attached
    avatar or operating system.
    """

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

    @conditionals.onOSFamily('nt')
    def test_temp_segments_location_nt(self):
        """
        On Windows for non impersonated account, the temporary folder
        is located inside the user temporary folder and not on c:\temp.
        """
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

    def test_convertToOSError_IOError(self):
        """
        Convert IOError to OSError using a context, and add the path if error
        is missing the path.
        """
        path = '/some/path-\N{snowman}'
        message = 'Message \N{sun} day'

        with self.assertRaises(OSError) as context:
            with self.filesystem._convertToOSError(path):
                raise IOError(3, message)

        self.assertEqual(3, context.exception.errno)

        expected = '[Errno 3] Message \u2609 day: /some/path-\u2603'
        self.assertEqual(expected, force_unicode(context.exception))

    def test_convertToOSError_OSError(self):
        """
        Keep OSError and don't add the path when the exception already has
        a path.
        """
        path = '/some/path-\N{snowman}'
        message = 'Message \N{sun} day'

        with self.assertRaises(OSError) as context:
            with self.filesystem._convertToOSError(path):
                raise OSError(3, message, 'other-path')

        self.assertEqual(3, context.exception.errno)

        expected = '[Errno 3] Message \u2609 day: other-path'
        self.assertEqual(expected, force_unicode(context.exception))

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
        self.assertTrue(self.filesystem.exists(self.test_segments))
        expected = '[Errno 21] Is a directory: ' + path
        self.assertStartsWith(expected, force_unicode(context.exception))

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
        path = mk.fs.getRealPathFromSegments(segments)

        with self.assertRaises(OSError) as context:
            self.filesystem.deleteFile(segments)

        self.assertEqual(errno.ENOENT, context.exception.errno)

        if self.TEST_LANGUAGE == 'FR':
            details = (
                '[Errno 2] Le fichier sp\xe9cifi\xe9 est introuvable: '
                + path
                )
        elif self.os_name == 'windows':
            details = (
                '[Errno 2] The system cannot find the file specified: '
                + path
                )
        else:
            details = '[Errno 2] No such file or directory: ' + path

        self.assertContains(
            details, force_unicode(context.exception))

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

    def test_deleteFolder_file_non_recursive(self):
        """
        Raise an OS error when trying to delete a file using folder API.
        """
        path, segments = self.tempFile()
        self.assertTrue(self.filesystem.exists(segments))

        with self.assertRaises(OSError) as context:
            self.filesystem.deleteFolder(segments, recursive=False)

        self.assertEqual(errno.ENOTDIR, context.exception.errno)
        self.assertTrue(self.filesystem.exists(segments))
        expected = '[Errno 20] Not a directory: ' + path
        self.assertEqual(expected, force_unicode(context.exception))

    def test_deleteFolder_file_recursive(self):
        """
        Raise an OS error when trying to delete a file using folder API,
        event when doing recursive delete.
        """
        path, segments = self.tempFile()
        self.assertTrue(self.filesystem.exists(segments))

        with self.assertRaises(OSError) as context:
            self.filesystem.deleteFolder(segments, recursive=True)

        self.assertEqual(errno.ENOTDIR, context.exception.errno)
        self.assertTrue(self.filesystem.exists(segments))
        expected = '[Errno 20] Not a directory: ' + path
        self.assertEqual(expected, force_unicode(context.exception))

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

    def test_deleteFolder_non_found(self):
        """
        Raise OSError when folder is not found.
        """
        segments = ['c', 'no-such', mk.string()]
        path = mk.fs.getRealPathFromSegments(segments)
        self.assertFalse(self.filesystem.exists(segments))

        with self.assertRaises(OSError) as context:
            self.filesystem.deleteFolder(segments, recursive=False)

        self.assertEqual(errno.ENOENT, context.exception.errno)

        if self.TEST_LANGUAGE == 'FR':
            expected = (
                '[Errno 2] Le chemin d\u2019acc\xe8s sp\xe9cifi\xe9 est '
                'introuvable: ' + path
                )
        elif self.os_name == 'windows':
            expected = (
                '[Errno 2] The system cannot find the path specified: '
                + path
                )
        else:
            expected = '[Errno 2] No such file or directory: ' + path

        self.assertEqual(expected, force_unicode(context.exception))

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
        _, segments = self.tempFile(content=content.encode('utf-8'))
        link_segments = segments[:]
        link_segments[-1] = '%s-link' % segments[-1]

        mk.fs.makeLink(
            target_segments=segments,
            link_segments=link_segments,
            )

        self.assertTrue(mk.fs.exists(link_segments))
        self.assertTrue(mk.fs.isLink(link_segments))
        # Will point to the same content.
        link_content = mk.fs.getFileContent(segments)
        self.assertEqual(content, link_content)
        # Can be removed as a simple file and target file is not removed.
        mk.fs.deleteFile(link_segments)
        self.assertFalse(mk.fs.exists(link_segments))
        self.assertTrue(mk.fs.exists(segments))

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

        self.assertTrue(self.filesystem.exists(self.test_segments))
        self.assertTrue(self.filesystem.isLink(self.test_segments))

    @conditionals.onOSFamily('nt')
    @conditionals.onCapability('symbolic_link', True)
    def test_makeLink_windows_share(self):
        """
        It can create links to a Windows share.
        """
        # We assume all slaves have the c:\temp folder.
        share_name = 'share-name ' + mk.string()
        self.makeWindowsShare(path='c:\\temp', name=share_name)
        path, segments = mk.fs.makePathInTemp()
        self.addCleanup(self.filesystem.deleteFolder, segments)
        filename = mk.makeFilename()
        file_segments = ['c', 'temp', filename]
        data = mk.string() * 100
        mk.fs.writeFileContent(file_segments, content=data)

        self.filesystem.makeLink(
            target_segments=['UNC', '127.0.0.1', share_name],
            link_segments=segments,
            )

        # We can list the folder of the linked folder and do file operations
        # on its content.
        result = self.filesystem.getFolderContent(segments)
        self.assertContains(filename, result)
        self.assertTrue(self.filesystem.exists(segments))
        self.assertTrue(self.filesystem.isFolder(segments))
        result = self.filesystem.getFileSize(segments)
        self.assertEqual(0, result)
        result = self.filesystem.getFileSize(file_segments)
        self.assertEqual(len(data.encode('utf-8')), result)
        self.filesystem.deleteFile(file_segments)

    @conditionals.onOSFamily('nt')
    @conditionals.onCapability('symbolic_link', True)
    def test_makeLink_windows_share_invalid(self):
        """
        It can create links to a non-existent Windows share.
        """
        path, segments = self.tempPath()
        # We assume all slaves have the c:\temp folder.
        share_name = 'no such share name-' + mk.string()
        self.filesystem.makeLink(
            target_segments=['UNC', '127.0.0.1', share_name],
            link_segments=segments,
            )
        self.addCleanup(self.filesystem.deleteFolder, segments)

        self.assertTrue(os.path.exists(path))
        self.assertEqual(
            ['UNC', '127.0.0.1', share_name],
            self.filesystem.readLink(segments))
        result = self.filesystem.exists(segments)
        self.assertTrue(result)

    # Raw data returned from reparse point.
    # print_name and target_name is  u'c:\\temp\\str1593-cp\u021b'
    raw_reparse_buffer = (
        b'\x0c\x00\x00\xa0`\x00\x00\x00&\x00.\x00\x00\x00&\x00\x00\x00\x00'
        b'\x00c\x00:\x00\\\x00t\x00e\x00m\x00p\x00\\\x00s\x00t\x00r\x001\x005'
        b'\x009\x003\x00-\x00c\x00p\x00\x1b\x02\\\x00?\x00?\x00\\\x00c\x00:'
        b'\x00\\\x00t\x00e\x00m\x00p\x00\\\x00s\x00t\x00r\x001\x005\x009\x003'
        b'\x00-\x00c\x00p\x00\x1b\x02'
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

        Target is always returned in Long UNC.
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
        self.assertEqual(
            u'\\\\?\\c:\\temp\\str1593-cp\u021b', result['target'])

    @conditionals.onCapability('symbolic_link', True)
    def test_readLink_ok(self):
        """
        Can be used for reading target for a link.
        """
        self.test_segments = mk.fs.createFileInTemp()
        link_segments = self.makeLink(self.test_segments)

        result = self.filesystem.readLink(link_segments)

        self.assertEqual(self.test_segments, result)

    @conditionals.onOSFamily('nt')
    @conditionals.onCapability('symbolic_link', True)
    def test_readLink_ok_created_outside(self):
        """
        Can be used for reading target for a link created with mklink /D
        command.
        """
        # We need to use ascii for os.system.
        name = mk.ascii()
        segments = ['c', 'temp', name]
        path = 'c:\\temp\\' + name
        subprocess.call('mklink /d %s \\\\127.0.0.1\\no-such-share' % (
            path,), shell=True)
        self.addCleanup(mk.fs.deleteFolder, segments)

        result = self.filesystem.readLink(segments)

        self.assertEqual(['UNC', '127.0.0.1', 'no-such-share'], result)

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
        segments = ['c', 'no-such-segments']
        path = mk.fs.getRealPathFromSegments(segments)
        with self.assertRaises(OSError) as context:
            self.filesystem.readLink(segments)

        self.assertEqual(errno.ENOENT, context.exception.errno)

        if self.TEST_LANGUAGE == 'FR':
            expected = (
                '[Errno 2] 2 - Le fichier sp\xe9cifi\xe9 est '
                'introuvable.: ' + path
                )
        elif self.os_name == 'windows':
            expected = (
                '[Errno 2] 2 - The system cannot find the file specified.: '
                + path
                )
        else:
            expected = '[Errno 2] No such file or directory: ' + path

        self.assertEqual(expected, force_unicode(context.exception))

    @conditionals.onCapability('symbolic_link', True)
    def test_readLink_not_link(self):
        """
        Raise an error when path is not a link.
        """
        path, segments = self.tempFile()

        with self.assertRaises(OSError) as context:
            self.filesystem.readLink(segments)

        self.assertEqual(errno.EINVAL, context.exception.errno)

        if self.TEST_LANGUAGE == 'FR':
            expected = (
                '[Errno 22] 4390 - Le fichier ou r\xe9pertoire n\u2019est '
                'pas un point d\u2019analyse.: ' + path
                )
        elif self.os_name == 'windows':
            expected = (
                '[Errno 22] 4390 - The file or directory is not a reparse '
                'point.: ' + path
                )
        else:
            expected = '[Errno 22] Invalid argument: ' + path

        self.assertEqual(expected, force_unicode(context.exception))

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
        _, segments = self.tempFile()
        _, non_existent_segments = mk.fs.makePathInTemp()

        self.assertTrue(self.filesystem.isFile(segments))
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
        _, segments = self.tempFolder()

        attributes = self.filesystem.getAttributes(segments)

        self.assertTrue(attributes.is_folder)
        self.assertFalse(attributes.is_file)
        self.assertFalse(attributes.is_link)
        self.assertNotEqual(0, attributes.node_id)
        self.assertIsNotNone(attributes.node_id)
        if self.os_family == 'posix':
            current_umask = mk.fs._getCurrentUmask()
            expected_mode = 0o40777 ^ current_umask
            self.assertEqual(expected_mode, attributes.mode)

    def test_getAttributes_root(self):
        """
        Check attributes for root.
        """
        attributes = self.filesystem.getAttributes([])

        self.assertTrue(attributes.is_folder)
        self.assertFalse(attributes.is_file)
        self.assertFalse(attributes.is_link)
        self.assertNotEqual(0, attributes.node_id)
        self.assertIsNotNone(attributes.node_id)
        # Root has no name.
        self.assertIsNone(attributes.name)
        if self.os_family == 'nt':
            self.assertEqual('c:\\', attributes.path)
        else:
            self.assertEqual('/', attributes.path)

    @conditionals.onCapability('symbolic_link', True)
    def test_getAttributes_link_file(self):
        """
        A link to a file is recognized as both a link and a file.
        """
        self.test_segments = mk.fs.createFileInTemp(content=b'blala')
        link_segments = self.makeLink(self.test_segments)

        attributes = self.filesystem.getAttributes(link_segments)

        self.assertTrue(attributes.is_file)
        self.assertTrue(attributes.is_link)
        self.assertFalse(attributes.is_folder)
        self.assertEqual(5, attributes.size)

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

        if self.TEST_LANGUAGE == 'FR':
            expected_path = path
            expected_message = (
                b'Le chemin d\x92acc\xe8s sp\xe9cifi\xe9 est introuvable')

        elif self.os_family == 'nt':
            expected_path = path
            expected_message = b'The system cannot find the path specified'
        else:
            expected_path = path.encode('utf-8')
            expected_message = b'No such file or directory'
        self.assertEqual(errno.ENOENT, error.errno)
        self.assertEqual(expected_path, error.filename)
        self.assertEqual(expected_message, error.strerror)

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

    def test_getFolderContent_not_found(self):
        """
        Raise OSError when trying to get folder for a non existent path.
        """
        segments = ['c', mk.string()]
        path = mk.fs.getRealPathFromSegments(segments)

        with self.assertRaises(OSError) as context:
            self.filesystem.getFolderContent(segments)

        self.assertEqual(errno.ENOENT, context.exception.errno)

        if self.TEST_LANGUAGE == 'FR':
            expected = (
                '[Errno 2] Le chemin d\u2019acc\xe8s sp\xe9cifi\xe9 est '
                'introuvable: ' + path + '\\*.*'
                )
        elif self.os_name == 'windows':
            expected = (
                '[Errno 2] The system cannot find the path specified: '
                + path + '\\*.*'
                )
        else:
            expected = '[Errno 2] No such file or directory: ' + path

        self.assertEqual(expected, force_unicode(context.exception))

    def test_getFolderContent_file(self):
        """
        Raise OSError when trying to get folder content for a file.
        """
        path, segments = self.tempFile()

        with self.assertRaises(OSError) as context:
            self.filesystem.getFolderContent(segments)

        self.assertEqual(errno.ENOTDIR, context.exception.errno)
        expected = '[Errno 20] Not a directory: ' + path
        self.assertEqual(expected, force_unicode(context.exception))

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
        path = mk.fs.getRealPathFromSegments(segments)

        with self.assertRaises(OSError) as context:
            self.filesystem.iterateFolderContent(segments)

        self.assertEqual(errno.ENOENT, context.exception.errno)

        if self.TEST_LANGUAGE == 'FR':
            expected = (
                '[Errno 2] Le chemin d\u2019acc\xe8s sp\xe9cifi\xe9 est '
                'introuvable: ' + path
                )
        elif self.os_name == 'windows':
            expected = (
                '[Errno 2] The system cannot find the path specified: '
                + path
                )
        else:
            expected = '[Errno 2] No such file or directory: ' + path

        self.assertEqual(expected, force_unicode(context.exception))

    @conditionals.skipOnPY3()
    def test_iterateFolderContent_file(self):
        """
        Raise OSError when trying to get folder content for a file.
        """
        segments = self.fileInTemp()
        path = mk.fs.getRealPathFromSegments(segments)

        with self.assertRaises(OSError) as context:
            self.filesystem.iterateFolderContent(segments)

        if self.os_family == 'nt':
            # On Windows, we get a different error.
            expected_error = errno.EINVAL
        else:
            expected_error = errno.ENOTDIR

        self.assertEqual(expected_error, context.exception.errno)

        if self.TEST_LANGUAGE == 'FR':
            expected = (
                '[Errno 22] Nom de r\xe9pertoire non valide: '
                + path
                )
        elif self.os_name == 'windows':
            expected = (
                '[Errno 22] The directory name is invalid: '
                + path
                )
        else:
            expected = '[Errno 20] Not a directory: ' + path
        self.assertEqual(expected, force_unicode(context.exception))

    @conditionals.skipOnPY3()
    def test_iterateFolderContent_empty(self):
        """
        Return empty iterator for empty folders.
        """
        segments = self.folderInTemp()

        result = self.filesystem.iterateFolderContent(segments)

        self.assertIteratorItemsEqual([], result)

    @conditionals.skipOnPY3()
    def test_iterateFolderContent_non_empty(self):
        """
        Return folder content as list of Unicode names.
        """
        base_segments = self.folderInTemp()
        file_name = mk.makeFilename(prefix='file-')
        folder_name = mk.makeFilename(prefix='folder-')
        file_segments = base_segments + [file_name]
        folder_segments = base_segments + [folder_name]
        mk.fs.createFile(file_segments, content=b'123456789')
        mk.fs.createFolder(folder_segments)

        content = self.filesystem.iterateFolderContent(base_segments)

        result = list(content)
        self.assertEqual(2, len(result))
        self.assertProvides(IFileAttributes, result[0])
        self.assertProvides(IFileAttributes, result[1])
        result = {r.name: r for r in result}
        folder_attributes = result[folder_name]
        self.assertTrue(folder_attributes.is_folder)
        self.assertFalse(folder_attributes.is_file)
        self.assertFalse(folder_attributes.is_link)

        file_attributes = result[file_name]
        self.assertFalse(file_attributes.is_folder)
        self.assertTrue(file_attributes.is_file)
        self.assertFalse(file_attributes.is_link)
        self.assertEqual(9, file_attributes.size)
        self.assertAlmostEqual(self.now(), file_attributes.modified, delta=5)

    @conditionals.skipOnPY3()
    @conditionals.onCapability('symbolic_link', True)
    def test_iterateFolderContent_broken_links(self):
        """
        Return placeholder for members with broken links.
        """
        base_segments = self.folderInTemp()
        file_name = mk.makeFilename(prefix='file-')
        folder_name = mk.makeFilename(prefix='folder-')
        link_name = mk.makeFilename(prefix='link-')
        file_segments = base_segments + [file_name]
        folder_segments = base_segments + [folder_name]
        link_segments = base_segments + [link_name]
        mk.fs.createFile(file_segments, content=b'123456789')
        mk.fs.createFolder(folder_segments)

        mk.fs.makeLink(
            target_segments=['z', 'no-such', 'target'],
            link_segments=link_segments,
            )

        content = self.filesystem.iterateFolderContent(base_segments)

        result = list(content)
        self.assertEqual(3, len(result))
        self.assertProvides(IFileAttributes, result[0])
        self.assertProvides(IFileAttributes, result[1])
        self.assertProvides(IFileAttributes, result[2])
        result = {r.name: r for r in result}
        folder_attributes = result[folder_name]
        self.assertTrue(folder_attributes.is_folder)
        self.assertFalse(folder_attributes.is_file)
        self.assertFalse(folder_attributes.is_link)

        file_attributes = result[file_name]
        self.assertFalse(file_attributes.is_folder)
        self.assertTrue(file_attributes.is_file)
        self.assertFalse(file_attributes.is_link)
        self.assertEqual(9, file_attributes.size)
        self.assertAlmostEqual(self.now(), file_attributes.modified, delta=5)

        link_attributes = result[link_name]
        self.assertFalse(link_attributes.is_folder)
        self.assertFalse(link_attributes.is_file)
        self.assertTrue(link_attributes.is_link)
        self.assertAlmostEqual(self.now(), link_attributes.modified, delta=5)

    @attr('slow')
    @conditionals.skipOnPY3()
    def test_iterateFolderContent_big(self):
        """
        It will not block on listing folders with many members.

        On some systems, this test takes more than 1 minute.
        """
        final_error = None
        for _ in range(3):  # pragma: no branch
            try:
                self._iterateFolderContent_big()
                # All good. Stop trying.
                return
            except AssertionError as error:
                final_error = error
                # Run cleanup and try again.
                self.callCleanup()

        # We tried 3 times and still got a failure.
        raise final_error  # noqa:cover

    def _iterateFolderContent_big(self):
        """
        Main code for running the test
        """
        if self.os_name == 'aix':
            count = 3000
            base_timeout = 0.02
        elif self.os_name == 'osx':
            count = 32000
            base_timeout = 0.1
        elif self.os_name in ['hpux', 'freebsd', 'openbsd']:
            # Some OS/FS does not allow more than 32765 members in a folder
            # and the slave is generally slow.
            count = 32000
            base_timeout = 0.15
        elif self.cpu_type in ['sparc', 'arm64']:
            count = 5000
            base_timeout = 0.1
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
        expected = '[Errno 21] Is a directory: ' + path
        self.assertStartsWith(expected, force_unicode(context.exception))

    def test_openFileForReading_folder(self):
        """
        Raise OSError when trying to open a folder as file for reading.
        """
        self.test_segments = mk.fs.createFolderInTemp()
        path = mk.fs.getRealPathFromSegments(self.test_segments)

        with self.assertRaises(OSError) as context:
            self.filesystem.openFileForReading(self.test_segments)

        self.assertEqual(errno.EISDIR, context.exception.errno)
        details = '[Errno 21] Is a directory: ' + path
        self.assertStartsWith(details, force_unicode(context.exception))

    def test_openFileForWriting_folder(self):
        """
        Raise OSError when trying to open a folder as file for writing.
        """
        self.test_segments = mk.fs.createFolderInTemp()
        path = mk.fs.getRealPathFromSegments(self.test_segments)

        with self.assertRaises(OSError) as context:
            self.filesystem.openFileForWriting(self.test_segments)

        self.assertEqual(errno.EISDIR, context.exception.errno)
        self.assertEqual(path.encode('utf-8'), context.exception.filename)
        details = '[Errno 21] Is a directory: ' + path
        self.assertStartsWith(details, force_unicode(context.exception))

    def test_openFileForAppending_folder(self):
        """
        Raise OSError when trying to open a folder as file for appending.
        """
        self.test_segments = mk.fs.createFolderInTemp()
        path = mk.fs.getRealPathFromSegments(self.test_segments)

        with self.assertRaises(OSError) as context:
            self.filesystem.openFileForAppending(
                self.test_segments)

        self.assertEqual(errno.EISDIR, context.exception.errno)
        self.assertEqual(path.encode('utf-8'), context.exception.filename)
        details = '[Errno 21] Is a directory: ' + path
        self.assertStartsWith(details, force_unicode(context.exception))

    def test_touch_no_parent(self):
        """
        Raise an error when path does not exists and can not be created.
        """
        segments = ['c', 'no-such', 'path']
        path = mk.fs.getRealPathFromSegments(segments)

        with self.assertRaises(IOError) as context:
            self.filesystem.touch(segments)

        self.assertEqual(errno.ENOENT, context.exception.errno)
        details = '[Errno 2] No such file or directory: ' + path
        self.assertEqual(details, force_unicode(context.exception))

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
        path = mk.fs.getRealPathFromSegments(destination_segments)

        with self.assertRaises(IOError) as context:
            self.filesystem.copyFile(self.test_segments, destination_segments)

        self.assertEqual(errno.ENOENT, context.exception.errno)
        details = '[Errno 2] No such file or directory: ' + path
        self.assertEqual(details, force_unicode(context.exception))

    def test_copyFile_file_destination_exists_no_overwrite(self):
        """
        Raise an error when destination exists and it was not instructed to
        overwrite existing files.
        """
        source_segments = ['ignore', 'source']
        path, segments = self.tempFile()

        with self.assertRaises(OSError) as context:
            self.filesystem.copyFile(source_segments, segments)

        self.assertEqual(errno.EEXIST, context.exception.errno)
        details = '[Errno 17] Destination exists: ' + path
        self.assertEqual(details, force_unicode(context.exception))

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
        path = mk.fs.getRealPathFromSegments(
            destination_segments + self.test_segments[-1:])
        source_segments = ['bla', self.test_segments[-1]]

        with self.assertRaises(OSError) as context:
            self.filesystem.copyFile(source_segments, destination_segments)

        self.assertEqual(errno.EEXIST, context.exception.errno)
        details = '[Errno 17] Destination exists: ' + path
        self.assertEqual(details, force_unicode(context.exception))

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

    def test_rename_file_overwrite_destination(self):
        """
        It will overwrite existing file.
        """
        _, source_segments = self.tempFile(prefix='src-', cleanup=False)
        _, destination_segments = self.tempFile(prefix='dst-')
        self.assertTrue(self.filesystem.exists(source_segments))
        self.assertTrue(self.filesystem.exists(destination_segments))

        self.filesystem.rename(source_segments, destination_segments)

        self.assertFalse(self.filesystem.exists(source_segments))
        self.assertTrue(self.filesystem.exists(destination_segments))

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
        self.test_segments.append(mk.makeFilename(suffix='low'))
        with (self.filesystem.openFileForWriting(
                self.test_segments)) as new_file:
            new_file.write(mk.getUniqueString().encode('utf8'))

        self.assertTrue(self.filesystem.exists(self.test_segments))

        segments_case = self.test_segments[:]
        segments_case[-1] = (
            segments_case[-1][:-3] + segments_case[-1][-3:].upper())
        if self.os_name in ['windows', 'osx']:
            # On Windows, the operations are case insensitive.
            self.assertTrue(self.filesystem.exists(segments_case))
        else:
            self.assertFalse(self.filesystem.exists(segments_case))

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

            a_file = self.filesystem.openFileForReading(self.test_segments)

            self.assertEqual(content, a_file.read().decode('utf-8'))
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

            self.assertEqual(b'', a_file.read())
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

    def test_openFileForReading_no_delete_lock(self):
        """
        A file opened only for reading will not be locked for delete
        operations.
        """
        _, segments = mk.fs.makePathInTemp()
        mk.fs.writeFileContent(segments=segments, content='something-\N{sun}')
        a_file = None
        try:
            a_file = self.filesystem.openFileForReading(segments)

            self.filesystem.deleteFile(segments)

            content = a_file.read(100)
            self.assertEqual(b'something-\xe2\x98\x89', content)
        finally:
            if a_file:
                a_file.close()

    def test_openFile_read_no_delete_lock(self):
        """
        A file opened only for reading will not be locked for delete
        operations.
        """
        _, segments = mk.fs.makePathInTemp()
        mk.fs.writeFileContent(segments=segments, content='something-\N{sun}')
        fd = None
        try:
            fd = self.filesystem.openFile(
                segments,
                flags=self.filesystem.OPEN_READ_ONLY,
                mode=0,
                )

            self.filesystem.deleteFile(segments)

            content = os.read(fd, 100)
            self.assertEqual(b'something-\xe2\x98\x89', content)
        finally:
            if fd:
                os.close(fd)

    def test_openFileForWriting_ascii(self):
        """
        Check opening a file for writing in plain/ascii/str mode.

        It will create the file if it doesn't exists with owner only
        permisisons.
        """
        content = b'some ascii text'
        _, segments = self.tempPathCleanup()
        self.assertFalse(mk.fs.exists(segments))

        sut = self.filesystem.openFileForWriting(segments)
        sut.write(content)
        sut.close()

        result = self.filesystem.getAttributes(segments)
        self.assertEqual(result.mode | 0o600, result.mode)

        a_file = self.filesystem.openFileForReading(segments)
        test_content = a_file.read()
        a_file.close()
        self.assertEqual(test_content, content)

    def test_openFileForWriting_mode(self):
        """
        You can specify the file permissions for the newly created file.
        """
        _, segments = self.tempPathCleanup()

        sut = self.filesystem.openFileForWriting(segments, mode=0o642)
        self.addCleanup(sut.close)
        sut.write(b'some data')

        if self.os_family == 'posix':
            result = self.filesystem.getAttributes(segments)
            # The umask will overwrite the requested attributes.
            self.assertEqual(0o640, result.mode & 0o640)

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
        if self.os_family == 'posix':
            result = self.filesystem.setAttributes(
                self.test_segments, {'mode': 0o666})

        # Write new content into file.
        test_file = self.filesystem.openFileForWriting(
            self.test_segments)
        test_file.write(new_content.encode('utf-8'))
        test_file.close()

        file_content = mk.fs.getFileContent(self.test_segments)
        self.assertEqual(new_content, file_content)

        if self.os_family == 'posix':
            # It will not overwrite the permissions for existing files.
            result = self.filesystem.getAttributes(self.test_segments)
            self.assertEqual(0o666, result.mode & 0o666)

    def test_openFileForAppending(self):
        """
        System test for openFileForAppending.
        """
        content = mk.getUniqueString()
        new_content = mk.getUniqueString()
        self.test_segments = mk.fs.createFileInTemp(content=content)

        if self.os_family == 'posix':
            result = self.filesystem.setAttributes(
                self.test_segments, {'mode': 0o666})

        a_file = None
        try:
            a_file = self.filesystem.openFileForAppending(
                self.test_segments)

            a_file.write(new_content.encode('utf-8'))
            a_file.close()

            a_file = self.filesystem.openFileForReading(
                self.test_segments)
            new_test_content = a_file.read().decode('utf-8')
            self.assertEqual(new_test_content, content + new_content)
        finally:
            if a_file:
                a_file.close()

        if self.os_family == 'posix':
            # It will not overwrite the permissions for existing files.
            result = self.filesystem.getAttributes(self.test_segments)
            self.assertEqual(0o666, result.mode & 0o666)

    def test_openFileForAppending_mode(self):
        """
        You can specify the file permissions used to create a new file
        if doesn't exists.
        """
        _, segments = self.tempPathCleanup()

        sut = self.filesystem.openFileForAppending(segments, mode=0o642)
        sut.write(b'some data')
        sut.close()

        a_file = self.filesystem.openFileForReading(segments)
        new_test_content = a_file.read()
        self.assertEqual(b'some data', new_test_content)

        if self.os_family == 'posix':
            result = self.filesystem.getAttributes(segments)
            # The umask will overwrite the requested attributes.
            self.assertEqual(0o640, result.mode & 0o640)

    def test_openFileForReading_ascii(self):
        """
        Check opening file for reading in ascii mode.
        """
        content = 'ceva nou'
        content_str = b'ceva nou'
        self.test_segments = mk.fs.createFileInTemp(content=content)
        a_file = None
        try:

            a_file = self.filesystem.openFileForReading(
                self.test_segments)

            self.assertEqual(content_str, a_file.read())
        finally:
            if a_file:
                a_file.close()

    def test_setAttributes_owner_and_group(self):
        """
        It will raise OSError when trying to set ownership as normal user.
        """
        _, segments = self.tempFile()

        if self.os_name == 'hpux':
            # On HP-UX you can change the ownership of a file which is owned
            # by you.
            # But you can't reset it later, as it no longer belongs to you.
            self.filesystem.setAttributes(segments, {'uid': 2, 'gid': 4})

        error = self.assertRaises(
            OSError,
            self.filesystem.setAttributes,
            segments, {'uid': 1, 'gid': 1},
            )

        self.assertEqual(errno.EPERM, error.errno)

    def test_setAttributes_time(self):
        """
        It will set the time of the file.
        """
        _, segments = self.tempFile()
        initial = self.filesystem.getAttributes(segments)

        self.filesystem.setAttributes(segments, {'atime': 1, 'mtime': 2})

        after = self.filesystem.getAttributes(segments)

        self.assertNotEqual(initial.modified, after.modified)
        self.assertEqual(2, after.modified)


class LocalFilesystemNTMixin(object):
    """
    Shared tests for Windows path handling in an unlocked filesystem.
    """

    def test_temp_segments(self):
        """
        The temporary segments are the default Windows OS segments
        """
        result = self.filesystem.temp_segments

        # We assume that all tests run from drive C
        # and were we check that the temp segments are for an absolute path.
        self.assertEqual('C', result[0])

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

    def test_getFileData(self):
        """
        Return a dict with file data.
        """
        content = mk.string()
        path, segments = self.tempFile(content=content.encode('utf-8'))
        name = segments[-1]

        result = self.filesystem._getFileData(path)

        self.assertEqual(len(content.encode('utf-8')), result['size'])
        self.assertEqual(name, result['name'])
        self.assertEqual(0, result['tag'])

    @conditionals.onCapability('symbolic_link', True)
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

    def test_setAttributes_mode(self):
        """
        It will ignore the mode of the file as is not implemented in Windows.
        """
        _, segments = self.tempFile()
        initial = self.filesystem.getAttributes(segments)

        self.filesystem.setAttributes(segments, {'mode': 0o777})

        after = self.filesystem.getAttributes(segments)

        self.assertEqual(initial.mode, after.mode)

    def test_isAbsolutePath(self):
        """
        Unit test for detecting which Windows path is absolute.
        """
        # Traditional DOS paths.
        self.assertIsTrue(
            self.filesystem.isAbsolutePath('c'))
        self.assertIsTrue(
            self.filesystem.isAbsolutePath('c:'))
        self.assertIsTrue(
            self.filesystem.isAbsolutePath('c:/'))
        self.assertIsTrue(
            self.filesystem.isAbsolutePath('c:\\'))
        self.assertIsTrue(
            self.filesystem.isAbsolutePath('c:/some/path'))
        self.assertIsTrue(
            self.filesystem.isAbsolutePath('c:\\some\\path'))

        # UNC paths are always absolute.
        self.assertIsTrue(self.filesystem.isAbsolutePath(
            '\\\\system07\\C$\\'))
        self.assertIsTrue(self.filesystem.isAbsolutePath(
            '\\\\.\\UNC\\Server\\Foo.txt'))
        self.assertIsTrue(self.filesystem.isAbsolutePath(
            '\\\\?\\UNC\\Server\\Share\\Foo.txt'))
        self.assertIsTrue(self.filesystem.isAbsolutePath(
            '\\\\.\\Volume{b75e2c83-0000-0000-0000-602f00000000}\\Foo.txt'))
        self.assertIsTrue(self.filesystem.isAbsolutePath(
            '\\\\?\\Volume{b75e2c83-0000-0000-0000-602f00000000}\\Foo.txt'))
        self.assertIsTrue(self.filesystem.isAbsolutePath(
            r'\\.\C:\Test\Foo.txt'))
        self.assertIsTrue(self.filesystem.isAbsolutePath(
            r'\\?\C:\Test\Foo.txt'))

        # Just the share root.
        self.assertIsTrue(self.filesystem.isAbsolutePath(
            '\\\\Server\\Share'))

        # Empty path is not absolute.
        self.assertIsFalse(self.filesystem.isAbsolutePath(''))

        # Using forward slashes will handled it as relative path.
        self.assertIsFalse(self.filesystem.isAbsolutePath(
            '//system07/share-name'))

        # Normal relative path.
        self.assertIsFalse(self.filesystem.isAbsolutePath(
            'some/path'))
        self.assertIsFalse(self.filesystem.isAbsolutePath(
            r'win\path'))
        self.assertIsFalse(self.filesystem.isAbsolutePath(
            r'.\win\path'))
        self.assertIsFalse(self.filesystem.isAbsolutePath(
            r'..\win\path'))

        # Crazy Windows API
        # A relative path from the current directory of the C: drive.
        self.assertIsFalse(self.filesystem.isAbsolutePath(
            r'C:Projects\apilibrary\apilibrary.sln'))

        # They look like absolute, but they are default drive,
        # so we consider them relative.
        # On WIndows API this is defined as
        # An absolute path from the root of the current drive.
        self.assertIsFalse(
            self.filesystem.isAbsolutePath(r'\default-drive\path'))
        self.assertIsFalse(
            self.filesystem.isAbsolutePath('/default/drive/path'))


class TestLocalFilesystemNTnonDevicePath(
        DefaultFilesystemTestCase, LocalFilesystemNTMixin):
    """
    Test for default local filesystem with special behavior for Windows.

    Running with current working directory which is not defined as a
    device path.

    os.getcwd() -> C:\\Some\\path
    """
    _prev_os_getcwd = ''

    @classmethod
    def setUpClass(cls):
        if cls.os_family != 'nt':
            raise cls.skipTest('Only on Windows.')
        cls._prev_os_getcwd = os.getcwd()
        if cls._prev_os_getcwd.startswith('\\\\'):  # noqa:cover
            # We have a device path, so force using a non-device path
            # Most of the time, tests are executed from a process
            # that already has a DOS path and not a device path.
            os.chdir(cls._prev_os_getcwd[4:])
        super(TestLocalFilesystemNTnonDevicePath, cls).setUpClass()

    @classmethod
    def tearDownClass(cls):
        try:
            super(TestLocalFilesystemNTnonDevicePath, cls).tearDownClass()
        finally:
            os.chdir(cls._prev_os_getcwd)


class TestLocalFilesystemNTDevicePath(
        DefaultFilesystemTestCase, LocalFilesystemNTMixin):
    """
    Test for default local filesystem with special behavior for Windows.

    Running with current working directory which is defined as a
    device path.
    os.getcwd() -> \\\\?\\C:\\Some\\path
    """
    _prev_os_getcwd = ''

    @classmethod
    def setUpClass(cls):
        if cls.os_family != 'nt':
            raise cls.skipTest('Only on Windows.')

        cls._prev_os_getcwd = os.getcwd()
        if not cls._prev_os_getcwd.startswith('\\\\'):
            # We have a device path, so force using a non-device path
            os.chdir('\\\\?\\' + cls._prev_os_getcwd)
        super(TestLocalFilesystemNTDevicePath, cls).setUpClass()

    @classmethod
    def tearDownClass(cls):
        try:
            super(TestLocalFilesystemNTDevicePath, cls).tearDownClass()
        finally:
            os.chdir(cls._prev_os_getcwd)


@conditionals.onOSFamily('posix')
class TestLocalFilesystemUnix(DefaultFilesystemTestCase):
    """
    Test for default local filesystem with special behavior for Linux and Unix.
    """

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

    def test_setAttributes_mode(self):
        """
        It will set the mode of the file.
        """
        _, segments = self.tempFile()
        initial = self.filesystem.getAttributes(segments)

        self.filesystem.setAttributes(segments, {'mode': 0o777})

        after = self.filesystem.getAttributes(segments)

        self.assertNotEqual(initial.mode, after.mode)

    def test_isAbsolutePath(self):
        """
        Only paths starting with forward slash are absolute on Unix.
        """
        self.assertIsTrue(self.filesystem.isAbsolutePath('/some/path'))
        self.assertIsFalse(self.filesystem.isAbsolutePath('some/path'))
        self.assertIsFalse(self.filesystem.isAbsolutePath(r'c:\win\path'))
        self.assertIsFalse(self.filesystem.isAbsolutePath(r'\\win-share\path'))


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

    @conditionals.onOSFamily('posix')
    def test_getRealPathFromSegments_unix(self):
        """
        Check getting real path for Unix.
        """
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

        segments = ['UNC', 'server', 'some parent', 'Path']
        path = self.unlocked_filesystem.getRealPathFromSegments(segments)
        self.assertEqual(u'\\\\server\\some parent\\Path', path)

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

    # This test applies only for windows as the root folder is a meta
    # folder containing the Local drives.
    @conditionals.onOSFamily('nt')
    def test_iterateFolderContent_root_nt(self):
        """
        When listing the content for Windows _root_ folder, all local drives
        are returned as an iterator.

        For us on Windows, _root_ folder is something similar to
        "My Computer".
        """
        result = self.unlocked_filesystem.iterateFolderContent([])
        # Make sure we have an iterator and not an iterable.
        members = [next(result)] + list(result)

        # All windows should contain drive C.
        self.assertContains('C', [c.name for c in members])

        parent_content = self.unlocked_filesystem.iterateFolderContent(['..'])
        self.assertEqual(members, list(parent_content))

        parent_content = self.unlocked_filesystem.iterateFolderContent(['.'])
        self.assertEqual(members, list(parent_content))

    # This test applies only for windows as the root folder is a meta
    # folder containing the Local drives.
    @conditionals.onOSFamily('nt')
    def test_getFolderContent_root_nt(self):
        """
        When listing the content for Windows _root_ folder, all local drives
        are listed.

        For us on Windows, _root_ folder is something similar to
        "My Computer".
        """
        content = self.unlocked_filesystem.getFolderContent([])
        self.assertTrue(len(content) > 0)
        self.assertContains(u'C', content)

        parent_content = self.unlocked_filesystem.getFolderContent(['..'])
        self.assertEqual(content, parent_content)

        parent_content = self.unlocked_filesystem.getFolderContent(['.'])
        self.assertEqual(content, parent_content)

    @conditionals.onOSFamily('nt')
    def test_getFolderContent_root_child_nt(self):
        """
        Check getting folder content for a drive on Windows.
        """
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
        absolute_path = self.unlocked_filesystem.getAbsoluteRealPath(path)
        absolute_segments = (
            self.unlocked_filesystem.getSegmentsFromRealPath(absolute_path))
        self.assertEqual(absolute_segments, relative_segments)

    @conditionals.onOSFamily('posix')
    def test_getSegmentsFromRealPath_unix(self):
        """
        Check getting real OS path for Unix.
        """
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

    @conditionals.onOSFamily('nt')
    def test_getSegmentsFromRealPath_nt(self):
        """
        Check getting real OS path for Windows.
        """
        path = u''
        segments = self.unlocked_filesystem.getSegmentsFromRealPath(path)
        self.assertEqual([], segments)

        segments = self.unlocked_filesystem.getSegmentsFromRealPath('c:')
        self.assertEqual(['c'], segments)

        # A drive path.
        path = u'c:\\'
        segments = self.unlocked_filesystem.getSegmentsFromRealPath(path)
        self.assertEqual([u'c'], segments)

        path = u'c:\\Temp'
        segments = self.unlocked_filesystem.getSegmentsFromRealPath(path)
        self.assertEqual([u'c', u'Temp'], segments)

        path = u'c:\\Temp\\'
        segments = self.unlocked_filesystem.getSegmentsFromRealPath(path)
        self.assertEqual([u'c', u'Temp'], segments)

        # Local path with space.
        path = u'c:\\Temp\\Other path'
        segments = self.unlocked_filesystem.getSegmentsFromRealPath(path)
        self.assertEqual([u'c', u'Temp', u'Other path'], segments)

        # UNC.
        path = '\\\\server-name\\Path on\\server'
        segments = self.unlocked_filesystem.getSegmentsFromRealPath(path)
        self.assertEqual(
            ['UNC', 'server-name', 'Path on', 'server'], segments)

        # UNC with relative path segments.
        path = '\\\\server-name\\Path on\\skip\\..\\other'
        segments = self.unlocked_filesystem.getSegmentsFromRealPath(path)
        self.assertEqual(
            ['UNC', 'server-name', 'Path on', 'other'], segments)

        # Long UNC for remote server.
        path = '\\\\?\\UNC\\server-name\\Path on\\server'
        segments = self.unlocked_filesystem.getSegmentsFromRealPath(path)
        self.assertEqual(
            ['UNC', 'server-name', 'Path on', 'server'], segments)

        # Long UNC with doth for remote server.
        path = '\\\\.\\UNC\\server-name\\Path on\\server'
        segments = self.unlocked_filesystem.getSegmentsFromRealPath(path)
        self.assertEqual(
            ['UNC', 'server-name', 'Path on', 'server'], segments)

        # Long UNC for local files.
        path = '\\\\?\\c:\\Temp\\Other path'
        segments = self.unlocked_filesystem.getSegmentsFromRealPath(path)
        self.assertEqual([u'c', u'Temp', u'Other path'], segments)

        # Long UNC with dot for local files.
        path = '\\\\.\\c:\\Temp\\Other path'
        segments = self.unlocked_filesystem.getSegmentsFromRealPath(path)
        self.assertEqual(['c', 'Temp', 'Other path'], segments)

    @conditionals.onOSFamily('nt')
    def test_getRealPathFromSegments_fix_bad_path_nt(self):
        """
        When Unix folder separators are used for Windows path, the
        filesystem will convert them without any errors or warnings.
        """
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

    @conditionals.onOSFamily('nt')
    @conditionals.onCapability('symbolic_link', True)
    def test_exists_share_link(self):
        """
        Will return True when we have a UNC / network link.
        """
        path, segments = mk.fs.makePathInTemp()
        # Make sure path does not exists.
        result = self.unlocked_filesystem.exists(segments)
        self.assertFalse(result)
        # We assume all slaves have the c:\temp folder.
        share_name = 'share name-' + mk.string()
        self.makeWindowsShare(path='c:\\temp', name=share_name)
        self.unlocked_filesystem.makeLink(
            target_segments=['UNC', '127.0.0.1', share_name],
            link_segments=segments,
            )
        self.addCleanup(self.unlocked_filesystem.deleteFolder, segments)

        self.assertTrue(self.unlocked_filesystem.exists(segments))
        self.assertTrue(self.unlocked_filesystem.isLink(segments))

    @conditionals.onCapability('symbolic_link', True)
    def test_exists_broken_link(self):
        """
        Will check the existence of the link file and not the target.
        """
        _, self.test_segments = mk.fs.makePathInTemp()
        self.unlocked_filesystem.makeLink(
            target_segments=['z', 'no-such', 'target'],
            link_segments=self.test_segments,
            )

        self.assertTrue(self.unlocked_filesystem.exists(self.test_segments))
        self.assertTrue(self.unlocked_filesystem.isLink(self.test_segments))


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
        segments = self.locked_filesystem.getSegments(b'/cAca')
        self.assertEqual([u'cAca'], segments)

        segments = self.locked_filesystem.getSegments(b'm\xc8\x9b')
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

    @conditionals.onOSFamily('nt')
    def test_getRealPathFromSegments_fix_bad_path_nt(self):
        """
        When Unix folder separators are used for Windows path, the
        filesystem will convert them without any errors or warnings.
        """
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
            self.locked_filesystem.getSegmentsFromRealPath(
                'UNC\\server\\share\\path')

        with self.assertRaises(CompatError):
            self.locked_filesystem.getSegmentsFromRealPath('..\\..\\outside')

    def test_temp_segments(self):
        """
        The temporary segments are inside the locked path.
        """
        result = self.locked_filesystem.temp_segments
        self.assertEqual(['__chevah_test_temp__'], result)

    @conditionals.onCapability('symbolic_link', True)
    def test_exists_outside_link(self):
        """
        Will return True when link target is outside of home folder as we
        only check that link file itself exists.
        """
        _, self.test_segments = mk.fs.makePathInTemp()
        link_segments = [self.test_segments[-1]]
        mk.fs.makeLink(
            target_segments=['z', 'no', 'such'],
            link_segments=self.test_segments,
            )
        # Make sure link was created.
        self.assertTrue(self.locked_filesystem.isLink(link_segments))

        self.assertTrue(self.locked_filesystem.exists(link_segments))

    @conditionals.onCapability('symbolic_link', True)
    def test_readLink_inside_home(self):
        """
        It return the virtual link of the target.
        """
        path, target_segments = self.tempFile()
        link_segments = ['%s-link' % target_segments[-1]]
        mk.fs.makeLink(
            target_segments=target_segments,
            link_segments=target_segments[:-1] + link_segments,
            )
        self.addCleanup(self.locked_filesystem.deleteFile, link_segments)

        result = self.locked_filesystem.readLink(link_segments)

        self.assertEqual(target_segments[-1:], result)

    @conditionals.onCapability('symbolic_link', True)
    def test_readLink_outside_home(self):
        """
        Raise an error when target is outside of locked folder to not
        disclose the actual path.
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

    @conditionals.onCapability('symbolic_link', True)
    def test_getAttributes_link_file_outside(self):
        """
        Will return the attribute of the file, even when the target is
        outside of the home folder.
        """
        path, segments = self.tempPath()
        name = segments[-1]
        # Targets present on all systems, but outside of the locked filesystem.
        if self.os_family == 'nt':
            target = ['c', 'windows', 'system32', 'xcopy.exe']
        else:
            # This needs to point to a file that we know that exists on all
            # operating systems.
            target = ['bin', 'sh']
        mk.fs.makeLink(
            target_segments=target,
            link_segments=segments,
            )
        self.addCleanup(mk.fs.deleteFile, segments)

        # We use the segments as visible to the locked filesystem.
        attributes = self.locked_filesystem.getAttributes([name])

        # The attributes are for the link, and the target is not revealed.
        self.assertEqual(name, attributes.name)
        self.assertEqual(path, attributes.path)
        self.assertTrue(attributes.is_file)
        self.assertTrue(attributes.is_link)
        self.assertFalse(attributes.is_folder)
        # Make sure we get the attributes of the file, and not of the link.
        self.assertLess(1000, attributes.size)


@conditionals.onOSFamily('nt')
@conditionals.onCapability('symbolic_link', True)
class TestLocalFilesystemLockedUNC(CompatTestCase, FilesystemTestMixin):
    """
    Tests for locked filesystem with UNC path.
    """

    @classmethod
    def setUpClass(cls):
        if cls.__unittest_skip__:
            raise cls.skipTest()

        cls.locked_avatar = DefaultAvatar()
        cls._share_name = 'TestLocalFilesystemLockedUNC ' + mk.string()
        cls.addWindowsShare('c:\\temp', cls._share_name)
        unc = '\\\\127.0.0.1\%s' % (cls._share_name)
        cls.locked_avatar.root_folder_path = unc
        cls.locked_avatar.home_folder_path = unc
        cls.locked_avatar.lock_in_home_folder = True
        cls.locked_filesystem = LocalFilesystem(avatar=cls.locked_avatar)
        cls.filesystem = cls.locked_filesystem

    @classmethod
    def tearDownClass(cls):
        cls.removeWindowsShare(cls._share_name)
        super(TestLocalFilesystemLockedUNC, cls).tearDownClass()

    def test_openFileForWriting(self):
        """
        Can write to files over UNC.
        """
        name = mk.string()
        content = mk.getUniqueString()
        outside_segments = ['c', 'temp', name]
        a_file = None
        try:
            a_file = self.filesystem.openFileForWriting([name])
            self.addCleanup(mk.fs.deleteFile, outside_segments)
            a_file.write(content.encode('utf-8'))
        finally:
            if a_file:
                a_file.close()

        result = mk.fs.getFileContent(outside_segments)
        self.assertEqual(content, result)


class TestLocalFilesystemVirtualFolder(CompatTestCase):
    """
    Test with the default filesystem using virtual folders.
    """
    def getFilesystem(self, virtual_folders=()):
        avatar = FilesystemApplicationAvatar(
            name=mk.string(),
            home_folder_path=mk.fs.temp_path,
            virtual_folders=virtual_folders,
            )
        return LocalFilesystem(avatar=avatar)

    def test_init_virtual_overlap_folder(self):
        """
        You can't initiate with virtual folder if the virtual path overlaps
        with an existing folder.
        """
        path, segments = self.tempFolder()

        # It fails when the exact path exists.
        with self.assertRaises(CompatError) as context:
            self.getFilesystem(virtual_folders=[
                (['virtual-\N{cloud}', 'base\N{sun}'], mk.fs.temp_path),
                (segments[-1:], mk.fs.temp_path),
                ])
        self.assertEqual(1005, context.exception.event_id)
        self.assertEqual(
            'Virtual path "/%s" overlaps an existing file or '
            'folder at "%s".' % (segments[-1], path),
            context.exception.message)

        # But also if a parent of the virtual path exists.
        with self.assertRaises(CompatError) as context:
            self.getFilesystem(virtual_folders=[
                (['virtual-\N{cloud}', 'base\N{sun}'], mk.fs.temp_path),
                (segments[-1:] + ['deep', 'virtual'], mk.fs.temp_path),
                ])
        self.assertEqual(1005, context.exception.event_id)

    def test_init_virtual_overlap_folder_case_sensitive(self):
        """
        Virtual path on Windows/OSX are case insensitive, while on other
        systems are case sensitive.
        """
        path, segments = self.tempFolder(suffix='low')
        virtual_shadow = segments[-1][:-3] + segments[-1][-3:].upper()

        if self.os_name in ['windows', 'osx']:
            with self.assertRaises(CompatError) as context:
                self.getFilesystem(virtual_folders=[
                    (['virtual-\N{cloud}', 'base\N{sun}'], mk.fs.temp_path),
                    ([virtual_shadow], mk.fs.temp_path),
                    ])
            self.assertEqual(1005, context.exception.event_id)

        else:
            self.getFilesystem(virtual_folders=[
                (['virtual-\N{cloud}', 'base\N{sun}'], mk.fs.temp_path),
                ([virtual_shadow], mk.fs.temp_path),
                ])
            self.getFilesystem(virtual_folders=[
                (['virtual-\N{cloud}', 'base\N{sun}'], mk.fs.temp_path),
                ([virtual_shadow, 'deep'], mk.fs.temp_path),
                ])

    def test_getRealPathFromSegments_no_match(self):
        """
        Returns the non-virtual real path when the is no match for the
        segments.
        """
        sut = self.getFilesystem(virtual_folders=[
            (['base'], '/other/path'),
            (['some', 'base'], '/some/path'),
            ])

        result = sut.getRealPathFromSegments(['other', 'path'])

        self.assertEqual(
            os.path.join(mk.fs.temp_path, 'other', 'path'), result)

    def test_getRealPathFromSegments_sub_match(self):
        """
        Returns the non-virtual real path when the is no full match for the
        segments.
        """
        sut = self.getFilesystem(virtual_folders=[
            (['base'], '/other/path'),
            (['some', 'base', 'deep'], '/some/path'),
            ])

        result = sut.getRealPathFromSegments(['some', 'base', 'path'])
        self.assertEqual(
            os.path.join(mk.fs.temp_path, 'some', 'base', 'path'), result)

        with self.assertRaises(CompatError) as context:
            sut.getRealPathFromSegments(
                ['some', 'base', 'path'], include_virtual=False)
        self.assertEqual(1007, context.exception.event_id)

    def test_getRealPathFromSegments_inner_match(self):
        """
        Returns the non-virtual real path when the is no full match for the
        segments.
        """
        sut = self.getFilesystem(virtual_folders=[
            (['base'], '/other/path'),
            (['some', 'base'], '/some/path'),
            ])

        result = sut.getRealPathFromSegments(['some'])
        self.assertEqual(
            os.path.join(mk.fs.temp_path, 'some'), result)

        with self.assertRaises(CompatError) as context:
            sut.getRealPathFromSegments(['some'], include_virtual=False)
        self.assertEqual(1007, context.exception.event_id)

    @conditionals.onOSFamily('posix')
    def test_getRealPathFromSegments_match_posix(self):
        """
        Returns the non-virtual real path when the is no full match for the
        segments.

        Tests with Posix paths, which are case sensitives
        """
        sut = self.getFilesystem(virtual_folders=[
            (['some', 'base'], '/some/path'),
            (['base\N{leo}'], '/other\N{sun}/path'),
            ])

        result = sut.getRealPathFromSegments(['base\N{leo}'])
        self.assertEqual('/other\N{sun}/path', result)

        # If case is different
        result = sut.getRealPathFromSegments(['Base\N{leo}'])
        if self.os_name == 'osx':
            # OSX is case insensitive:
            self.assertEqual('/other\N{sun}/path', result)
        else:
            self.assertEqual(
                os.path.join(mk.fs.temp_path, 'Base\N{leo}'), result)

    @conditionals.onOSFamily('nt')
    def test_getRealPathFromSegments_match_nt(self):
        """
        Returns the non-virtual real path when the is no full match for the
        segments.

        Tests with NT paths.
        """
        sut = self.getFilesystem(virtual_folders=[
            (['some\N{sun}', 'base\N{sun}'], 'c:/some\N{sun}/path'),
            (['base\N{sun}'], 'e:\\otherN{leo}\\path'),
            ])

        result = sut.getRealPathFromSegments(['base\N{sun}'])
        self.assertEqual('e:\\otherN{leo}\\path', result)

        # It will normalize the path.
        result = sut.getRealPathFromSegments(['some\N{sun}', 'base\N{sun}'])
        self.assertEqual('c:\\some\N{sun}\\path', result)

    def test_getRealPathFromSegments_match_no_virtual(self):
        """
        Raise a CompatError when we match full or subpart of virtual
        folder and were asked to not return virtual paths.
        """
        sut = self.getFilesystem(virtual_folders=[
            (['some\N{sun}', 'base\N{sun}'], '/some/path'),
            (['base\N{sun}'], '/other/path'),
            ])

        with self.assertRaises(CompatError) as context:
            sut.getRealPathFromSegments(
                ['base\N{sun}'], include_virtual=False)
        self.assertEqual(1007, context.exception.event_id)

        with self.assertRaises(CompatError) as context:
            sut.getRealPathFromSegments(
                ['some\N{sun}', 'base\N{sun}'], include_virtual=False)
        self.assertEqual(1007, context.exception.event_id)

        with self.assertRaises(CompatError) as context:
            sut.getRealPathFromSegments(['some\N{sun}'], include_virtual=False)
        self.assertEqual(1007, context.exception.event_id)

    @conditionals.onOSFamily('posix')
    def test_getRealPathFromSegments_child_match_posix(self):
        """
        Returns the non-virtual real path when the is no full match for the
        segments.

        Test with Posix paths.
        """
        sut = self.getFilesystem(virtual_folders=[
            (['some', 'base'], '/some/path\N{sun}'),
            (['base\N{sun}'], '/other/path\N{sun}'),
            ])

        result = sut.getRealPathFromSegments(['base\N{sun}', 'child\N{cloud}'])

        self.assertEqual('/other/path\N{sun}/child\N{cloud}', result)

    @conditionals.onOSFamily('nt')
    def test_getRealPathFromSegments_child_match_nt(self):
        """
        Returns the non-virtual real path when the is no full match for the
        segments.
        """
        sut = self.getFilesystem(virtual_folders=[
            (['some', 'base\N{sun}'], 'c:/some/path\N{sun}'),
            (['base\N{sun}'], 'e:\\other\N{sun}\\path'),
            ])

        result = sut.getRealPathFromSegments(['base\N{sun}', 'child\N{cloud}'])
        self.assertEqual('e:\\other\N{sun}\\path\\child\N{cloud}', result)

        result = sut.getRealPathFromSegments(
            ['some', 'base\N{sun}', 'child\N{sun}'])
        self.assertEqual('c:\\some\\path\N{sun}\\child\N{sun}', result)

    def test_getSegmentsFromRealPath_no_match(self):
        """
        Returns the non-virtual real path when the is no full match for the
        segments.
        """
        sut = self.getFilesystem(virtual_folders=[
            (['some', 'base'], '/some/path'),
            (['base'], '/other/path'),
            ])

        result = sut.getSegmentsFromRealPath(mk.fs.temp_path)

        self.assertEqual([], result)

        result = sut.getSegmentsFromRealPath(
            os.path.join(mk.fs.temp_path, 'child path'))
        self.assertEqual(['child path'], result)

        # It will not allow getting out of the root.
        with self.assertRaises(CompatError) as context:
            sut.getSegmentsFromRealPath('/some/path/../other')
        self.assertEqual(1018, context.exception.event_id)

    @conditionals.onOSFamily('posix')
    def test_getSegmentsFromRealPath_match_posix(self):
        """
        Returns the virtual segments when the path matches a virtual one.
        Trailing path separators are ignored and relative paths are resolved.

        Tests with posix paths. Keep in sync with NT paths.
        """
        sut = self.getFilesystem(virtual_folders=[
            (['some\N{sun}', 'base'], '/virtual/path\N{sun}/'),
            (['base\N{sun}'], '/other\N{sun}/path'),
            ])

        result = sut.getSegmentsFromRealPath('/virtual/path\N{sun}')
        self.assertEqual(['some\N{sun}', 'base'], result)

        result = sut.getSegmentsFromRealPath('/virtual/path\N{sun}/')
        self.assertEqual(['some\N{sun}', 'base'], result)

        result = sut.getSegmentsFromRealPath('/virtual/path\N{sun}//')
        self.assertEqual(['some\N{sun}', 'base'], result)

        result = sut.getSegmentsFromRealPath('/other/../virtual/path\N{sun}//')
        self.assertEqual(['some\N{sun}', 'base'], result)

        result = sut.getSegmentsFromRealPath('/other\N{sun}/path')
        self.assertEqual(['base\N{sun}'], result)

        result = sut.getSegmentsFromRealPath('/other\N{sun}/path/')
        self.assertEqual(['base\N{sun}'], result)

    @conditionals.onOSFamily('nt')
    def test_getSegmentsFromRealPath_match_nt(self):
        """
        Returns the virtual segments when the path matches a virtual one.
        Trailing path separators are ignored and relative paths are resolved.

        Tests with NT paths. Keep in sync with posix paths.
        """

        sut = self.getFilesystem(virtual_folders=[
            (['some', 'base'], 'c:\\virtual\\path\\'),
            (['base'], 'e:/other/path'),
            ])

        result = sut.getSegmentsFromRealPath('c:\\virtual\\path')
        self.assertEqual(['some', 'base'], result)

        result = sut.getSegmentsFromRealPath('C:\\Virtual\\Path')
        self.assertEqual(['some', 'base'], result)

        result = sut.getSegmentsFromRealPath('c:\\virtual\\path')
        self.assertEqual(['some', 'base'], result)

        result = sut.getSegmentsFromRealPath('c:\\virtual\\path\\\\')
        self.assertEqual(['some', 'base'], result)

        result = sut.getSegmentsFromRealPath('c:\\other\\..\\virtual\\path\\')
        self.assertEqual(['some', 'base'], result)

        result = sut.getSegmentsFromRealPath('e:\\other\\path')
        self.assertEqual(['base'], result)

        result = sut.getSegmentsFromRealPath('e:\\other\\path\\')
        self.assertEqual(['base'], result)

    @conditionals.onOSFamily('posix')
    def test_getSegmentsFromRealPath_child_match_posix(self):
        """
        Returns the virtual segments when the path matches a virtual one.
        """
        sut = self.getFilesystem(virtual_folders=[
            (['some', 'base'], '/virtual/path'),
            (['base'], '/other/path'),
            ])

        result = sut.getSegmentsFromRealPath('/other/path/child')
        self.assertEqual(['base', 'child'], result)

        result = sut.getSegmentsFromRealPath('/other/path/child/')
        self.assertEqual(['base', 'child'], result)

        result = sut.getSegmentsFromRealPath('/other/path/child/../other-dir')
        self.assertEqual(['base', 'other-dir'], result)

    @conditionals.onOSFamily('nt')
    def test_getSegmentsFromRealPath_child_match_nt(self):
        """
        Returns the virtual segments when the path matches a virtual one.
        """
        sut = self.getFilesystem(virtual_folders=[
            (['some', 'base'], 'c:\\virtual\\path'),
            (['base'], 'e:/other/path'),
            ])

        result = sut.getSegmentsFromRealPath('e:/other/path/child')
        self.assertEqual(['base', 'child'], result)

        result = sut.getSegmentsFromRealPath('e:/other/path/child/')
        self.assertEqual(['base', 'child'], result)

        result = sut.getSegmentsFromRealPath('e:/other\path\child/')
        self.assertEqual(['base', 'child'], result)

        result = sut.getSegmentsFromRealPath(
            'e:/other/path/child/../other-dir')
        self.assertEqual(['base', 'other-dir'], result)

    def test_exists_virtual(self):
        """
        Returns True for a member of a virtual path and for any part of the
        virtual path itself.
        """
        virtual_path, virtual_segments = self.tempFolder(
            'virtual-base\N{cloud}')
        mk.fs.createFolder(virtual_segments + ['inside-virtual\N{sun}'])

        sut = self.getFilesystem(virtual_folders=[
            (['some', 'base\N{sun}'], virtual_path),
            (['virtual', 'non-existent-\N{sun}'], mk.fs.makePathInTemp()[0])
            ])

        self.assertFalse(sut.exists(['no-such-root-child']))
        self.assertFalse(sut.exists(['some', 'base\N{sun}', 'no-such-child']))

        # The exact virtual root even if mapped to path which does not exists,
        # it exists as virtual path.
        self.assertTrue(sut.exists(['virtual', 'non-existent-\N{sun}']))

        # This is part of our real root.
        self.assertTrue(sut.exists(['virtual-base\N{cloud}']))
        # Any virtual part or child exists.
        self.assertTrue(
            sut.exists(['some', 'base\N{sun}', 'inside-virtual\N{sun}']))
        self.assertTrue(sut.exists(['some', 'base\N{sun}']))
        self.assertTrue(sut.exists(['some']))

        # A path which has no direct virtual folder does not exists.
        self.assertFalse(sut.exists(['some', 'lost\N{sun}']))

        # And the real root exits.
        self.assertTrue(sut.exists([]))

    def test_deleteFolder_virtual(self):
        """
        It can delete folders which are ancestors of a virtual path but will
        fail to delete the virtual root itself.
        """
        virtual_path, virtual_segments = self.tempFolder('virtual')
        mk.fs.createFolder(virtual_segments + ['child-folder'])

        sut = self.getFilesystem(virtual_folders=[
            (['some', 'base'], virtual_path)
            ])

        sut.deleteFolder(['some', 'base', 'child-folder'])

        # It will not allow delete the virtual root.
        with self.assertRaises(CompatError) as context:
            sut.deleteFolder(['some', 'base'])
        self.assertEqual(1007, context.exception.event_id)

        with self.assertRaises(CompatError) as context:
            sut.deleteFolder(['some', 'lost\N{sun}'])
        self.assertEqual(1007, context.exception.event_id)

        # It will allow to parts of the virtual root.
        with self.assertRaises(CompatError) as context:
            sut.deleteFolder(['some'])
        self.assertEqual(1007, context.exception.event_id)

    def test_createFolder_virtual(self):
        """
        You can't create a folder over a virtual path.
        """
        sut = self.getFilesystem(virtual_folders=[
            (['virtual-\N{cloud}', 'base\N{sun}'], mk.fs.temp_path)
            ])

        # It can create outside of the virtual folders.
        sut.createFolder(['new\N{cloud}'])
        self.addCleanup(sut.deleteFolder, ['new\N{cloud}'])
        result = sut.getFolderContent([])
        self.assertItemsEqual(['new\N{cloud}', 'virtual-\N{cloud}'], result)

        # It can create folders inside the virtual folders
        sut.createFolder(
            ['virtual-\N{cloud}', 'base\N{sun}', 'inside-virt'])
        # We do the assertion using the testing filesystem and not sut.
        inside_segments = mk.fs.temp_segments + ['inside-virt']
        self.addCleanup(mk.fs.deleteFolder, inside_segments)
        self.assertTrue(mk.fs.isFolder(inside_segments))

        # It can't create folders over the virtual ones.
        with self.assertRaises(CompatError) as context:
            sut.createFolder(['virtual-\N{cloud}'])
        self.assertEqual(1007, context.exception.event_id)

        with self.assertRaises(CompatError) as context:
            sut.createFolder(['virtual-\N{cloud}', 'base\N{sun}'])
        self.assertEqual(1007, context.exception.event_id)

        # It will not allow create something which looks like a virtual path,
        # but which has no direct mapping.
        with self.assertRaises(CompatError) as context:
            sut.createFolder(['virtual-\N{cloud}', 'air-member\N{sun}'])
        self.assertEqual(1007, context.exception.event_id)

    def test_deleteFile_virtual(self):
        """
        It can delete a file which is ancestor of a virtual path but will
        fail to delete the virtual path itself or its parent.
        """
        virtual_path, virtual_segments = self.tempFolder('virtual')
        mk.fs.createFile(virtual_segments + ['child-file\N{sun}'])

        sut = self.getFilesystem(virtual_folders=[
            (['some', 'base'], virtual_path)
            ])

        sut.deleteFile(['some', 'base', 'child-file\N{sun}'])

        # It will not allow delete the virtual root.
        with self.assertRaises(CompatError) as context:
            sut.deleteFile(['some', 'base'])
        self.assertEqual(1007, context.exception.event_id)

        # It will not allow delete something which looks like a virtual path,
        # but which has no direct mapping.
        with self.assertRaises(CompatError) as context:
            sut.deleteFile(['some', 'lost\N{sun}'])
        self.assertEqual(1007, context.exception.event_id)

        # It will allow to parts of the virtual root.
        with self.assertRaises(CompatError) as context:
            sut.deleteFile(['some'])
        self.assertEqual(1007, context.exception.event_id)

    def test_setOwner_virtual(self):
        """
        It can set owner for folders which are ancestors of a virtual path but
        will fail to change the virtual root itself.
        """
        virtual_path, virtual_segments = self.tempFolder('virtual')
        mk.fs.createFolder(virtual_segments + ['child-folder'])

        sut = self.getFilesystem(virtual_folders=[
            (['some', 'base'], virtual_path)
            ])

        # It will try to set the owner.
        with self.assertRaises(CompatError) as context:
            sut.setOwner(['some', 'base', 'child-folder'], 'no-such-owner')
        # Owner not found error while trying to perform the operation.
        self.assertEqual(1016, context.exception.event_id)

        with self.assertRaises(CompatError) as context:
            sut.setOwner(['some', 'base'], 'no-such-owner')
        # Operation denied.
        self.assertEqual(1007, context.exception.event_id)

        with self.assertRaises(CompatError) as context:
            sut.setOwner(['some', 'lost\n{sun}'], 'no-such-owner')
        # Operation denied.
        self.assertEqual(1007, context.exception.event_id)

        with self.assertRaises(CompatError) as context:
            sut.setOwner(['some'], 'no-such-owner')
        # Operation denied.
        self.assertEqual(1007, context.exception.event_id)

    def test_addGroup_virtual(self):
        """
        It can add group for folders which are ancestors of a virtual path but
        will fail to change the virtual root or virtual parent.
        """
        virtual_path, virtual_segments = self.tempFolder('virtual')
        mk.fs.createFolder(virtual_segments + ['child-folder'])

        sut = self.getFilesystem(virtual_folders=[
            (['some', 'base'], virtual_path)
            ])

        # It will try to set the owner.
        with self.assertRaises(CompatError) as context:
            sut.addGroup(['some', 'base', 'child-folder'], 'no-such-group')
        # Group not found error.. while trying to perform the operation.
        self.assertEqual(1017, context.exception.event_id)

        with self.assertRaises(CompatError) as context:
            sut.addGroup(['some', 'base'], 'no-such-group')
        # Operation denied.
        self.assertEqual(1007, context.exception.event_id)

        with self.assertRaises(CompatError) as context:
            sut.addGroup(['some', 'lost\N{sun}'], 'no-such-group')
        # Operation denied.
        self.assertEqual(1007, context.exception.event_id)

        with self.assertRaises(CompatError) as context:
            sut.addGroup(['some'], 'no-such-group')
        # Operation denied.
        self.assertEqual(1007, context.exception.event_id)

    def test_rename_virtual(self):
        """
        It can rename to and from folders which are ancestors of a virtual path
        but will fail to rename to and from virtual root or parent.
        """
        virtual_path, virtual_segments = self.tempFolder('virtual')
        mk.fs.createFolder(virtual_segments + ['child-folder'])

        sut = self.getFilesystem(virtual_folders=[
            (['some', 'base'], virtual_path)
            ])

        sut.rename(['some', 'base', 'child-folder'], ['outside-folder'])
        self.assertFalse(mk.fs.exists(virtual_segments + ['child-folder']))
        self.assertTrue(mk.fs.exists(mk.fs.temp_segments + ['outside-folder']))

        sut.rename(['outside-folder'], ['some', 'base', 'child-folder'])
        self.assertTrue(mk.fs.exists(virtual_segments + ['child-folder']))
        self.assertFalse(
            mk.fs.exists(mk.fs.temp_segments + ['outside-folder']))

        with self.assertRaises(CompatError) as context:
            sut.rename(['some', 'base'], ['outside-root'])
        # Operation denied.
        self.assertEqual(1007, context.exception.event_id)

        with self.assertRaises(CompatError) as context:
            sut.rename(['some', 'lost'], ['outside-root'])
        # Operation denied.
        self.assertEqual(1007, context.exception.event_id)

        with self.assertRaises(CompatError) as context:
            sut.rename(['outside-folder'], ['some', 'base'])
        # Operation denied.
        self.assertEqual(1007, context.exception.event_id)

        with self.assertRaises(CompatError) as context:
            sut.rename(['outside-folder'], ['some', 'lost'])
        # Operation denied.
        self.assertEqual(1007, context.exception.event_id)

        with self.assertRaises(CompatError) as context:
            sut.rename(['some'], ['outside-root'])
        # Operation denied.
        self.assertEqual(1007, context.exception.event_id)

        with self.assertRaises(CompatError) as context:
            sut.rename(['outside-folder'], ['some'])
        # Operation denied.
        self.assertEqual(1007, context.exception.event_id)

    def test_setAttributes_virtual(self):
        """
        It can setAttributes for folders which is ancestor of a virtual path
        but will fail to change the virtual root itself.
        """
        virtual_path, virtual_segments = self.tempFolder('virtual')
        mk.fs.createFolder(virtual_segments + ['child-folder'])

        sut = self.getFilesystem(virtual_folders=[
            (['some', 'base'], virtual_path)
            ])

        sut.setAttributes(
            ['some', 'base', 'child-folder'],
            {'atime': 1111, 'mtime': 1111},
            )

        with self.assertRaises(CompatError) as context:
            sut.setAttributes(
                ['some', 'base'],
                {'atime': 1111, 'mtime': 1111},
                )
        # Operation denied.
        self.assertEqual(1007, context.exception.event_id)

        with self.assertRaises(CompatError) as context:
            sut.setAttributes(
                ['some', 'lost'],
                {'atime': 1111, 'mtime': 1111},
                )
        # Operation denied.
        self.assertEqual(1007, context.exception.event_id)

        with self.assertRaises(CompatError) as context:
            sut.setAttributes(
                ['some'],
                {'atime': 1111, 'mtime': 1111},
                )
        # Operation denied.
        self.assertEqual(1007, context.exception.event_id)

    def test_getAttributes_virtual(self):
        """
        It can getAttributes for a virtual path or part of it, and that
        is just a folder placeholder.
        """
        virtual_path, virtual_segments = self.tempFolder('virtual')
        mk.fs.createFolder(virtual_segments + ['child-folder\N{sun}'])
        mk.fs.createFile(
            virtual_segments + ['child-file\N{cloud}'], content=b'123456789')

        sut = self.getFilesystem(virtual_folders=[
            (['some\N{cloud}', 'other-base\N{sun}'], virtual_path),
            (['some\N{cloud}', 'base\N{sun}'], virtual_path),
            ])

        result = sut.getAttributes(
            ['some\N{cloud}', 'base\N{sun}', 'child-folder\N{sun}'])
        self.assertTrue(result.is_folder)
        self.assertFalse(result.is_file)
        self.assertEqual('child-folder\N{sun}', result.name)

        result = sut.getAttributes(
            ['some\N{cloud}', 'base\N{sun}', 'child-file\N{cloud}'])
        self.assertFalse(result.is_folder)
        self.assertTrue(result.is_file)
        self.assertEqual('child-file\N{cloud}', result.name)
        self.assertEqual(9, result.size)

        result = sut.getAttributes(['some\N{cloud}', 'base\N{sun}'])
        self.assertTrue(result.is_folder)
        self.assertFalse(result.is_file)
        self.assertEqual('base\N{sun}', result.name)

        result = sut.getAttributes(['some\N{cloud}'])
        self.assertTrue(result.is_folder)
        self.assertFalse(result.is_file)
        self.assertFalse(result.is_link)
        self.assertEqual('some\N{cloud}', result.name)
        self.assertEqual(
            os.path.join(mk.fs.temp_path, 'some\N{cloud}'), result.path)
        self.assertEqual(0, result.size)
        self.assertEqual(start_of_year, result.modified)

        result = sut.getAttributes([])
        self.assertTrue(result.is_folder)
        self.assertFalse(result.is_file)
        self.assertFalse(result.is_link)
        self.assertEqual(mk.fs.temp_path, result.path)
        self.assertIsNone(result.name)

        # Since is part of virtual path, this fail as is an invalid path which
        # does not exists.
        with self.assertRaises(CompatError) as context:
            sut.getAttributes(['some\N{cloud}', 'lost\N{sun}'])
        self.assertEqual(1004, context.exception.event_id)

    def test_getAttributes_virtual_case(self):
        """
        On Windows is case insensitive, while on other system is case
        sensitive.
        """
        virtual_path, virtual_segments = self.tempFolder('virtual')
        mk.fs.createFolder(virtual_segments + ['child-folder\N{sun}'])
        mk.fs.createFile(
            virtual_segments + ['child-file\N{cloud}'], content=b'123456789')

        sut = self.getFilesystem(virtual_folders=[
            (['some\N{cloud}', 'base\N{sun}'], virtual_path),
            ])

        if self.os_name in ['windows', 'osx']:
            result = sut.getAttributes(['Some\N{cloud}'])
            self.assertTrue(result.is_folder)
            self.assertFalse(result.is_file)
            self.assertEqual('Some\N{cloud}', result.name)
            self.assertEqual(
                os.path.join(mk.fs.temp_path, 'Some\N{cloud}'), result.path)
            self.assertEqual(0, result.size)

            result = sut.getAttributes(['some\N{cloud}', 'Base\N{sun}'])
            self.assertTrue(result.is_folder)
            self.assertFalse(result.is_file)
            self.assertEqual('Base\N{sun}', result.name)
            self.assertEqual(virtual_path, result.path)
            self.assertEqual(0, result.size)

        else:
            with self.assertRaises(OSError) as context:
                sut.getAttributes(['Some\N{cloud}'])

            with self.assertRaises(CompatError) as context:
                sut.getAttributes(['some\N{cloud}', 'Base\N{sun}'])
            self.assertEqual(1004, context.exception.event_id)

    def test_getStatus_virtual(self):
        """
        It can getStatus for a virtual path or part of it, and that
        is just a folder placeholder.
        """
        virtual_path, virtual_segments = self.tempFolder('virtual')
        mk.fs.createFolder(virtual_segments + ['child-folder\N{sun}'])
        mk.fs.createFile(
            virtual_segments + ['child-file\N{cloud}'], content=b'123456789')

        sut = self.getFilesystem(virtual_folders=[
            (['some\N{cloud}', 'other-base\N{sun}'], virtual_path),
            (['some\N{cloud}', 'base\N{sun}'], virtual_path),
            (['some\N{cloud}', 'more-base\N{sun}'], virtual_path),
            ])

        result = sut.getStatus(
            ['some\N{cloud}', 'base\N{sun}', 'child-folder\N{sun}'])
        self.assertFalse(stat.S_ISREG(result.st_mode))
        self.assertTrue(stat.S_ISDIR(result.st_mode))
        self.assertFalse(stat.S_ISLNK(result.st_mode))
        self.assertNotEqual(0, result.st_ino)

        result = sut.getStatus(
            ['some\N{cloud}', 'base\N{sun}', 'child-file\N{cloud}'])
        self.assertTrue(stat.S_ISREG(result.st_mode))
        self.assertFalse(stat.S_ISDIR(result.st_mode))
        self.assertFalse(stat.S_ISLNK(result.st_mode))
        self.assertNotEqual(0, result.st_ino)
        self.assertEqual(9, result.st_size)

        result = sut.getStatus(['some\N{cloud}', 'base\N{sun}'])
        self.assertFalse(stat.S_ISREG(result.st_mode))
        self.assertTrue(stat.S_ISDIR(result.st_mode))
        self.assertFalse(stat.S_ISLNK(result.st_mode))
        self.assertEqual(0, result.st_ino)

        result = sut.getStatus(['some\N{cloud}'])
        self.assertFalse(stat.S_ISREG(result.st_mode))
        self.assertTrue(stat.S_ISDIR(result.st_mode))
        self.assertFalse(stat.S_ISLNK(result.st_mode))
        self.assertEqual(0, result.st_ino)
        self.assertEqual(start_of_year, result.st_mtime)
        self.assertEqual(1, result.st_atime)

        result = sut.getStatus([])
        self.assertFalse(stat.S_ISREG(result.st_mode))
        self.assertTrue(stat.S_ISDIR(result.st_mode))
        self.assertFalse(stat.S_ISLNK(result.st_mode))
        self.assertNotEqual(0, result.st_ino)

        # Since is part of virtual path, this fail as is an invalid path which
        # does not exists.
        with self.assertRaises(CompatError) as context:
            sut.getStatus(['some\N{cloud}', 'lost\N{sun}'])
        self.assertEqual(1004, context.exception.event_id)

    def test_removeGroup_virtual(self):
        """
        It can removeGroup for folders which are ancestors of a virtual path
        but will fail to change the virtual root or virtual parent.
        """
        virtual_path, virtual_segments = self.tempFolder('virtual')
        mk.fs.createFolder(virtual_segments + ['child-folder'])

        sut = self.getFilesystem(virtual_folders=[
            (['some', 'base'], virtual_path)
            ])

        # It can remove group.
        child_segments = ['some', 'base', 'child-folder']
        if self.os_family == 'nt':
            with self.assertRaises(CompatError) as context:
                sut.removeGroup(child_segments, 'no-such-group')
            # Failed to remove as group does not exist.
            self.assertEqual(1013, context.exception.event_id)
        else:
            # On Non-Windows this does nothing.
            sut.removeGroup(child_segments, 'no-such-group')

        with self.assertRaises(CompatError) as context:
            sut.removeGroup(['some', 'base'], 'no-such-group')
        # Operation denied.
        self.assertEqual(1007, context.exception.event_id)

        with self.assertRaises(CompatError) as context:
            sut.removeGroup(['some', 'lost'], 'no-such-group')
        # Operation denied.
        self.assertEqual(1007, context.exception.event_id)

        with self.assertRaises(CompatError) as context:
            sut.removeGroup(['some'], 'no-such-group')
        # Operation denied.
        self.assertEqual(1007, context.exception.event_id)

    def test_touch_virtual(self):
        """
        It can't touch a virtual root.
        """
        sut = self.getFilesystem(virtual_folders=[
            (['virtual-\N{cloud}', 'base\N{sun}'], mk.fs.temp_path)
            ])

        with self.assertRaises(CompatError) as context:
            sut.touch(['virtual-\N{cloud}'])
        self.assertEqual(1007, context.exception.event_id)

        with self.assertRaises(CompatError) as context:
            sut.touch(['virtual-\N{cloud}', 'base\N{sun}'])
        self.assertEqual(1007, context.exception.event_id)

        with self.assertRaises(CompatError) as context:
            sut.touch(['virtual-\N{cloud}', 'lost\N{sun}'])
        self.assertEqual(1007, context.exception.event_id)

    def test_isLink_virtual(self):
        """
        Virtual paths are not links.
        """
        sut = self.getFilesystem(virtual_folders=[
            (['virtual-\N{cloud}', 'base\N{sun}'], mk.fs.temp_path)
            ])

        self.assertFalse(sut.isLink(['virtual-\N{cloud}']))
        self.assertFalse(sut.isLink(['virtual-\N{cloud}', 'base\N{sun}']))
        self.assertFalse(sut.isLink(
            ['virtual-\N{cloud}', 'base\N{sun}', 'non-existent-file']))

        # Since is part of virtual path, this fail as is an invalid path which
        # does not exists.
        with self.assertRaises(CompatError) as context:
            sut.isLink(['virtual-\N{cloud}', 'lost\N{sun}'])
        self.assertEqual(1004, context.exception.event_id)

    def test_readLink_virtual(self):
        """
        Virtual paths can't be links and readLink will fail on them.
        """
        sut = self.getFilesystem(virtual_folders=[
            (['virtual-\N{cloud}', 'base\N{sun}'], mk.fs.temp_path)
            ])

        with self.assertRaises(CompatError) as context:
            sut.readLink(['virtual-\N{cloud}'])
        self.assertEqual(1007, context.exception.event_id)

        with self.assertRaises(CompatError) as context:
            sut.readLink(['virtual-\N{cloud}', 'lost'])
        self.assertEqual(1007, context.exception.event_id)

        with self.assertRaises(CompatError) as context:
            sut.readLink(['virtual-\N{cloud}', 'base\N{sun}'])
        self.assertEqual(1007, context.exception.event_id)

        # It will try read the link inside the virtual path.
        with self.assertRaises(OSError) as context:
            sut.readLink(
                ['virtual-\N{cloud}', 'base\N{sun}', 'non-existent-file'])

    @conditionals.onCapability('symbolic_link', True)
    def test_makeLink_virtual(self):
        """
        It can't create links to or from virtual paths.
        """
        sut = self.getFilesystem(virtual_folders=[
            (['virtual-\N{cloud}', 'base\N{sun}'], mk.fs.temp_path)
            ])

        with self.assertRaises(CompatError) as context:
            sut.makeLink(['virtual-\N{cloud}', 'base\N{sun}'], ['anything'])
        self.assertEqual(1007, context.exception.event_id)

        with self.assertRaises(CompatError) as context:
            sut.makeLink(['virtual-\N{cloud}'], ['anything'])
        self.assertEqual(1007, context.exception.event_id)

        with self.assertRaises(CompatError) as context:
            sut.makeLink(['virtual-\N{cloud}', 'lost'], ['anything'])
        self.assertEqual(1007, context.exception.event_id)

        with self.assertRaises(CompatError) as context:
            sut.makeLink(['anything'], ['virtual-\N{cloud}', 'base\N{sun}'])
        self.assertEqual(1007, context.exception.event_id)

        with self.assertRaises(CompatError) as context:
            sut.makeLink(['anything'], ['virtual-\N{cloud}'])
        self.assertEqual(1007, context.exception.event_id)

        with self.assertRaises(CompatError) as context:
            sut.makeLink(['anything'], ['virtual-\N{cloud}', 'lost'])
        self.assertEqual(1007, context.exception.event_id)

    def test_openFile_virtual(self):
        """
        It can't open file to virtual paths or its parents, but can open
        files inside the virtual root.
        """
        _, segments = self.tempFile(content=b'1234')
        sut = self.getFilesystem(virtual_folders=[
            (['virtual-\N{cloud}', 'base\N{sun}'], mk.fs.temp_path)
            ])

        with self.assertRaises(CompatError) as context:
            sut.openFile(
                ['virtual-\N{cloud}', 'base\N{sun}'], os.O_RDONLY, 0o777)
        self.assertEqual(1007, context.exception.event_id)

        with self.assertRaises(CompatError) as context:
            sut.openFile(
                ['virtual-\N{cloud}', 'lost\N{sun}'], os.O_RDONLY, 0o777)
        self.assertEqual(1007, context.exception.event_id)

        with self.assertRaises(CompatError) as context:
            sut.openFile(
                ['virtual-\N{cloud}'], os.O_RDONLY, 0o777)
        self.assertEqual(1007, context.exception.event_id)

        result = sut.openFile(
            ['virtual-\N{cloud}', 'base\N{sun}', segments[-1]],
            os.O_RDONLY, 0o777)
        actual_data = os.read(result, 100)
        os.close(result)
        self.assertEqual(b'1234', actual_data)

    def test_openFileForReading_virtual(self):
        """
        It can't open file to virtual paths or its parents, but can open
        files inside the virtual root.
        """
        _, segments = self.tempFile(content=b'1234')
        sut = self.getFilesystem(virtual_folders=[
            (['virtual-\N{cloud}', 'base\N{sun}'], mk.fs.temp_path)
            ])

        with self.assertRaises(CompatError) as context:
            sut.openFileForReading(['virtual-\N{cloud}', 'base\N{sun}'])
        self.assertEqual(1007, context.exception.event_id)

        with self.assertRaises(CompatError) as context:
            sut.openFileForReading(['virtual-\N{cloud}', 'lost\N{sun}'])
        self.assertEqual(1007, context.exception.event_id)

        with self.assertRaises(CompatError) as context:
            sut.openFileForReading(['virtual-\N{cloud}'])
        self.assertEqual(1007, context.exception.event_id)

        result = sut.openFileForReading(
            ['virtual-\N{cloud}', 'base\N{sun}', segments[-1]])
        actual_data = result.read()
        result.close()
        self.assertEqual(b'1234', actual_data)

    def test_openFileForWriting_virtual(self):
        """
        It can't open file to virtual paths or its parents, but can open
        files inside the virtual root.
        """
        _, segments = self.tempFile(content=b'1234')
        sut = self.getFilesystem(virtual_folders=[
            (['virtual-\N{cloud}', 'base\N{sun}'], mk.fs.temp_path)
            ])

        with self.assertRaises(CompatError) as context:
            sut.openFileForWriting(['virtual-\N{cloud}', 'base\N{sun}'])
        self.assertEqual(1007, context.exception.event_id)

        with self.assertRaises(CompatError) as context:
            sut.openFileForWriting(['virtual-\N{cloud}', 'lost\N{sun}'])
        self.assertEqual(1007, context.exception.event_id)

        with self.assertRaises(CompatError) as context:
            sut.openFileForWriting(['virtual-\N{cloud}'])
        self.assertEqual(1007, context.exception.event_id)

        result = sut.openFileForWriting(
            ['virtual-\N{cloud}', 'base\N{sun}', segments[-1]])
        result.write(b'56789')
        result.close()
        self.assertEqual(u'56789', mk.fs.getFileContent(segments))

    def test_openFileForAppending_virtual(self):
        """
        It can't open file to virtual paths or its parents, but can open
        files inside the virtual root.
        """
        _, segments = self.tempFile(content=b'1234')
        sut = self.getFilesystem(virtual_folders=[
            (['virtual-\N{cloud}', 'base\N{sun}'], mk.fs.temp_path)
            ])

        with self.assertRaises(CompatError) as context:
            sut.openFileForAppending(['virtual-\N{cloud}', 'base\N{sun}'])
        self.assertEqual(1007, context.exception.event_id)

        with self.assertRaises(CompatError) as context:
            sut.openFileForAppending(['virtual-\N{cloud}', 'lost\N{sun}'])
        self.assertEqual(1007, context.exception.event_id)

        with self.assertRaises(CompatError) as context:
            sut.openFileForAppending(['virtual-\N{cloud}'])
        self.assertEqual(1007, context.exception.event_id)

        result = sut.openFileForAppending(
            ['virtual-\N{cloud}', 'base\N{sun}', segments[-1]])
        result.write(b'56789')
        result.close()
        self.assertEqual(u'123456789', mk.fs.getFileContent(segments))

    def test_getFileSize_virtual(self):
        """
        Ancestors of the virtual path and the virtual root will get the actual
        size, while part of the virtual path will have the size 0.
        """
        virtual_path, virtual_segments = self.tempFolder('virtual')
        mk.fs.createFile(
            virtual_segments + ['child-file\N{sun}'], content=b'blalata')

        sut = self.getFilesystem(virtual_folders=[
            (['some', 'base'], virtual_path),
            (['some', 'more-base'], virtual_path),
            ])

        result = sut.getFileSize(['some', 'base', 'child-file\N{sun}'])
        self.assertEqual(7, result)

        result = sut.getFileSize(['some', 'base'])
        self.assertEqual(0, result)

        result = sut.getFileSize(['some'])
        self.assertEqual(0, result)

        # Since is part of virtual path, this fail as is an invalid path which
        # does not exists.
        with self.assertRaises(CompatError) as context:
            sut.getFileSize(['some', 'middle-virtual'])
        self.assertEqual(1004, context.exception.event_id)

    def test_getFolderContent_virtual(self):
        """
        It can list a virtual folder.
        """
        virtual_path, virtual_segments = self.tempFolder('virtual')
        mk.fs.createFolder(virtual_segments + ['child-folder'])
        mk.fs.createFile(virtual_segments + ['child-file\N{sun}'])

        sut = self.getFilesystem(virtual_folders=[
            (['base\N{sun}', 'deep'], virtual_path)
            ])

        result = sut.getFolderContent(['base\N{sun}', 'deep'])

        self.assertItemsEqual(['child-folder', 'child-file\N{sun}'], result)

    @conditionals.skipOnPY3()
    def test_getFolderContent_virtual_member(self):
        """
        It can list a virtual folder as member of a parent folder.
        """
        virtual_path, virtual_segments = self.tempFolder('other-real\N{sun}')
        self.tempFolder('non-virtual\N{sun}')
        mk.fs.createFolder(virtual_segments + ['child-folder\N{sun}'])
        mk.fs.createFile(virtual_segments + ['child-file'])

        sut = self.getFilesystem(virtual_folders=[
            (['\N{sun}base', 'base1'], virtual_path),
            (['\N{sun}base', 'base2'], mk.fs.temp_path),
            (['more-virtual', 'deep'], mk.fs.temp_path + 'no-such'),
            ])

        expected = [
            '\N{sun}base',
            'non-virtual\N{sun}',
            'other-real\N{sun}',
            'more-virtual',
            ]
        result = sut.getFolderContent([])
        self.assertItemsEqual(expected, result)

        result = sut.iterateFolderContent([])
        expected = [
            sut._getPlaceholderAttributes(['\N{sun}base']),
            sut.getAttributes(['non-virtual\N{sun}']),
            sut.getAttributes(['other-real\N{sun}']),
            sut._getPlaceholderAttributes(['more-virtual']),
            ]
        if self.os_name == 'windows':
            # On Windows, we don't get inode when iterating over real members.
            expected[1].node_id = 0
            expected[2].node_id = 0
        self.assertIteratorItemsEqual(expected, result)

        self.assertEqual(0o40555, expected[0].mode)
        self.assertIsTrue(expected[0].is_folder)
        self.assertIsFalse(expected[0].is_file)

        expected = [
            'non-virtual\N{sun}',
            'other-real\N{sun}',
            ]
        result = sut.getFolderContent(['\N{sun}base', 'base2'])
        self.assertItemsEqual(expected, result)

        result = sut.iterateFolderContent(['\N{sun}base', 'base2'])
        expected = [
            sut.getAttributes(['non-virtual\N{sun}']),
            sut.getAttributes(['other-real\N{sun}']),
            ]
        if self.os_name == 'windows':
            # On Windows, we don't get inode when iterating.
            expected[0].node_id = 0
            expected[1].node_id = 0
        self.assertIteratorItemsEqual(expected, result)

    @conditionals.skipOnPY3()
    def test_getFolderContent_virtual_no_match(self):
        """
        It will ignore the virtual folders if they don't overlay to the
        requested folder..
        """
        _, segments = self.tempFolder('non-virtual\N{sun}')
        mk.fs.createFolder(segments + ['child-folder'])
        mk.fs.createFile(segments + ['child-file\N{sun}'])

        sut = self.getFilesystem(virtual_folders=[
            (['virtual', 'child-virtual'], mk.fs.temp_path),
            (['virtual', 'deep-virtual', 'other'], mk.fs.temp_path),
            ])

        expected = ['child-folder', 'child-file\N{sun}']

        result = sut.getFolderContent(['non-virtual\N{sun}'])
        self.assertItemsEqual(expected, result)

        result = sut.iterateFolderContent(['non-virtual\N{sun}'])
        expected = [
            mk.fs.getAttributes(segments + ['child-folder']),
            mk.fs.getAttributes(segments + ['child-file\N{sun}']),
            ]
        if self.os_name == 'windows':
            # On Windows, we don't get inode when iterating over real members.
            expected[0].node_id = 0
            expected[1].node_id = 0
        self.assertIteratorItemsEqual(expected, result)

    @conditionals.skipOnPY3()
    def test_getFolderContent_virtual_mix(self):
        """
        It can list a virtual folder as member of a parent folder mixed
        with non-virtual members.

        The real members are shadowed by the virtual members.
        """
        sut = self.getFilesystem(virtual_folders=[
            (['non-virtual\N{sun}', 'virtual\N{cloud}'], mk.fs.temp_path),
            (['non-virtual\N{sun}', 'child-file', 'other'], mk.fs.temp_path),
            ])

        # We create the folders after the filesystem was initialized as
        # otherwise it will fail to initialized as it makes checks at init
        # time for overlapping.
        _, segments = self.tempFolder('non-virtual\N{sun}')
        mk.fs.createFolder(segments + ['child-folder'])
        mk.fs.createFile(segments + ['child-file'])

        _, other_segments = self.tempFolder('other-real\N{leo}')

        result = sut.getFolderContent(['non-virtual\N{sun}'])
        self.assertItemsEqual(['child-file', 'virtual\N{cloud}'], result)

        expected = [
            sut._getPlaceholderAttributes([
                'non-virtual\N{sun}', 'child-file']),
            sut._getPlaceholderAttributes([
                'non-virtual\N{sun}', 'virtual\N{cloud}']),
            ]
        result = sut.iterateFolderContent(['non-virtual\N{sun}'])
        self.assertIteratorItemsEqual(expected, result)

        result = sut.getFolderContent([])
        self.assertEqual(['non-virtual\N{sun}', 'other-real\N{leo}'], result)

        result = sut.iterateFolderContent([])
        # Even if non-virtual is real, we get the attributes for the virtual
        # path.

        expected = [
            mk.fs._getPlaceholderAttributes(segments),
            mk.fs.getAttributes(other_segments)
            ]
        if self.os_name == 'windows':
            # On Windows, we don't get inode when iterating over real members.
            expected[1].node_id = 0
        self.assertIteratorItemsEqual(expected, result)

    @conditionals.skipOnPY3()
    def test_iterateFolderContent_virtual_overlap(self):
        """
        When iterating over a folder with virtual members,
        the real members are shadowed by the virtual members.
        """
        sut = self.getFilesystem(virtual_folders=[
            (['non-virtual\N{sun}', 'virtual\N{cloud}'], mk.fs.temp_path),
            (['non-virtual\N{sun}', 'child-file', 'other'], mk.fs.temp_path),
            ])

        # We create the folders after the filesystem was initialized as
        # otherwise it will fail to initialized as it makes checks at init
        # time for overlapping.
        _, segments = self.tempFolder('non-virtual\N{sun}')

        result = sut.iterateFolderContent([])
        # Even if non-virtual is real, we get the attributes for the virtual
        # path.
        self.assertIteratorItemsEqual([
            mk.fs._getPlaceholderAttributes(segments),
            ],
            result)

    @conditionals.skipOnPY3()
    def test_getFolderContent_virtual_deep_member(self):
        """
        It will list a deep virtual folder as a normal folder.
        """
        virtual_path, segments = self.tempFolder('virt-target\N{sun}')
        mk.fs.createFolder(segments + ['inside-virt\N{sun}'])

        sut = self.getFilesystem(virtual_folders=[
            (['\N{sun}base', 'deep\N{cloud}', 'virt\N{sun}'], virtual_path),
            (['\N{sun}base', 'other\N{sun}', 'virt-folder'], virtual_path)
            ])

        expected = ['deep\N{cloud}', 'other\N{sun}']
        result = sut.getFolderContent(['\N{sun}base'])
        self.assertItemsEqual(expected, result)

        expected = [
            sut._getPlaceholderAttributes([
                '\N{sun}base', 'deep\N{cloud}']),
            sut._getPlaceholderAttributes([
                '\N{sun}base', 'other\N{sun}']),
            ]
        result = sut.iterateFolderContent(['\N{sun}base'])
        self.assertIteratorItemsEqual(expected, result)

        expected = ['virt\N{sun}']
        result = sut.getFolderContent(['\N{sun}base', 'deep\N{cloud}'])
        self.assertItemsEqual(expected, result)

        expected = [
            sut._getPlaceholderAttributes([
                '\N{sun}base', 'deep\N{cloud}', 'virt\N{sun}']),
            ]
        result = sut.iterateFolderContent(['\N{sun}base', 'deep\N{cloud}'])
        self.assertIteratorItemsEqual(expected, result)

    @conditionals.skipOnPY3()
    def test_getFolderContent_virtual_case(self):
        """
        On Windows the segments are case insensitive, while on the other
        systems are case sensitives..
        """
        virtual_path, segments = self.tempFolder('virt-target\N{sun}')
        mk.fs.createFolder(segments + ['inside-virt\N{sun}'])

        sut = self.getFilesystem(virtual_folders=[
            (['\N{sun}base', 'deep\N{cloud}', 'virt\N{sun}'], virtual_path),
            (['\N{sun}base', 'other\N{sun}', 'virt-folder'], virtual_path)
            ])

        if self.os_name in ['windows', 'osx']:
            expected = ['deep\N{cloud}', 'other\N{sun}']
            result = sut.getFolderContent(['\N{sun}Base'])
            self.assertItemsEqual(expected, result)

            result = sut.getFolderContent(['\N{sun}base', 'Deep\N{cloud}'])
            self.assertItemsEqual(['virt\N{sun}'], result)

            result = sut.getFolderContent(
                ['\N{sun}base', 'deep\N{cloud}', 'Virt\N{sun}'])
            self.assertItemsEqual(['inside-virt\N{sun}'], result)

        else:
            with self.assertRaises(OSError):
                sut.getFolderContent(['\N{sun}Base'])

            with self.assertRaises(OSError):
                sut.getFolderContent(['\N{sun}base', 'Deep\N{cloud}'])

            with self.assertRaises(OSError):
                sut.getFolderContent(
                    ['\N{sun}base', 'deep\N{cloud}', 'Virt\N{sun}'])


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
