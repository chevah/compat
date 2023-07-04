# Copyright (c) 2015 Adi Roiban.
# See LICENSE for details.
"""
Tests for the assertion helpers.
"""
import os

from chevah_compat.exceptions import CompatError
from chevah_compat.testing import ChevahTestCase, mk


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

        message = context.exception.args[0]
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

        message = context.exception.args[0]
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
            u'Iterable is not empty.\n(1, 2).', context.exception.args[0])

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
            "<class 'Exception'>",
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

    def test_assertIteratorItemsEqual_no_iterable(self):
        """
        Raise an exception if the actual value is not iterable.
        """
        sut = [1, 3]

        exception = self.assertRaises(
            AssertionError,
            self.assertIteratorItemsEqual,
            [],
            sut,
            )

        self.assertEqual(
            'Value is not iterable.',
            exception.args[0],
            )

    def test_assertIteratorItemsEqual_ok(self):
        """
        Is equal even if elements are in a different order.
        """
        iterator = iter([2])
        value = [1, b'3', u'a', iterator]
        sut = iter(value)

        self.assertIteratorItemsEqual([b'3', 1, u'a', iterator], sut)

    def test_assertIteratorItemsEqual_less(self):
        """
        It fails if the values are not equal.
        """
        value = [1, b'3', u'a']
        sut = iter(value)

        exception = self.assertRaises(
            AssertionError,
            self.assertIteratorItemsEqual,
            [1],
            sut,
            )

        # The check here is more complicated since the message relies on the
        # assertEqual implementation.
        self.assertStartsWith(
            "Element counts were not equal:",
            exception.args[0],
            )

    def test_assertEqual_unicode_vs_bytestring_in_list(self):
        """
        Fails with AssertionError when asserting that lists containing
        a Unicode string vs. a bytestring are equal.
        """

        unicode_list = [u'text']
        bytes_list = [b'text']
        with self.assertRaises(AssertionError):
            self.assertEqual(unicode_list, bytes_list)

    def test_assertEqual_unicode_vs_bytestring_in_nested_list(self):
        """
        Fails with AssertionError when asserting that nested lists containing
        a Unicode string vs. a bytestring are equal.
        """

        unicode_list = [[u'text']]
        bytes_list = [[b'text']]
        with self.assertRaises(AssertionError):
            self.assertEqual(unicode_list, bytes_list)

    def test_assertEqual_unicode_vs_bytestring_in_tuple(self):
        """
        Fails with AssertionError when asserting that tuples containing
        a Unicode string vs. a bytestring are equal.
        """

        unicode_tuple = (u'text',)
        bytes_tuple = (b'text',)
        with self.assertRaises(AssertionError):
            self.assertEqual(unicode_tuple, bytes_tuple)

    def test_assertEqual_unicode_vs_bytestring_in_set(self):
        """
        Fails with AssertionError when asserting that sets containing
        a Unicode string vs. a bytestring are equal.
        """

        unicode_set = set([u'text'])
        bytes_set = set([b'text'])
        with self.assertRaises(AssertionError):
            self.assertEqual(unicode_set, bytes_set)

    def test_assertEqual_unicode_vs_bytestring_in_dict_keys(self):
        """
        Fails with AssertionError when asserting that lists containing
        a Unicode string vs. a bytestring are equal.
        """

        unicode_dict = {u'key': 'value'}
        bytes_dict = {b'key': 'value'}
        with self.assertRaises(AssertionError):
            self.assertEqual(unicode_dict, bytes_dict)

    def test_assertEqual_unicode_vs_bytestring_in_dict_values(self):
        """
        Fails with AssertionError when asserting that lists containing
        a Unicode string vs. a bytestring are equal.
        """

        unicode_dict = {'key': u'value'}
        bytes_dict = {'key': b'value'}
        with self.assertRaises(AssertionError):
            self.assertEqual(unicode_dict, bytes_dict)
