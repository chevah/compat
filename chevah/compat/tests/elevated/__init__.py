# Copyright (c) 2012 Adi Roiban.
# See LICENSE for details.
'''Code for testing compat module that requires access to system security
functions.'''

from chevah.empirical.testcase import (
    ChevahTestCase,
    setup_os,
    teardown_os,
    )
from chevah.empirical.constants import (
    TEST_GROUPS,
    TEST_USERS,
    )


def setup_package():
    # Don't run these tests if we can not access privileged OS part.
    if not ChevahTestCase.haveSuperPowers():
        raise ChevahTestCase.skipTest()
    # Initialize the testing OS.

    try:
        setup_os(users=TEST_USERS, groups=TEST_GROUPS)
    except:
        import traceback
        print traceback.format_exc()
        print "Failed to initilized the system accounts!"
        teardown_os(users=TEST_USERS, groups=TEST_GROUPS)
        raise


def teardown_package():
    teardown_os(users=TEST_USERS, groups=TEST_GROUPS)
