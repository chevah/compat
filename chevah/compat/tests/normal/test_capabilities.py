# -*- coding: utf-8 -*-
# Copyright (c) 2011 Adi Roiban.
# See LICENSE for details.
'''Test system users portable code code.'''
from __future__ import with_statement
import os

from zope.interface.verify import verifyObject

from chevah.compat import process_capabilities
from chevah.empirical.testcase import ChevahTestCase
from chevah.compat.exceptions import CompatException
from chevah.compat.interfaces import IProcessCapabilities


class TestProcessCapabilities(ChevahTestCase):

    def setUp(self):
        super(TestProcessCapabilities, self).setUp()
        self.capabilities = process_capabilities

    def test_init(self):
        """
        Check ProcessCapabilities initialization.
        """
        verifyObject(IProcessCapabilities, self.capabilities)

    def test_impersonate_local_account(self):
        """
        When running under normal account, impersonation is always False
        on Unix and always True on Windows.
        """
        result = self.capabilities.impersonate_local_account
        if os.name == 'posix':
            self.assertFalse(result)
        elif os.name == 'nt':
            self.assertTrue(result)
        else:
            raise AssertionError('Unsupported os.')

    def test_create_home_folder(self):
        """
        When running under normal account, we can not create home folders
        on Unix.

        On Windows home folders can be created if required privileges
        are configured for the process.
        """
        result = self.capabilities.create_home_folder
        if os.name == 'posix':
            self.assertFalse(result)
        elif os.name == 'nt':
            self.assertTrue(result)
        else:
            raise AssertionError('Unsupported os.')

    def test_get_home_folder(self):
        """
        On Unix we can always get home home folder.
        On Windows, only Windows 2008 and Windows 7 can get home folder path.
        """
        result = self.capabilities.get_home_folder
        if os.name == 'posix':
            self.assertTrue(result)
        elif os.name == 'nt':
            # The Windows test is handled in elevated module.
            pass
        else:
            raise AssertionError('Unsupported os.')

    def test_getCurrentPrivilegesDescription(self):
        """
        Check getCurrentPrivilegesDescription.
        """
        text = self.capabilities.getCurrentPrivilegesDescription()
        if os.name == 'posix':
            self.assertEqual(u'root capabilities disabled.', text)
        else:
            # Windows tests are done in elevated
            self.assertTrue('SeChangeNotifyPrivilege' in text, text)


class TestNTProcessCapabilities(TestProcessCapabilities):

    def setUp(self):
        super(TestNTProcessCapabilities, self).setUp()

        if os.name != 'nt':
            raise self.skipTest("Only Windows platforms supported.")

    def test_openProcess_no_mode(self):
        """
        _openProcess fails if no mode is specified.
        """
        with self.assertRaises(TypeError):
            self.capabilities._openProcess()

    def test_openProcess_succeed(self):
        """
        _openProcess can be used for process token for the current
        process having a specified mode enabled.
        """
        import win32security
        with self.capabilities._openProcess(win32security.TOKEN_QUERY) as (
                process_token):
            self.assertIsNotNone(process_token)

    def test_openProcess_failed(self):
        """
        A CompatException is raised when trying to open the process with
        a mode which is not allowed.
        """
        import win32security
        # TODO: Find a mode which is not enabled for normal users or
        # some condition which makes the process opening fail.
        mode = win32security.TOKEN_QUERY
        with self.assertRaises(CompatException) as context:
            self.capabilities._openProcess(mode)

        self.assertEqual('some failure', context.excetion.message)
