# Copyright (c) 2010 Adi Roiban.
# See LICENSE for details.
"""
Tests for portable filesystem access.
"""
import os
import stat

from mock import patch

from chevah.compat import DefaultAvatar, LocalFilesystem
from chevah.compat.interfaces import ILocalFilesystem
from chevah.compat.testing import CompatTestCase, conditionals, manufacture


class TestDefaultFilesystem(CompatTestCase):
    """
    Test for default local filesystem which does not depend on attached
    avatar.
    """

    def setUp(self):
        super(TestDefaultFilesystem, self).setUp()
        self.filesystem = LocalFilesystem(avatar=DefaultAvatar())

    def makeLink(self, segments):
        """
        Create a symbolic link to `segments` and return the segments for it.
        """
        link_segments = segments[:]
        link_segments[-1] = '%s-link' % segments[-1]
        manufacture.fs.makeLink(
            target_segments=segments,
            link_segments=link_segments,
            )
        self.addCleanup(manufacture.fs.deleteFile, link_segments)
        return link_segments

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

    def test_temp_segments_location_unix(self):
        """
        On unix the temporary folders are located inside the temp folder.
        """
        if os.name != 'posix':
            raise self.skipTest()

        self.assertEqual([u'tmp'], self.filesystem.temp_segments)

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
        filename = manufacture.makeFilename()
        segments.append(filename)

        test_content = manufacture.getUniqueString()
        manufacture.fs.createFile(segments, content=test_content)

        self.assertIsTrue(self.filesystem.isFile(segments))
        manufacture.fs.deleteFile(segments)

    def test_installation_segments(self):
        """
        Installation segments is the base installation path.
        """
        segments = self.filesystem.installation_segments
        self.assertTrue(manufacture.fs.isFolder(segments))
        folder_name = segments[-1]
        self.assertTrue(folder_name.startswith('build-'))

    def test_isFile(self):
        """
        Check isFile.
        """
        self.test_segments = manufacture.fs.createFileInTemp()
        _, non_existent_segments = manufacture.fs.makePathInTemp()

        self.assertTrue(self.filesystem.isFile(self.test_segments))
        # Non existent paths are not files.
        self.assertFalse(self.filesystem.isFile(non_existent_segments))
        # Folders are not files.
        self.assertFalse(self.filesystem.isFile(manufacture.fs.temp_segments))

    def test_makeLink_file(self):
        """
        Can be used for linking a file.
        """
        self.test_segments = manufacture.fs.createFileInTemp()
        link_segments = self.test_segments[:]
        link_segments[-1] = '%s-link' % self.test_segments[-1]
        manufacture.fs.makeLink(
            target_segments=self.test_segments,
            link_segments=link_segments,
            )

        self.assertTrue(manufacture.fs.exists(link_segments))

        # Can be removed as a simple file and target file is not removed.
        manufacture.fs.deleteFile(link_segments)
        self.assertFalse(manufacture.fs.exists(link_segments))
        self.assertTrue(manufacture.fs.exists(self.test_segments))

    def test_makeLink_folder(self):
        """
        Can be used for linking a folder.
        """
        self.test_segments = manufacture.fs.createFolderInTemp()
        link_segments = self.test_segments[:]
        link_segments[-1] = '%s-link' % self.test_segments[-1]
        manufacture.fs.makeLink(
            target_segments=self.test_segments,
            link_segments=link_segments,
            )

        self.assertTrue(manufacture.fs.exists(link_segments))

        # Can be removed as a simple file and target file is not removed.
        manufacture.fs.deleteFile(link_segments)
        self.assertFalse(manufacture.fs.exists(link_segments))
        self.assertTrue(manufacture.fs.exists(self.test_segments))

    def test_isFolder(self):
        """
        Check isFolder.
        """
        self.test_segments = manufacture.fs.createFileInTemp()
        _, non_existent_segments = manufacture.fs.makePathInTemp()

        self.assertTrue(
            self.filesystem.isFolder(manufacture.fs.temp_segments))
        # Non existent folders are not files.
        self.assertFalse(
            self.filesystem.isFolder(non_existent_segments))
        # Files are not folders.
        self.assertFalse(
            self.filesystem.isFolder(self.test_segments))

    def test_isLink(self):
        """
        Check isLink.
        """
        self.test_segments = manufacture.fs.createFileInTemp()
        _, non_existent_segments = manufacture.fs.makePathInTemp()
        file_link_segments = self.makeLink(self.test_segments)
        folder_link_segments = self.test_segments[:]
        folder_link_segments[-1] = '%s-folder-link' % folder_link_segments[-1]
        # manufacture.fs.makeLink(
        #     target_segments=manufacture.fs.temp_segments,
        #     link_segments=folder_link_segments,
        #     )
        #self.addCleanup(manufacture.fs.deleteFolder, folder_link_segments)


        self.assertTrue(self.filesystem.isLink(file_link_segments))
        #self.assertTrue(self.filesystem.isLink(folder_link_segments))
        self.assertFalse(self.filesystem.isLink(manufacture.fs.temp_segments))
        self.assertFalse(self.filesystem.isLink(self.test_segments))
        self.assertFalse(self.filesystem.isLink(non_existent_segments))

    def test_getAttributes_file(self):
        """
        Check attributes for a file.
        """
        self.test_segments = manufacture.fs.createFileInTemp()
        (
            file_mode,
            is_file,
            is_directory,
            is_link,
            ) = self.filesystem.getAttributes(
                self.test_segments,
                attributes=('permissions', 'file', 'directory', 'link'))

        self.assertFalse(is_directory)
        self.assertTrue(is_file)
        self.assertFalse(is_link)

        if self.os_family == 'posix':
            current_umask = manufacture.fs._getCurrentUmask()
            expected_mode = 0100666 ^ current_umask
            self.assertEqual(expected_mode, file_mode)

    def test_getAttributes_folder(self):
        """
        Check attributes for a folder.
        """
        self.test_segments = manufacture.fs.createFolderInTemp()

        (
            folder_mode,
            is_file,
            is_directory,
            is_link,
            ) = self.filesystem.getAttributes(
                self.test_segments,
                attributes=('permissions', 'file', 'directory', 'link'))

        self.assertTrue(is_directory)
        self.assertFalse(is_file)
        self.assertFalse(is_link)

        if self.os_family == 'posix':
            current_umask = manufacture.fs._getCurrentUmask()
            expected_mode = 040777 ^ current_umask
            self.assertEqual(expected_mode, folder_mode)

    @conditionals.onOSFamily('posix')
    def test_getAttributes_link_file(self):
        """
        A link to a file is recognized as both a link and a file.
        """
        self.test_segments = manufacture.fs.createFileInTemp()
        link_segments = self.makeLink(self.test_segments)

        (
            is_file,
            is_directory,
            is_link,
            ) = self.filesystem.getAttributes(
                link_segments,
                attributes=('file', 'directory', 'link'))

        self.assertTrue(is_file)
        self.assertTrue(is_link)
        self.assertFalse(is_directory)

    @conditionals.onOSFamily('posix')
    def test_getAttributes_link_folder(self):
        """
        A link to a file is recognized as both a link and a file.
        """
        _, link_segments = manufacture.fs.makePathInTemp()
        manufacture.fs.makeLink(
            target_segments=manufacture.fs.temp_segments,
            link_segments=link_segments,
            )
        self.addCleanup(manufacture.fs.deleteFile, link_segments)

        (
            is_file,
            is_directory,
            is_link,
            ) = self.filesystem.getAttributes(
                link_segments,
                attributes=('file', 'directory', 'link'))

        self.assertFalse(is_file)
        self.assertTrue(is_link)
        self.assertTrue(is_directory)

    def test_getStatus_normal(self):
        """
        For non links will return the same status.
        """
        self.test_segments = manufacture.fs.createFileInTemp()

        resolved, own = self.filesystem.getStatus(self.test_segments)

        # We can not test to much here, but getStatus is used by other
        # high level method and we should have specific tests there.
        self.assertEqual(resolved, own)
        self.assertTrue(stat.S_ISREG(resolved.st_mode))
        self.assertFalse(stat.S_ISDIR(resolved.st_mode))
        self.assertFalse(stat.S_ISLNK(resolved.st_mode))

    def test_getStatus_link(self):
        """
        For links will return different status only on Unix.
        """
        self.test_segments = manufacture.fs.createFileInTemp()
        link_segments = self.makeLink(self.test_segments)

        resolved, own = self.filesystem.getStatus(link_segments)

        if self.os_family == 'posix':
            # We can not test to much here, but getStatus is used by other
            # high level method and we should have specific tests there.
            self.assertNotEqual(resolved, own)

            self.assertTrue(stat.S_ISREG(resolved.st_mode))
            self.assertFalse(stat.S_ISDIR(resolved.st_mode))
            self.assertFalse(stat.S_ISLNK(resolved.st_mode))

            self.assertFalse(stat.S_ISREG(own.st_mode))
            self.assertFalse(stat.S_ISDIR(own.st_mode))
            self.assertTrue(stat.S_ISLNK(own.st_mode))
        else:
            self.assertEqual(resolved, own)


