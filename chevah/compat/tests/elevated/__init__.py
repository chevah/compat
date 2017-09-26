# Copyright (c) 2012 Adi Roiban.
# See LICENSE for details.
"""
Code for testing compat module that requires access to system security
functions.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from chevah.compat import process_capabilities
from chevah.compat.testing import (
    CompatTestCase,
    setup_access_control,
    teardown_access_control,
    TEST_GROUPS,
    TEST_USERS,
    )


def runElevatedTest():
    """
    Return true if we can access privileged OS operations.
    """
    if not process_capabilities.impersonate_local_account:
        return False

    if not process_capabilities.get_home_folder:
        return False

    return True


def setup_package():
    # Don't run these tests if we can not access privileged OS part.
    if not runElevatedTest():
        raise CompatTestCase.skipTest()

    # Initialize the testing OS.
    try:
        setup_access_control(users=TEST_USERS, groups=TEST_GROUPS)
    except Exception:  # pragma: no cover
        import traceback
        print(traceback.format_exc())
        print("Failed to initialized the system accounts!")
        teardown_access_control(users=TEST_USERS, groups=TEST_GROUPS)
        raise


def teardown_package():
    teardown_access_control(users=TEST_USERS, groups=TEST_GROUPS)
