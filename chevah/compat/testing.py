# -*- coding: utf-8 -*-
# Copyright (c) 2012 Adi Roiban.
# See LICENSE for details.
"""
Helpers for testing.
"""
import os
import sys

from chevah.empirical.testcase import ChevahTestCase
from chevah.empirical.mockup import ChevahCommonsFactory

from chevah.compat import system_users
from chevah.compat.avatar import (
    FilesystemApplicationAvatar,
    FilesystemOSAvatar,
    )


# Export ChevahTestCase from here.
ChevahTestCase

# Test accounts and passwords.
TEST_ACCOUNT_USERNAME = u'mâț mițișor'
TEST_ACCOUNT_PASSWORD = u'Baroșanu42!'
TEST_ACCOUNT_GROUP = u'g mâțmițișor'
TEST_ACCOUNT_UID = 2000
TEST_ACCOUNT_GID = 2010
TEST_ACCOUNT_GROUP_WIN = u'Users'
TEST_ACCOUNT_USERNAME_OTHER = u'miț motan'
TEST_ACCOUNT_PASSWORD_OTHER = u'altapara'
TEST_ACCOUNT_UID_OTHER = 2001
TEST_ACCOUNT_GID_OTHER = 2011
TEST_ACCOUNT_GROUP_OTHER = u'g mițmotan'
TEST_ACCOUNT_LDAP_USERNAME = u'ldap mâț test-account'
TEST_ACCOUNT_LDAP_PASSWORD = u'ldap mâț test-password'
# An ascii username with no shell.
# To be used on system without Unicode suport.
# It is also used for testing SSL based authentication.
TEST_ACCOUNT_USERNAME_TEMP = u'test_user'
TEST_ACCOUNT_UID_TEMP = 2002

# Centrify testing account.
TEST_ACCOUNT_CENTRIFY_USERNAME = u'centrify-user'
TEST_ACCOUNT_CENTRIFY_PASSWORD = u'Parola01!'
TEST_ACCOUNT_CENTRIFY_UID = 1363149908

# Another test group to test an user belonging to multiple groups.
TEST_ACCOUNT_GROUP_ANOTHER = u'g-another-test'
TEST_ACCOUNT_GID_ANOTHER = 2012


class TestUser(object):
    '''An object storing all user information.'''

    def __init__(self, name, uid=None, gid=None, home_path=None,
            home_group=None, shell=None, shadow=None, password=None,
            domain=None):
        if home_path is None:
            home_path = u'/tmp'

        if shell is None:
            shell = u'/bin/sh'

        if shadow is None:
            shadow = '!'

        if gid is None:
            gid = uid

        self.name = name
        self.uid = uid
        self.gid = gid
        self.home_path = home_path
        self.home_group = home_group
        self.shell = shell
        self.shadow = shadow
        self.password = password
        self.domain = domain


class TestGroup(object):
    '''An object storing all user information.'''

    def __init__(self, name, gid=None, members=None, domain=None):

        if members is None:
            members = []

        self.name = name
        self.gid = gid
        self.members = members
        self.domain = domain


if sys.platform.startswith('aix'):
    fix_username = lambda name: name.replace(' ', '_')[:5]
    fix_groupname = fix_username
if sys.platform.startswith('win'):
    # FIXME:927:
    # On Windows, we can't delete home folders with unicode names.
    from unidecode import unidecode
    fix_username = lambda name: unicode(unidecode(name))
    fix_groupname = fix_username
else:
    fix_username = lambda name: name
    fix_groupname = fix_username

TEST_ACCOUNT_USERNAME = fix_username(TEST_ACCOUNT_USERNAME)
TEST_ACCOUNT_GROUP = fix_groupname(TEST_ACCOUNT_GROUP)
TEST_ACCOUNT_USERNAME_OTHER = fix_username(TEST_ACCOUNT_USERNAME_OTHER)
TEST_ACCOUNT_GROUP_OTHER = fix_groupname(TEST_ACCOUNT_GROUP_OTHER)

if sys.platform.startswith('sunos'):
    TEST_ACCOUNT_HOME_PATH = u'/export/home/' + TEST_ACCOUNT_USERNAME
    TEST_ACCOUNT_HOME_PATH_OTHER = (
        u'/export/home/' + TEST_ACCOUNT_USERNAME_OTHER)
