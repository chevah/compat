# Copyright (c) 2011 Adi Roiban.
# See LICENSE for details.
"""
Capabilities detection tests for accounts with elevated permissions.
"""
import os

from chevah.compat import process_capabilities
from chevah.empirical import ChevahTestCase


class TestProcessCapabilities(ChevahTestCase):

    def setUp(self):
        super(TestProcessCapabilities, self).setUp()
        self.capabilities = process_capabilities

    def test_impersonate_local_account(self):
        """
        When running as super user we can always impersonate local accounts.
        """
        result = self.capabilities.impersonate_local_account
        self.assertTrue(result)

    def test_create_home_folder(self):
        """
        When running as super user, we can always create home folders.
        """
        result = self.capabilities.create_home_folder
        self.assertTrue(result)

    def test_get_home_folder(self):
        """
        On unix we can always get home folder.

        On Windows 7 and 2008 home folder path can be retrieved. On
        all other system below Windows 7, the home folder can not be
        retrieved yet.
        """
        result = self.capabilities.get_home_folder
        hostname = self.getHostname()
        if 'win-xp' in hostname or 'win-2003' in hostname:
            self.assertFalse(result)
        else:
            self.assertTrue(result)

    def test_getCurrentPrivilegesDescription(self):
        """
        Check getCurrentPrivilegesDescription.
        """
        if os.name == 'posix':
            text = self.capabilities.getCurrentPrivilegesDescription()
            self.assertEqual(u'root capabilities enabled.', text)
        else:
            # Windows tests are done in the normal tests.
            pass
