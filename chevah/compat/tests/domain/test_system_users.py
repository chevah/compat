# -*- coding: utf-8 -*-
# Copyright (c) 2013 Adi Roiban.
# See LICENSE for details.
"""
Test for portable system users access for Domain Controller.
"""

import os
from chevah.compat import (
    system_users,
    )
from chevah.compat.administration import os_administration
from chevah.compat.testing import (
    CompatTestCase,
    mk,
    TEST_ACCOUNT_USERNAME_DOMAIN,
    TEST_ACCOUNT_PASSWORD_DOMAIN,
    TEST_DOMAIN,
    TestUser,
    )


class TestSystemUsers(CompatTestCase):
    """
    SystemUsers tests with users from Domain Controller.
    """

    def test_userExists(self):
        """
        Return `True` when the user used for testing exists and a non existent
        generated user doesn't exists.
        """
        upn = u'%s@%s' % (TEST_ACCOUNT_USERNAME_DOMAIN, TEST_DOMAIN)
        non_existent = u'nonexistent@%s' % (TEST_DOMAIN)
        self.assertTrue(system_users.userExists(upn))
        self.assertFalse(system_users.userExists(non_existent))

    def test_isUserInGroups(self):
        """
        Return `True` when the user used for testing is included in required
        group.
        """
        upn = u'%s@%s' % (TEST_ACCOUNT_USERNAME_DOMAIN, TEST_DOMAIN)
        # FIXME: 1273:
        # not working with 'TEST_ACCOUNT_GROUP_DOMAIN'
        #groups = [TEST_ACCOUNT_GROUP_DOMAIN]
        groups = [u'Domain Users']
        groups_non_existent = [u'non-existent-group']

        token = mk.makeToken(
            username=upn, password=TEST_ACCOUNT_PASSWORD_DOMAIN)

        self.assertTrue(system_users.isUserInGroups(upn, groups, token))
        self.assertFalse(system_users.isUserInGroups(
            upn, groups_non_existent, token))

    def test_authenticateWithUsernameAndPassword_good(self):
        """
        Check successful call to authenticateWithUsernameAndPassword.
        """
        result, token = system_users.authenticateWithUsernameAndPassword(
            username=TEST_ACCOUNT_USERNAME_DOMAIN,
            password=TEST_ACCOUNT_PASSWORD_DOMAIN,
            )

        self.assertIsNotNone(token)

    def test_authenticateWithUsernameAndPassword_bad_password(self):
        """
         Check authentication with bad password.
        """
        result, token = system_users.authenticateWithUsernameAndPassword(
                username=TEST_ACCOUNT_USERNAME_DOMAIN,
                password=u'mțș',
                )

        self.assertFalse(result)
        self.assertIsNone(token)

    def test_authenticateWithUsernameAndPassword_bad_user(self):
        """
        Check authentication for bad user.
        """
        result, token = system_users.authenticateWithUsernameAndPassword(
                username=u'other-mșț', password=u'other-mțs')

        self.assertFalse(result)
        self.assertIsNone(token)

    def test_executeAsUser(self):
        """
        Test executing as a different user.
        """

        # FIXME : 1273:
        # Not a good test. The test should run as Administrator and execute
        # a command as a normal user.
        username = TEST_ACCOUNT_USERNAME_DOMAIN
        token = mk.makeToken(
            username=username, password=TEST_ACCOUNT_PASSWORD_DOMAIN)

        with system_users.executeAsUser(
            username=username, token=token):
            self.assertEqual(
                username, system_users.getCurrentUserName())

    def test_getHomeFolder_good(self):
        """
        If a valid token is provided the home folder path can be retrieved
        for any other account, as long as the process has the required
        capabilities.
        """
        token = mk.makeToken(
            username=TEST_ACCOUNT_USERNAME_DOMAIN,
            password=TEST_ACCOUNT_PASSWORD_DOMAIN
            )

        home_folder = system_users.getHomeFolder(
            username=TEST_ACCOUNT_USERNAME_DOMAIN, token=token)

        self.assertContains(
            TEST_ACCOUNT_USERNAME_DOMAIN.lower(), home_folder.lower())

    def test_getHomeFolder_nt_no_previous_profile(self):
        """
        On Windows, if user has no profile it will be created.

        This tests creates a temporary account and in the end it deletes
        the account and home folder.
        """
        username = u'no-home'
        password = u'qwe123QWE'
        home_path = None
        domain = 'chevah'
        pdc = 'chevah-dc'

        user = TestUser(
            name=username,
            uid=None,
            password=password,
            home_path=home_path,
            domain=domain,
            pdc=pdc)

        try:
            # We don't want to create the profile here since this is
            # what we are testing.
            os_administration._addUser_windows(user, create_profile=False)
            token = mk.makeToken(username=username, password=password)

            home_path = system_users.getHomeFolder(
                username=username + '@' + domain, token=token)

            self.assertTrue(
                username.lower() in home_path.lower(),
                'Home folder "%s" is not good for user "%s"' % (
                    home_path, username))
        finally:
            os_administration.deleteUser(user)
            # Delete user does not removed the user home folder,
            # so we explicitly remove it here.
            if home_path:
                os.system('rmdir /S /Q ' + home_path.encode('utf-8'))