class TestPosixFilesystem(CompatTestCase):
    '''Tests for path independent, OS independent tests.'''

    @classmethod
    def setUpClass(cls):
        cls.avatar = manufacture.makeFilesystemOSAvatar()
        cls.avatar._root_folder_path = cls.avatar.home_folder_path
        cls.filesystem = LocalFilesystem(avatar=cls.avatar)

    def setUp(self):
        super(TestPosixFilesystem, self).setUp()

    def test_getPath(self):
        '''Commons tests for getPath.'''
        path = self.filesystem.getPath([])
        self.assertEqual(u'/', path)

        path = self.filesystem.getPath([u'c'])
        self.assertEqual(u'/c', path)

        path = self.filesystem.getPath(
            [u'caca', u'Maca raca'])
        self.assertEqual(u'/caca/Maca raca', path)

        path = self.filesystem.getPath(
            [u'caca', u'.', u'Maca raca'])
        self.assertEqual(u'/caca/Maca raca', path)

        path = self.filesystem.getPath(
            [u'caca', u'..', u'Maca raca'])
        self.assertEqual(u'/Maca raca', path)

    def test_home_segments_root_is_home(self):
        """
        Emtpy list is returned for home_segments if root folder is the same
        as home folder.
        """
        locked_avatar = manufacture.makeFilesystemOSAvatar()
        locked_avatar._root_folder_path = locked_avatar.home_folder_path
        filesystem = LocalFilesystem(avatar=locked_avatar)
        self.assertEqual([], filesystem.home_segments)

    def test_home_segments_absolute_root(self):
        """
        Check getting home segments for an absolute root where home folder
        is not the same as root folder.
        """
        absolute_avatar = manufacture.makeFilesystemOSAvatar()
        absolute_avatar._root_folder_path = None
        filesystem = LocalFilesystem(avatar=absolute_avatar)
        home = filesystem._pathSplitRecursive(
            absolute_avatar.home_folder_path)
        self.assertEqual(home, filesystem.home_segments)

    def test_home_segments_relative_root(self):
        """
        Check home_segments when root folder for the avatar is not the same
        as root folder for filesystem.
        """
        locked_avatar = manufacture.makeFilesystemOSAvatar()
        locked_avatar._root_folder_path = locked_avatar.home_folder_path
        locked_avatar._home_folder_path = os.path.join(
            locked_avatar.home_folder_path, u'test')
        filesystem = LocalFilesystem(avatar=locked_avatar)
        self.assertEqual([u'test'], filesystem.home_segments)


