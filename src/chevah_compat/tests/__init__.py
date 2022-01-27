# Copyright (c) 2011 Adi Roiban.
# See LICENSE for details.
"""
Tests for the system compatibility module.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from chevah.compat.testing import mk


def setup_package():
    """
    Called before running all tests.
    """
    # Prepare the main testing filesystem.
    mk.fs.setUpTemporaryFolder()


def teardown_package():
    """
    Called after all tests were run.
    """
    # Remove main testing folder.
    mk.fs.tearDownTemporaryFolder()
    mk.fs.checkCleanTemporaryFolders()
