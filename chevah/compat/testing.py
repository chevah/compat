# -*- coding: utf-8 -*-
# Copyright (c) 2012 Adi Roiban.
# See LICENSE for details.
"""
Helpers for testing.
"""
import os
import random
import sys

from unidecode import unidecode

from chevah.empirical import conditionals
from chevah.empirical.filesystem import LocalTestFilesystem
from chevah.empirical.testcase import ChevahTestCase
from chevah.empirical.mockup import ChevahCommonsFactory

from chevah.compat import (
    LocalFilesystem,
    process_capabilities,
    system_users,
    )
from chevah.compat.administration import os_administration
from chevah.compat.avatar import (
    FilesystemApplicationAvatar,
    FilesystemOSAvatar,
    )
from chevah.compat.exceptions import CompatError


# Shut up the linter.
ChevahTestCase
conditionals


class CompatManufacture(ChevahCommonsFactory):
    """
    Generator of testing helpers for chevah.compat package.
    """

    # Class member used for generating unique user/group id(s).
    _posix_id = random.randint(2000, 3000)

    def makeFilesystemOSAvatar(
        self, name=None, home_folder_path=None, root_folder_path=None,
        lock_in_home_folder=False, token=None,
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

    def makeFilesystemApplicationAvatar(
            self, name=None, home_folder_path=None, root_folder_path=None):
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

    def PosixUID(self):
        """
        Return a valid Posix Unique ID.
        """
        self.__class__._posix_id += 1
        return self.__class__._posix_id


mk = manufacture = CompatManufacture()


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

# Centrify testing account.
TEST_ACCOUNT_CENTRIFY_USERNAME = u'centrify-user'
TEST_ACCOUNT_CENTRIFY_PASSWORD = u'Parola01!'
TEST_ACCOUNT_CENTRIFY_UID = 1363149908

# Another test group to test an user belonging to multiple groups.
TEST_ACCOUNT_GROUP_ANOTHER = u'g-another-test'
TEST_ACCOUNT_GID_ANOTHER = 2012

# Domain controller helpers.
TEST_PDC = u'\\\\CHEVAH-DC'
TEST_DOMAIN = u'chevah'
TEST_ACCOUNT_USERNAME_DOMAIN = u'domain test-user'
TEST_ACCOUNT_PASSWORD_DOMAIN = u'qwe123QWE'
TEST_ACCOUNT_GROUP_DOMAIN = u'domain test_group'


# FIXME:2106:
# Get rid of global functions and replace with OS specialized TestUSer
# instances: TestUserAIX, TestUserWindows, TestUserUnix, etc.
def _sanitize_name_aix(candidate):
    """
    Return valid user/group name for AIX from `candidate`.

    By default aix is limited to 8 characters without spaces.
    """
    return unicode(unidecode(candidate)).replace(' ', '_')[:8]


def _sanitize_name_windows(candidate):
    """
    Return valid user/group name for Windows OSs from `candidate.
    """
    # FIXME:927:
    # On Windows, we can't delete home folders with unicode names.
    return unicode(unidecode(candidate))


class TestUser(object):
    """
    An object storing all user information.
    """

    @classmethod
    def sanitizeName(cls, name):
        """
        Return name sanitized for current OS.
        """
        if sys.platform.startswith('aix'):
            return _sanitize_name_aix(name)
        elif sys.platform.startswith('win'):
            return _sanitize_name_windows(name)

        return name

    def __init__(
        self, name, posix_uid=None, posix_gid=None, home_path=None,
        home_group=None, shell=None, shadow=None, password=None,
        domain=None, pdc=None, primary_group_name=None, create_profile=False,
        windows_required_rights=None
            ):
        """
        Convert user name to an OS valid value.
        """
        if home_path is None:
            home_path = u'/tmp'

        if shell is None:
            shell = u'/bin/sh'

        if shadow is None:
            shadow = '!'

        if posix_gid is None:
            posix_gid = posix_uid

        self._name = self.sanitizeName(name)
        self.uid = posix_uid
        self.gid = posix_gid
        self.home_path = home_path
        self.home_group = home_group
        self.shell = shell
        self.shadow = shadow
        self.password = password
        self.domain = domain
        self.pdc = pdc
        self.primary_group_name = primary_group_name
        self.windows_sid = None
        self.windows_create_profile = create_profile
        self.windows_required_rights = windows_required_rights

    @property
    def name(self):
        """
        Actual user name.
        """
        return self._name


class TestGroup(object):
    """
    An object storing all group information.
    """

    @classmethod
    def sanitizeName(cls, group):
        """
        Return name sanitized for current OS.
        """
        if sys.platform.startswith('aix'):
            return _sanitize_name_aix(group)
        elif sys.platform.startswith('win'):
            return _sanitize_name_windows(group)

        return group

    def __init__(self, name, gid=None, members=None, pdc=None):
        """
        Convert name to an OS valid value.
        """
        if members is None:
            members = []

        self._name = self.sanitizeName(name)
        self.gid = gid
        self.members = members
        self.pdc = pdc

    @property
    def name(self):
        """
        Actual group name.
        """
        return self._name


TEST_ACCOUNT_USERNAME = TestUser.sanitizeName(TEST_ACCOUNT_USERNAME)
TEST_ACCOUNT_GROUP = TestGroup.sanitizeName(TEST_ACCOUNT_GROUP)

TEST_ACCOUNT_USERNAME_OTHER = TestUser.sanitizeName(
    TEST_ACCOUNT_USERNAME_OTHER)
TEST_ACCOUNT_GROUP_OTHER = TestGroup.sanitizeName(TEST_ACCOUNT_GROUP_OTHER)
TEST_ACCOUNT_GROUP_ANOTHER = TestGroup.sanitizeName(
    TEST_ACCOUNT_GROUP_ANOTHER)

TEST_ACCOUNT_USERNAME_DOMAIN = TestUser.sanitizeName(
    TEST_ACCOUNT_USERNAME_DOMAIN)
TEST_ACCOUNT_GROUP_DOMAIN = TestGroup.sanitizeName(
    TEST_ACCOUNT_GROUP_DOMAIN)


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
        posix_uid=TEST_ACCOUNT_UID,
        posix_gid=TEST_ACCOUNT_GID,
        primary_group_name=TEST_ACCOUNT_GROUP,
        home_path=TEST_ACCOUNT_HOME_PATH,
        home_group=TEST_ACCOUNT_GROUP,
        password=TEST_ACCOUNT_PASSWORD,
        ),
    TestUser(
        name=TEST_ACCOUNT_USERNAME_OTHER,
        posix_uid=TEST_ACCOUNT_UID_OTHER,
        posix_gid=TEST_ACCOUNT_GID_OTHER,
        primary_group_name=TEST_ACCOUNT_GROUP_OTHER,
        home_path=TEST_ACCOUNT_HOME_PATH_OTHER,
        password=TEST_ACCOUNT_PASSWORD_OTHER,
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

    For now, there is nothing special here.
    """

    def runningAsAdministrator(self):
        """
        Return True if slave runs as administrator.
        """
        # Windows 2008 and DC client tests are done in administration mode,
        # 2003 and XP under normal mode.
        if 'win-2008' in self.hostname or 'win-dc' in self.hostname:
            return True
        else:
            return False

    def assertCompatError(self, expected_id, actual_error):
        """
        Raise an error if `actual_error` is not a `CompatError` instance.

        Raise an error if `expected_id` does not match event_id of
        `actual_error`.
        """
        if not isinstance(actual_error, CompatError):
            values = (actual_error, type(actual_error))
            message = u'Error %s not CompatError but %s' % values
            raise AssertionError(message.encode('utf-8'))

        actual_id = getattr(actual_error, 'event_id', None)
        if expected_id != actual_id:
            values = (actual_error, str(expected_id), str(actual_id))
            message = u'Error id for %s is not %s, but %s.' % values
            raise AssertionError(message.encode('utf-8'))


class FileSystemTestCase(CompatTestCase):
    """
    Common test case for all file-system tests.
    """

    @classmethod
    def setUpClass(cls):
        # FIXME:924:
        # Disabled when we can not find the home folder path.
        if not process_capabilities.get_home_folder:
            raise cls.skipTest()

        super(FileSystemTestCase, cls).setUpClass()

        cls.os_user = cls.setUpTestUser()

        token = manufacture.makeToken(
            username=cls.os_user.name, password=cls.os_user.password)
        home_folder_path = system_users.getHomeFolder(
            username=cls.os_user.name, token=token)

        cls.avatar = manufacture.makeFilesystemOSAvatar(
            name=cls.os_user.name,
            home_folder_path=home_folder_path,
            token=token,
            )
        cls.filesystem = LocalFilesystem(avatar=cls.avatar)

    @classmethod
    def setUpTestUser(cls):
        """
        Set-up OS user for symbolic link testing.
        """
        # FIXME:2106:
        # Re-use global instance.
        return TestUser(
            name=TEST_ACCOUNT_USERNAME,
            password=TEST_ACCOUNT_PASSWORD
            )

    def setUp(self):
        super(FileSystemTestCase, self).setUp()
        # Initialized only to clean the home folder.
        test_filesystem = LocalTestFilesystem(avatar=self.avatar)
        test_filesystem.cleanHomeFolder()


class OSAccountFileSystemTestCase(FileSystemTestCase):
    """
    Test case for tests that need a local OS account present.
    """

    # User will be created before running the test case and removed on
    # teardown.
    CREATE_TEST_USER = None

    @classmethod
    def setUpTestUser(cls):
        """
        Add `CREATE_TEST_USER` to local OS.
        """
        os_administration.addUser(cls.CREATE_TEST_USER)
        return cls.CREATE_TEST_USER

    @classmethod
    def tearDownClass(cls):
        """
        Remove OS user used for testing.
        """
        os_administration.deleteUser(cls.CREATE_TEST_USER)

        super(OSAccountFileSystemTestCase, cls).tearDownClass()


def setup_access_control(users, groups):
    """
    Create testing environment access control.

    Add users, groups, create temporary folders and other things required
    by the testing system.
    """
    for group in groups:
        os_administration.addGroup(group)

    for user in users:
        os_administration.addUser(user)

    for group in groups:
        os_administration.addUsersToGroup(group, group.members)


def teardown_access_control(users, groups):
    """
    Revert changes from setup_access_control.

    It aggregates all teardown errors and report them at exit.
    """
    # First remove the accounts as groups can not be removed first
    # since they are blocked by accounts.
    errors = []
    for user in users:
        try:
            os_administration.deleteUser(user)
        except Exception, error:
            errors.append(error)

    for group in groups:
        try:
            os_administration.deleteGroup(group)
        except Exception, error:
            errors.append(error)

    if errors:
        raise AssertionError(errors)
