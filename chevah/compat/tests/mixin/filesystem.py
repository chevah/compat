# Copyright (c) 2010 Adi Roiban.
# See LICENSE for details.
"""
Tests for portable filesystem access.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from chevah.compat.testing import conditionals, mk


class SymbolicLinksMixin(object):
    """
    Unit tests for `makeLink` executed by an OS account which has permission
    to create symbolic links.
    """

    @conditionals.onCapability('symbolic_link', True)
    def test_makeLink_good(self):
        """
        Can create link under impersonated account.
        """
        target_segments = self.filesystem.home_segments
        target_segments.append(mk.string())
        file_object = self.filesystem.openFileForWriting(target_segments)
        file_object.close()
        self.addCleanup(self.filesystem.deleteFile, target_segments)
        link_segments = self.filesystem.home_segments
        link_segments.append(mk.string())

        self.filesystem.makeLink(
            target_segments=target_segments,
            link_segments=link_segments,
            )

        self.addCleanup(self.filesystem.deleteFile, link_segments)
        self.assertTrue(self.filesystem.isLink(link_segments))
        self.assertTrue(self.filesystem.exists(link_segments))

    @conditionals.onCapability('symbolic_link', True)
    def test_makeLink_bad_target(self):
        """
        Can create broken links under impersonated account.
        """
        segments = self.filesystem.home_segments
        segments.append(mk.string())

        self.filesystem.makeLink(
            target_segments=['z', 'no-such', 'target'],
            link_segments=segments,
            )

        self.addCleanup(self.filesystem.deleteFile, segments)
        self.assertTrue(self.filesystem.isLink(segments))
        self.assertFalse(self.filesystem.exists(segments))

    @conditionals.onCapability('symbolic_link', True)
    def test_makeLink_invalid_link(self):
        """
        Raise an error when link can not be created under impersonated
        account.
        """
        with self.assertRaises(OSError):
            mk.fs.makeLink(
                target_segments=self.filesystem.temp_segments,
                link_segments=['no-such', 'link'],
                )
