# Copyright (c) 2011 Adi Roiban.
# See LICENSE for details.
"""
Tests for the testing infrastructure.
"""

from chevah_compat.testing import ChevahTestCase, mk
from chevah_compat.testing.mockup import ChevahCommonsFactory


class TestFactory(ChevahTestCase):
    """
    Test for test objects factory.
    """

    def test_string(self):
        """
        It will return different values at each call.

        Value is Unicode.
        """
        self.assertNotEqual(mk.string(), mk.string())
        self.assertIsInstance(str, mk.string())

    def test_number(self):
        """
        It will return different values at each call.
        """
        self.assertNotEqual(mk.number(), mk.number())

    def test_ascii(self):
        """
        It will return different values at each call.

        Value is str.
        """
        self.assertNotEqual(mk.ascii(), mk.ascii())
        self.assertIsInstance(str, mk.ascii())

    def test_bytes(self):
        """
        It will return different values with each call.
        """
        self.assertNotEqual(mk.bytes(), mk.bytes())
        self.assertIsInstance(bytes, mk.bytes())

    def assertUnicodeDecodeError(self, exception):
        """
        Check the error message for Unicode decode error.
        """
        expected = 'invalid start byte'
        self.assertEndsWith(expected, exception.reason)

    def test_bytes_string_conversion_utf8_default(self):
        """
        Conversion to unicode will fail for ASCII/UTF-8 for the default size.
        """
        value = mk.bytes()

        self.assertEqual(len(value), 8)

        with self.assertRaises(UnicodeDecodeError) as context:
            value.decode()

        self.assertUnicodeDecodeError(context.exception)

        with self.assertRaises(UnicodeDecodeError) as context:
            value.decode(encoding='ascii')

        self.assertEndsWith(
            'ordinal not in range(128)',
            context.exception.reason,
        )

        with self.assertRaises(UnicodeDecodeError) as context:
            value.decode(encoding='utf-8')

        self.assertEndsWith('invalid start byte', context.exception.reason)

    def test_bytes_string_conversion_utf8_arbitrary(self):
        """
        Conversion to unicode will fail for ASCII/UTF-8 for an array of an
        arbitrary size.
        """
        value = mk.bytes(10)

        self.assertEqual(len(value), 10)

        with self.assertRaises(UnicodeDecodeError) as context:
            value.decode()

        self.assertUnicodeDecodeError(context.exception)

        with self.assertRaises(UnicodeDecodeError) as context:
            value.decode(encoding='ascii')

        self.assertEndsWith(
            'ordinal not in range(128)',
            context.exception.reason,
        )

        with self.assertRaises(UnicodeDecodeError) as context:
            value.decode(encoding='utf-8')

        self.assertEndsWith('invalid start byte', context.exception.reason)

    def test_bytes_string_conversion_utf16_default(self):
        """
        Conversion to unicode will succeed for UTF-16 for the default size.
        """
        value = mk.bytes()

        value.decode(encoding='utf-16')

    def test_bytes_string_conversion_utf16_valid(self):
        """
        Conversion to unicode will succeed for UTF-16 when an array of valid
        size is used.
        """
        value = mk.bytes(16)

        self.assertEqual(len(value), 16)

        value.decode(encoding='utf-16')

    def test_bytes_string_conversion_utf16_invalid(self):
        """
        Conversion to unicode will fail for UTF-16 when an invalid size
        is used.
        """
        value = mk.bytes(size=15)

        self.assertEqual(len(value), 15)

        with self.assertRaises(UnicodeDecodeError) as context:
            value.decode(encoding='utf-16')

        self.assertEndsWith(context.exception.reason, 'truncated data')

    class OneFactory(ChevahCommonsFactory):
        """
        Minimal class to help with testing
        """

    class OtherFactory(ChevahCommonsFactory):
        """
        Minimal class to help with testing
        """

    def test_getUniqueInteger(self):
        """
        Integer is unique between various classes implementing the factory.
        """
        one = self.OneFactory()
        other = self.OtherFactory()

        self.assertNotEqual(one.getUniqueInteger(), other.getUniqueInteger())

    def test_getTestUser_not_found(self):
        """
        Returns `None` if user is not found.
        """
        result = mk.getTestUser('no-such-user-ever')

        self.assertIsNone(result)