else:
    TEST_ACCOUNT_HOME_PATH = u'/home/' + TEST_ACCOUNT_USERNAME
    TEST_ACCOUNT_HOME_PATH_OTHER = u'/home/' + TEST_ACCOUNT_USERNAME_OTHER

TEST_USERS = [
    TestUser(
            name=TEST_ACCOUNT_USERNAME,
            uid=TEST_ACCOUNT_UID,
            gid=TEST_ACCOUNT_GID,
            home_path=TEST_ACCOUNT_HOME_PATH,
            home_group=TEST_ACCOUNT_GROUP,
            password=TEST_ACCOUNT_PASSWORD,
            ),
    TestUser(
            name=TEST_ACCOUNT_USERNAME_OTHER,
            uid=TEST_ACCOUNT_UID_OTHER,
            gid=TEST_ACCOUNT_GID_OTHER,
            home_path=TEST_ACCOUNT_HOME_PATH_OTHER,
            password=TEST_ACCOUNT_PASSWORD_OTHER,
            ),
    TestUser(
            name=TEST_ACCOUNT_USERNAME_TEMP,
            uid=TEST_ACCOUNT_UID_TEMP,
            shell=u'/bin/false',
            shadow=u'!',
            ),
    TestUser(
            name=TEST_ACCOUNT_CENTRIFY_USERNAME,
            uid=TEST_ACCOUNT_CENTRIFY_UID,
            shadow=u'NP',
            ),
    ]

TEST_GROUPS = [
    TestGroup(
        name=TEST_ACCOUNT_GROUP,
        gid=TEST_ACCOUNT_GID,
        members=[TEST_ACCOUNT_USERNAME, TEST_ACCOUNT_USERNAME_OTHER],
        ),
    TestGroup(
        name=TEST_ACCOUNT_GROUP_OTHER,
        gid=TEST_ACCOUNT_GID_OTHER,
        members=[TEST_ACCOUNT_USERNAME_OTHER],
        ),
    TestGroup(
        name=TEST_ACCOUNT_GROUP_ANOTHER,
        gid=TEST_ACCOUNT_GID_ANOTHER,
        members=[TEST_ACCOUNT_USERNAME],
        ),
    ]


class CompatTestCase(ChevahTestCase):
    """
    Test case used in chevah.compat package.

    For not, there is nothing special here.
    """


class CompatManufacture(ChevahCommonsFactory):
    """
    Generator of testing helpers for chevah.compat package.
    """

    def makeFilesystemOSAvatar(self, name=None,
            home_folder_path=None, root_folder_path=None,
            lock_in_home_folder=False,
            token=None,
            ):
        """
        Creates a valid FilesystemOSAvatar.
        """
        if name is None:
            name = self.username

        if home_folder_path is None:
            home_folder_path = self.fs.temp_path

        return FilesystemOSAvatar(
            name=name,
            home_folder_path=home_folder_path,
            root_folder_path=root_folder_path,
            lock_in_home_folder=lock_in_home_folder,
            token=token,
            )

    def makeFilesystemApplicationAvatar(self, name=None,
            home_folder_path=None, root_folder_path=None,
            ):
        """
        Creates a valid FilesystemApplicationAvatar.
        """
        if name is None:
            name = self.getUniqueString()

        if home_folder_path is None:
            home_folder_path = self.fs.temp_path

        # Application avatars are locked inside home folders.
        if root_folder_path is None:
            root_folder_path = home_folder_path

        return FilesystemApplicationAvatar(
            name=name,
            home_folder_path=home_folder_path,
            root_folder_path=root_folder_path,
            )

    def makeToken(self, username, password):
        """
        Generate the Windows token for username and password.

        Only useful on Windows.
        On Unix it should return None.
        """
        if os.name != 'nt':
            return None

        result, token = system_users.authenticateWithUsernameAndPassword(
            username=username,
            password=password,
            )
        if not result:
            raise AssertionError(
                u'Failed to get a valid token for "%s" with "%s".' % (
                    username, password))
        return token

mk = manufacture = CompatManufacture()
