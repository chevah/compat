# Copyright (c) 2011 Adi Roiban.
# See LICENSE for details.
"""
Tests for the system compatibility module.
"""

import os

from chevah_compat.testing import ChevahTestCase, mk


def setup_package():
    """
    Called before running all tests.
    """
    drop_user = os.environ.get('CHEVAH_DROP_USER', '-')

    if drop_user != '-':
        ChevahTestCase.initialize(drop_user=drop_user)
        ChevahTestCase.dropPrivileges()

    # Prepare the main testing filesystem.
    mk.fs.setUpTemporaryFolder()


def teardown_package():
    """
    Called after all tests were run.
    """
    # Remove main testing folder.
    mk.fs.tearDownTemporaryFolder()
    mk.fs.checkCleanTemporaryFolders()
