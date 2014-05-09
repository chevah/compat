# Copyright (c) 2011 Adi Roiban.
# See LICENSE for details.
"""
Tests for the testing infrastructure.
"""
from chevah.compat.testing import ChevahTestCase, manufacture


class TestFactory(ChevahTestCase):
    """
    Test for factory methods.
    """

    def test_avatar_unicode(self):
        """
        Check that avatar is created with unicode members.
        """
        avatar = manufacture.makeFilesystemApplicationAvatar()
        self.assertTrue(type(avatar.name) is unicode)
        self.assertTrue(type(avatar.home_folder_path) is unicode)
