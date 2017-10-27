# Copyright (c) 2013 Adi Roiban.
# See LICENSE for details.
"""
Test for portable system users access for Domain Controller.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import os
from six import text_type

from chevah.compat import (
    system_users,
    )
from chevah.compat.administration import os_administration
from chevah.compat.testing import (
    CompatTestCase,
    mk,
    TEST_ACCOUNT_PASSWORD_DOMAIN,
    TEST_ACCOUNT_USERNAME_DOMAIN,
    TEST_DOMAIN,
    TEST_PDC,
    TestUser,
    )


class TestSystemUsers(CompatTestCase):
    """
    SystemUsers tests with users from Domain Controller.
    """

    def test_userExists(self):
        """
        Returns `True` if the user exists and `False` otherwise.
        """
        upn = u'%s@%s' % (TEST_ACCOUNT_USERNAME_DOMAIN, TEST_DOMAIN)
        non_existent = u'nonexistent@%s' % (TEST_DOMAIN)
        self.assertTrue(system_users.userExists(upn))
        self.assertFalse(system_users.userExists(non_existent))

    def test_isUserInGroups(self):
        """
        Return `True` when the user is member of the group and
        `False` otherwise.
        """
        test_user = mk.getTestUser(u'domain')
        # FIXME:1471:
        # Don't know why is not working with TEST_ACCOUNT_GROUP_DOMAIN so
        # for now we use the default group.
        groups = [u'Domain Users']
        groups_non_existent = [u'non-existent-group']

        self.assertTrue(system_users.isUserInGroups(
            test_user.upn, groups, test_user.token))
        self.assertFalse(system_users.isUserInGroups(
            test_user.upn, groups_non_existent, test_user.token))

    def test_authenticateWithUsernameAndPassword_good(self):
        """
        Return `True` when username and passwords are valid, together
        with a token that can be used for impersonating the account.
        """
        result, token = system_users.authenticateWithUsernameAndPassword(
            username=TEST_ACCOUNT_USERNAME_DOMAIN,
            password=TEST_ACCOUNT_PASSWORD_DOMAIN,
            )

        self.assertIsTrue(result)
        self.assertIsNotNone(token)

        with system_users.executeAsUser(
                username=TEST_ACCOUNT_USERNAME_DOMAIN, token=token):
            self.assertEqual(
                TEST_ACCOUNT_USERNAME_DOMAIN,
                system_users.getCurrentUserName(),
                )

    def test_authenticateWithUsernameAndPassword_bad_password(self):
        """
        `False` is returned when a bad password is provided.
        """
        result, token = system_users.authenticateWithUsernameAndPassword(
            username=TEST_ACCOUNT_USERNAME_DOMAIN, password=mk.string())

        self.assertFalse(result)
        self.assertIsNone(token)

    def test_authenticateWithUsernameAndPassword_bad_user(self):
        """
        `False` is returned when a bad user is provided.
        """
        result, token = system_users.authenticateWithUsernameAndPassword(
            username=mk.string(), password=mk.string())

        self.assertFalse(result)
        self.assertIsNone(token)

    def test_executeAsUser(self):
        """
        It uses the token to impersonate the account under which this
        process is executed..
        """
        test_user = mk.getTestUser(u'domain')

        self.assertNotEqual(test_user.name, system_users.getCurrentUserName())

        with system_users.executeAsUser(
                username=test_user.name, token=test_user.token):
            self.assertEqual(
                test_user.name, system_users.getCurrentUserName())

    def test_getHomeFolder_good(self):
        """
        If a valid token is provided the home folder path can be retrieved
        for any other account, as long as the process has the required
        capabilities.
        """
        test_user = mk.getTestUser(u'domain')

        home_folder = system_users.getHomeFolder(
            username=test_user.name, token=test_user.token)

        self.assertContains(test_user.name.lower(), home_folder.lower())
        self.assertIsInstance(text_type, home_folder)

    def test_getHomeFolder_nt_no_previous_profile(self):
        """
        On Windows, if user has no local home folder it will be created
        automatically when getting the home folder path.

        This tests creates a temporary account and in the end it deletes
        the account and home folder.
        """
        test_user = TestUser(
            name=u'domain no-home',
            password=mk.string(),
            domain=TEST_DOMAIN,
            pdc=TEST_PDC,
            )
        # Unfortunately there is no API to get default base home path for
        # users, we need to rely on an existing pattern.
        home_base = os.path.dirname(os.getenv('USERPROFILE'))
        expected_home_path = os.path.join(home_base, test_user.name)
        expected_home_segments = mk.fs.getSegmentsFromRealPath(
            expected_home_path)

        try:
            os_administration.addUser(test_user)
            # Home folder path is not created on successful login.
            token = test_user.token
            self.assertFalse(mk.fs.isFolder(expected_home_segments))

            home_path = system_users.getHomeFolder(
                username=test_user.upn, token=token)

            self.assertContains(test_user.name.lower(), home_path.lower())
            self.assertIsInstance(text_type, home_path)
            self.assertTrue(mk.fs.isFolder(expected_home_segments))
        finally:
            os_administration.deleteUser(test_user)
            os_administration.deleteHomeFolder(test_user)
