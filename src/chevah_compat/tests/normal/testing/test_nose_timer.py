# Copyright (c) 2015 Adi Roiban.
# See LICENSE for details.
"""
Tests for nose test timer plugin.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from nose.plugins.attrib import attr

from chevah.compat.testing import ChevahTestCase


class TestTestTimer(ChevahTestCase):
    """
    Test for TestTimer.
    """

    @attr('some_attribute', other_attribute=42)
    def test_attributes_wrapper(self):
        """
        When timer it used the attributes associated with a test method
        are still available.
        """
        test_target = getattr(self, self._testMethodName)
        self.assertTrue(test_target.some_attribute)
        self.assertEqual(42, test_target.other_attribute)
