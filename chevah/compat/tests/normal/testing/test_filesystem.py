# Copyright (c) 2012 Adi Roiban.
# See LICENSE for details.
"""
Tests for testing filesystem
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from six import text_type
from chevah.compat.testing import ChevahTestCase, mk
from chevah.compat.testing.filesystem import LocalTestFilesystem


class TestLocalTestFilesystem(ChevahTestCase):
    """
    Test for LocalTestFilesystem.
    """

    def test_uniqe_temporary_folder(self):
        """
        Each instance has a unique temporary folder.
        """
        first = mk.makeLocalTestFilesystem()
        second = mk.makeLocalTestFilesystem()

        self.assertNotEqual(first.temp_segments, second.temp_segments)

    def test_temporary_folders(self):
        """
        A list of all instantiated temp folders is kept as class member
        to help with final cleanup.
        """
        temp = mk.makeLocalTestFilesystem()

        temporary_segments = LocalTestFilesystem.getAllTemporaryFolders()

        # We check that the list contains the new temporary folder,
        # but it also contains other elements.
        # This test depends on the fact that mk.fs was already instantiated.
        self.assertContains(temp.temp_segments, temporary_segments)
        self.assertGreater(len(temporary_segments), 1)

    def test_uncleaned_temporary_folder(self):
        """
        Will raise an error if temporary folders were note cleaned
        and will try to clean the folders.
        """
        temp = mk.makeLocalTestFilesystem()
        temp.setUpTemporaryFolder()

        with self.assertRaises(AssertionError) as context:
            temp.checkCleanTemporaryFolders()

        try:
            # Will contain both the new temporary folder, but also
            # the general mk.fs folder.
            message = context.exception.args[0]
            self.assertContains(text_type(temp.temp_segments), message)
            self.assertContains(text_type(mk.fs.temp_segments), message)
            self.assertFalse(temp.exists(temp.temp_segments))
            self.assertFalse(temp.exists(mk.fs.temp_segments))
        finally:
            # Undo the side-effect of this tests.
            mk.fs.setUpTemporaryFolder()