class TestLocalFilesystemUnlocked(CompatTestCase):
    """
    Commons tests for both chrooted and non chrooted filesystem.

    # FIXME:1013:
    # This testcase need a lot of cleaning.
    """

    @classmethod
    def setUpClass(cls):
        cls.unlocked_avatar = DefaultAvatar()
        cls.unlocked_filesystem = LocalFilesystem(avatar=cls.unlocked_avatar)

    def setUp(self):
        super(TestLocalFilesystemUnlocked, self).setUp()
        self.test_segments = None

    def tearDown(self):
        if self.test_segments:
            if self.unlocked_filesystem.isFile(self.test_segments):
                self.unlocked_filesystem.deleteFile(self.test_segments)
            elif self.unlocked_filesystem.isFolder(self.test_segments):
                self.unlocked_filesystem.deleteFolder(self.test_segments)
        super(TestLocalFilesystemUnlocked, self).tearDown()

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

        bubu_segments = home_segments[:]
        bubu_segments.append(u'Bubu')
        segments = self.unlocked_filesystem.getSegments(u'./Bubu')
        self.assertEqual(bubu_segments, segments)

        # Going deep in the root will block at root folder.
        segments = self.unlocked_filesystem.getSegments(
            u'../../../../../../B')
        self.assertEqual([u'B'], segments)

        segments = self.unlocked_filesystem.getSegments(u'/Aa/././bB')
        self.assertEqual([u'Aa', u'bB'], segments)

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

    def test_getRealPathFromSegments_nt(self):
        """
        Check getting real path for Windows.
        """
        if os.name != 'nt':
            raise self.skipTest()

        path = self.unlocked_filesystem.getRealPathFromSegments([])
        self.assertEqual(u'c:\\', path)

        path = self.unlocked_filesystem.getRealPathFromSegments([u'caca'])
        self.assertEqual(u'caca:\\', path)

        path = self.unlocked_filesystem.getRealPathFromSegments(
            [u'caca', u'maca raca'])
        self.assertEqual(u'caca:\\maca raca', path)

        path = self.unlocked_filesystem.getRealPathFromSegments(None)
        self.assertEqual(u'c:\\', path)

        segments = [u'ceva', u'..', u'altceva']
        path = self.unlocked_filesystem.getRealPathFromSegments(segments)
        self.assertEqual(u'altceva:\\', path)

        segments = [u'ceva', u'.', u'altceva']
        path = self.unlocked_filesystem.getRealPathFromSegments(segments)
        self.assertEqual(u'ceva:\\altceva', path)

        segments = [u'..', u'..', u'altceva']
        path = self.unlocked_filesystem.getRealPathFromSegments(segments)
        self.assertEqual(u'altceva:\\', path)

        segments = [u'..', u'..', u'altceva', u'dad']
        path = self.unlocked_filesystem.getRealPathFromSegments(segments)
        self.assertEqual(u'altceva:\\dad', path)

    def test_exists_false(self):
        """
        exists will return `False` if file or folder does not exists.
        """
        segments = self.unlocked_filesystem.temp_segments[:]
        segments.append(manufacture.makeFilename())

        self.assertFalse(self.unlocked_filesystem.exists(segments))

    def test_exists_file_true(self):
        """
        exists will return `True` if file exists.
        """
        segments = self.unlocked_filesystem.temp_segments[:]
        segments.append(manufacture.makeFilename())

        try:
            with (self.unlocked_filesystem.openFileForWriting(
                    segments)) as new_file:
                new_file.write(manufacture.getUniqueString().encode('utf8'))

            self.assertTrue(self.unlocked_filesystem.exists(segments))
        finally:
            self.unlocked_filesystem.deleteFile(segments, ignore_errors=True)

    def test_exists_folder_true(self):
        """
        exists will return `True` if folder exists.
        """
        segments = self.unlocked_filesystem.temp_segments[:]
        segments.append(manufacture.makeFilename())

        try:
            self.unlocked_filesystem.createFolder(segments)

            self.assertTrue(self.unlocked_filesystem.exists(segments))
        finally:
            self.unlocked_filesystem.deleteFolder(segments)

    def test_makeFolder(self):
        """
        Check makeFolder.
        """
        folder_name = manufacture.makeFilename(length=10)
        tmp_segments = self.unlocked_filesystem.temp_segments[:]
        tmp_segments.append(folder_name)
        try:
            self.unlocked_filesystem.createFolder(tmp_segments)
            self.assertTrue(self.unlocked_filesystem.isFolder(tmp_segments))
        finally:
            self.unlocked_filesystem.deleteFolder(tmp_segments)

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
        self.assertTrue(isinstance(content[0], unicode))

    def test_getFolderContent(self):
        """
        Check getting folder content.
        """
        temp_segments = self.unlocked_filesystem.temp_segments
        folder_name = manufacture.makeFilename()
        test_folder = temp_segments[:]
        test_folder.append(folder_name)
        self.unlocked_filesystem.createFolder(test_folder)
        try:
            content = self.unlocked_filesystem.getFolderContent(temp_segments)
            self.assertTrue(len(content) > 0)
            self.assertTrue(isinstance(content[0], unicode))
            self.assertTrue(folder_name in content)
        finally:
            self.unlocked_filesystem.deleteFolder(test_folder)

    def test_getSegmentsFromRealPath_none(self):
        """
        The emtpy segments is return if path is None.
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

    def test_getFileSize(self):
        """
        Check retrieving the size for a file.
        """
        test_size = 1345
        segments = manufacture.fs.createFileInTemp(length=test_size)
        try:
            impersonate_user = self.unlocked_filesystem._impersonateUser
            with patch.object(
                    self.unlocked_filesystem, '_impersonateUser',
                    return_value=impersonate_user()) as mock_method:
                size = self.unlocked_filesystem.getFileSize(segments)
            self.assertEqual(test_size, size)
            self.assertTrue(mock_method.called)
        finally:
            manufacture.fs.deleteFile(segments)

    def test_getFileSize_empty_file(self):
        """
        Check getting file size for an empty file.
        """
        test_size = 0
        segments = manufacture.fs.createFileInTemp(length=0)
        try:
            size = self.unlocked_filesystem.getFileSize(segments)
            self.assertEqual(test_size, size)
        finally:
            manufacture.fs.deleteFile(segments)

    def test_getFileSize_impersonate(self):
        """
        Check getting file size for an avatar that requires impersonation.
        """
        segments = manufacture.fs.createFileInTemp()
        try:
            impersonate_user = self.unlocked_filesystem._impersonateUser
            with patch.object(
                    self.unlocked_filesystem, '_impersonateUser',
                    return_value=impersonate_user()) as mock_method:
                self.unlocked_filesystem.getFileSize(segments)
            self.assertTrue(mock_method.called)
        finally:
            manufacture.fs.deleteFile(segments)

    def test_openFileForReading_impersonate(self):
        """
        Check opening a file for reading for an avatar which requires
        impersonation.
        """
        segments = manufacture.fs.createFileInTemp()
        try:
            impersonate_user = self.unlocked_filesystem._impersonateUser
            with patch.object(
                    self.unlocked_filesystem, '_impersonateUser',
                    return_value=impersonate_user()) as mock_method:

                a_file = self.unlocked_filesystem.openFileForReading(segments)

                a_file.close()
            self.assertTrue(mock_method.called)
        finally:
            manufacture.fs.deleteFile(segments)

    def test_openFileForReading_ascii(self):
        """
        Check opening file for reading in ascii mode.
        """
        content = u'ceva nou'
        content_str = 'ceva nou'
        segments = manufacture.fs.createFileInTemp(content=content)
        a_file = None
        try:
            a_file = self.unlocked_filesystem.openFileForReading(segments)
            self.assertEqual(content_str, a_file.read())
        finally:
            if a_file:
                a_file.close()
            manufacture.fs.deleteFile(segments)

    def test_openFileForReading_unicode(self):
        """
        Check reading in unicode.
        """
        content = manufacture.getUniqueString()
        segments = manufacture.fs.createFileInTemp(content=content)
        a_file = None
        try:

            a_file = self.unlocked_filesystem.openFileForReading(
                segments, utf8=True)

            self.assertEqual(content, a_file.read())
        finally:
            if a_file:
                a_file.close()
            manufacture.fs.deleteFile(segments)

    def test_openFileForReading_empty(self):
        """
        An empty file can be opened for reading.
        """
        segments = manufacture.fs.createFileInTemp(length=0)
        a_file = None
        try:

            a_file = self.unlocked_filesystem.openFileForReading(segments)

            self.assertEqual('', a_file.read())
        finally:
            if a_file:
                a_file.close()
            manufacture.fs.deleteFile(segments)

    def test_openFileForReading_no_write(self):
        """
        A file opened only for reading will not be able to write into.
        """
        segments = manufacture.fs.createFileInTemp(length=0)
        try:
            a_file = self.unlocked_filesystem.openFileForReading(segments)

            with self.assertRaises(IOError):
                a_file.write('something')
            a_file.close()
        finally:
            manufacture.fs.deleteFile(segments)

    def test_openFileForWriting_impersonate(self):
        """
        Check openFileForWriting while using impersonation.
        """
        segments = manufacture.fs.createFileInTemp()
        try:
            impersonate_user = self.unlocked_filesystem._impersonateUser
            with patch.object(
                    self.unlocked_filesystem, '_impersonateUser',
                    return_value=impersonate_user()) as mock_method:

                a_file = self.unlocked_filesystem.openFileForWriting(segments)

                a_file.close()
            self.assertTrue(mock_method.called)
        finally:
            manufacture.fs.deleteFile(segments)

    def test_openFileForWriting_ascii(self):
        """
        Check opening a file for reading in plain/ascii/str mode.
        """
        content = 'some ascii text'
        segments = manufacture.fs.createFileInTemp(length=0)
        try:
            a_file = self.unlocked_filesystem.openFileForWriting(segments)
            a_file.write(content)
            a_file.close()
            a_file = self.unlocked_filesystem.openFileForReading(segments)
            test_content = a_file.read()
            self.assertEqual(test_content, content)
            a_file.close()
        finally:
            manufacture.fs.deleteFile(segments)

    def test_openFileForWriting_unicode(self):
        """
        Check opening a file for reading in unicode mode.
        """
        content = manufacture.getUniqueString()
        segments = manufacture.fs.createFileInTemp(length=0)
        try:
            a_file = self.unlocked_filesystem.openFileForWriting(
                segments, utf8=True)
            a_file.write(content)
            a_file.close()
            a_file = self.unlocked_filesystem.openFileForReading(
                segments, utf8=True)
            test_content = a_file.read()
            self.assertEqual(test_content, content)
            a_file.close()
        finally:
            manufacture.fs.deleteFile(segments)

    def test_openFileForWriting_no_read(self):
        """
        When a file is opened for writing, we can not read from it.
        """
        segments = manufacture.fs.createFileInTemp(length=0)
        try:
            a_file = self.unlocked_filesystem.openFileForWriting(segments)

            # We should not be able to read.
            with self.assertRaises(IOError):
                a_file.read()
            a_file.close()
        finally:
            manufacture.fs.deleteFile(segments)

    def test_openFileForWriting_truncate(self):
        """
        When a file is opened for writing, the previous file is truncated
        to 0 length and we write as a fresh file.
        """
        content = manufacture.getUniqueString(100)
        new_content = manufacture.getUniqueString(50)
        # Create initial content.
        self.test_segments = manufacture.fs.createFileInTemp(content=content)

        # Write new content into file.
        test_file = self.unlocked_filesystem.openFileForWriting(
            self.test_segments)
        test_file.write(new_content.encode('utf-8'))
        test_file.close()

        file_content = manufacture.fs.getFileContent(self.test_segments)
        self.assertEqual(new_content, file_content)

    def test_openFileForAppending_impersonate(self):
        """
        System test for openFileForAppending while using impersonation.
        """
        segments = manufacture.fs.createFileInTemp()
        try:
            impersonate_user = self.unlocked_filesystem._impersonateUser
            with patch.object(
                    self.unlocked_filesystem, '_impersonateUser',
                    return_value=impersonate_user()) as mock_method:

                a_file = self.unlocked_filesystem.openFileForAppending(
                    segments)
                a_file.close()

            self.assertTrue(mock_method.called)
        finally:
            manufacture.fs.deleteFile(segments)

    def test_openFileForAppending(self):
        """
        System test for openFileForAppending.
        """
        content = manufacture.getUniqueString()
        new_content = manufacture.getUniqueString()
        segments = manufacture.fs.createFileInTemp(content=content)
        a_file = None
        try:
            a_file = self.unlocked_filesystem.openFileForAppending(
                segments, utf8=True)

            a_file.write(new_content)
            a_file.close()

            a_file = self.unlocked_filesystem.openFileForReading(
                segments, utf8=True)
            new_test_content = a_file.read()
            self.assertEqual(new_test_content, content + new_content)
        finally:
            if a_file:
                a_file.close()
            manufacture.fs.deleteFile(segments)

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


class TestLocalFilesystemLocked(CompatTestCase):
    """
    Tests for locked filesystem.
    """

    @classmethod
    def setUpClass(cls):
        cls.locked_avatar = DefaultAvatar()
        cls.locked_avatar.root_folder_path = manufacture.fs.temp_path
        cls.locked_avatar.home_folder_path = manufacture.fs.temp_path
        cls.locked_avatar.lock_in_home_folder = True
        cls.locked_filesystem = LocalFilesystem(avatar=cls.locked_avatar)

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
        '''
        Test conversion of segments to a real path.
        '''

        def _p(*path):
            return unicode(
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

        name = manufacture.string()
        result = self.locked_filesystem.getSegmentsFromRealPath(
            root_path + separator + name)
        self.assertEqual([name], result)

        name = manufacture.string()
        child = manufacture.string()
        result = self.locked_filesystem.getSegmentsFromRealPath(
            root_path + separator + name + separator + child + separator)
        self.assertEqual([name, child], result)

    def test_exists_false(self):
        """
        exists will return `False` if file or folder does not exists.
        """
        segments = self.locked_filesystem.home_segments[:]
        segments.append(manufacture.makeFilename())

        self.assertFalse(self.locked_filesystem.exists(segments))

    def test_exists_file_true(self):
        """
        exists will return `True` if file exists.
        """
        segments = self.locked_filesystem.home_segments[:]
        segments.append(manufacture.makeFilename())

        try:
            with (self.locked_filesystem.openFileForWriting(
                    segments)) as new_file:
                new_file.write(manufacture.getUniqueString().encode('utf8'))

            self.assertTrue(self.locked_filesystem.exists(segments))
        finally:
            self.locked_filesystem.deleteFile(segments, ignore_errors=True)

    def test_exists_folder_true(self):
        """
        exists will return `True` if folder exists.
        """
        segments = self.locked_filesystem.home_segments[:]
        segments.append(manufacture.makeFilename())

        try:
            self.locked_filesystem.createFolder(segments)

            self.assertTrue(self.locked_filesystem.exists(segments))
        finally:
            self.locked_filesystem.deleteFolder(segments)

    def test_touch(self):
        """
        System test for touch.
        """
        segments = [manufacture.makeFilename(length=10)]
        self.assertFalse(self.locked_filesystem.exists(segments))
        try:
            self.locked_filesystem._touch(segments)
            self.assertTrue(self.locked_filesystem.exists(segments))
        finally:
            self.locked_filesystem.deleteFile(segments)

    def test_makeFolder(self):
        """
        System test for folder creation.
        """
        name = manufacture.makeFilename()
        try:
            # Just make sure we don't already have this folder
            self.locked_filesystem.deleteFolder([name], recursive=True)
        except OSError:
            # We don't care if there is no such folder.
            pass
        try:
            self.locked_filesystem.createFolder([name])
            self.locked_filesystem.isFolder([name])
        finally:
            self.locked_filesystem.deleteFolder([name], recursive=True)

    def test_rename_file(self):
        """
        System test for file renaming.
        """
        initial_segments = [manufacture.makeFilename(length=10)]
        final_segments = [manufacture.makeFilename(length=10)]
        self.assertFalse(self.locked_filesystem.exists(initial_segments))
        self.assertFalse(self.locked_filesystem.exists(final_segments))
        try:
            self.locked_filesystem._touch(initial_segments)
            self.locked_filesystem.rename(initial_segments, final_segments)
            self.assertFalse(self.locked_filesystem.exists(initial_segments))
            self.assertTrue(self.locked_filesystem.exists(final_segments))
        finally:
            self.locked_filesystem.deleteFile(final_segments)

    def test_rename_folder(self):
        """
        System test for folder renaming.
        """
        initial_segments = [manufacture.makeFilename(length=10)]
        final_segments = [manufacture.makeFilename(length=10)]
        self.assertFalse(self.locked_filesystem.exists(initial_segments))
        self.assertFalse(self.locked_filesystem.exists(final_segments))
        try:
            self.locked_filesystem.createFolder(initial_segments)
            self.locked_filesystem.rename(initial_segments, final_segments)
            self.assertFalse(self.locked_filesystem.exists(initial_segments))
            self.assertTrue(self.locked_filesystem.exists(final_segments))
        finally:
            self.locked_filesystem.deleteFolder(final_segments)

    def test_getFolderContent(self):
        """
        System test for test_getFolderContent.
        """
        initial_segments = [manufacture.makeFilename(length=10)]
        try:
            self.locked_filesystem.createFolder(initial_segments)
            content = self.locked_filesystem.getFolderContent([])
            self.assertTrue(len(content) > 0)
            self.assertTrue(isinstance(content[0], unicode))
        finally:
            self.locked_filesystem.deleteFolder(initial_segments)
