# Copyright (c) 2011 Adi Roiban.
# See LICENSE for details.
"""
Tests for the testing infrastructure.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from chevah.compat.testing import ChevahTestCase, mk


class TestFactory(ChevahTestCase):
    """
    Test for factory methods.
    """

    def test_avatar_unicode(self):
        """
        Check that avatar is created with unicode members.
        """
        avatar = mk.makeFilesystemApplicationAvatar()
        self.assertIsInstance(avatar.name, unicode)
        self.assertIsInstance(avatar.home_folder_path, unicode)
