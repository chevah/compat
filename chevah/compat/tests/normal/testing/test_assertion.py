# Copyright (c) 2015 Adi Roiban.
# See LICENSE for details.
"""
Tests for the assertion helpers.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import os

from chevah.compat.exceptions import CompatError
from chevah.compat.testing import ChevahTestCase, mk


class TestAssertionMixin(ChevahTestCase):
    """
    Test for assertions.

    ChevahTestCase is inheriting the assertion mixin and we can test it.
    """

    def check_assertWorkingFolderIsClean(self, content):
        """
        Common tests for assertWorkingFolderIsClean.
        """

        with self.assertRaises(AssertionError) as context:
            self.assertWorkingFolderIsClean()

        message = context.exception.args[0].decode('utf-8')
        for member in content:
            self.assertContains(member, message)

        # Calling it again will not raise any error since the folder is clean.
        self.assertWorkingFolderIsClean()

    def test_assertTempIsClean_clean_temp(self):
        """
        No error is raised if temp folder is clean.
        """
        self.assertTempIsClean()

    def test_assertTempIsClean_dirty(self):
        """
        If temp is not clean an error is raised and then temp folders
        is cleaned.
        """
        temp_segments = mk.fs.createFileInTemp()

        with self.assertRaises(AssertionError) as context:
            self.assertTempIsClean()

        message = context.exception.args[0].decode('utf-8')
        self.assertStartsWith(u'Temporary folder is not clean.', message)
        self.assertContains(temp_segments[-1], message)

        self.assertFalse(mk.fs.exists(temp_segments))

    def test_assertWorkingFolderIsClean_with_folder(self):
        """
        An error is raised if current working folder contains a temporary
        folder and folder is cleaned.
        """
        # Our compat filesystem API does not support creating files in
        # current working directory so we use direct API call to OS.
        name = mk.string()
        os.mkdir(mk.fs.getEncodedPath(name))

        self.check_assertWorkingFolderIsClean([name])

    def test_assertWorkingFolderIsClean_with_file(self):
        """
        An error is raised if current working folder contains a temporary
        file and file is cleaned.
        """
        name = mk.string()
        open(mk.fs.getEncodedPath(name), 'a').close()

        self.check_assertWorkingFolderIsClean([name])

    def test_assertWorkingFolderIsClean_with_file_and_folder(self):
        """
        An error is raised if current working folder contains a temporary
        folder and file, and folder and folder is cleaned.
        """
        file_name = mk.string()
        folder_name = mk.string()
        open(mk.fs.getEncodedPath(file_name), 'a').close()
        os.mkdir(mk.fs.getEncodedPath(folder_name))

        self.check_assertWorkingFolderIsClean([file_name, folder_name])

    def test_assertIsEmpty(self):
        """
        Raise an exception when not empty and otherwise does nothing.
        """
        self.assertIsEmpty(())
        self.assertIsEmpty([])
        self.assertIsEmpty('')
        self.assertIsEmpty(set())

        with self.assertRaises(AssertionError) as context:
            self.assertIsEmpty((1, 2))

        self.assertEqual(
            'Iterable is not empty.\n(1, 2).', context.exception.args[0])

    def test_assertCompatError_no_CompatError(self):
        """
        Will show the details if error is not an CompatError.
        """
        exception = self.assertRaises(
            AssertionError,
            self.assertCompatError,
            u'123-id',
            Exception('generic-error')
            )

        self.assertEqual(
            "Error generic-error not CompatError but "
            "<type 'exceptions.Exception'>",
            exception.args[0],
            )

    def test_assertCompatError_bad_id(self):
        """
        Will show the details if error is not an CompatError.
        """
        exception = self.assertRaises(
            AssertionError,
            self.assertCompatError,
            u'123-id',
            CompatError(u'456', u'Some details.')
            )

        self.assertEqual(
            'Error id for CompatError 456 - Some details. is not 123-id, '
            'but 456.',
            exception.args[0],
            )

    def test_assertIteratorEqual_no_iterable(self):
        """
        Raise an exception if the actual value is not iterable.
        """
        sut = [1, 3]

        exception = self.assertRaises(
            AssertionError,
            self.assertIteratorEqual,
            [],
            sut,
            )

        self.assertEqual(
            'Value is not iterable.',
            exception.args[0],
            )

    def test_assertIteratorEqual_ok(self):
        """
        All file is iterator is equal.
        """
        value = [1, b'3', u'a', iter([2])]
        sut = iter(value)

        self.assertIteratorEqual(value, sut)

    def test_assertIteratorEqual_less(self):
        """
        All file is iterator is equal.
        """
        value = [1, b'3', u'a']
        sut = iter(value)

        exception = self.assertRaises(
            AssertionError,
            self.assertIteratorEqual,
            [1],
            sut,
            )

        # The check here is more complicated since the message relies on the
        # assertEqual implementation.
        self.assertStartsWith(
            "Lists differ: [1] != [1, '3', u'a']",
            exception.args[0],
            )
