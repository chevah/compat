# Copyright (c) 2013 Adi Roiban.
# See LICENSE for details.
"""
Test for portable system users access for Domain Controller.
"""

from chevah.compat import (
    system_users,
    )
from chevah.compat.testing import (
    CompatTestCase,
    TEST_ACCOUNT_USERNAME_DOMAIN,
    TEST_DOMAIN,
    )


class TestSystemUsers(CompatTestCase):
    """
    SystemUsers tests with users from Domain Controller.
    """

    def test_userExists_good(self):
        """
        Return `True` when user exists.
        """
        upn = u'%s@%s' % (TEST_ACCOUNT_USERNAME_DOMAIN, TEST_DOMAIN)
        non_existent = u'nonexistent@%s' % (TEST_DOMAIN)
        self.assertTrue(system_users.userExists(upn))
        self.assertFalse(system_users.userExists(non_existent))
