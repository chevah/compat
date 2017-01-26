# -*- coding: utf-8 -*-
# Copyright (c) 2011 Adi Roiban.
# See LICENSE for details.
"""
Package with code that helps with testing.

Here are a few import shortcuts.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from future import standard_library

from chevah.compat import process_capabilities
from chevah.compat.administration import os_administration
from chevah.compat.testing.mockup import (
    mk,
    TestGroup,
    TestUser,
    )
from chevah.compat.testing.testcase import ChevahTestCase

# Update Py3 modules.
standard_library.install_aliases()
# Keep this alias for backward compatibility.
CompatTestCase = ChevahTestCase

# Export them in root package.
mk

# Test accounts and passwords.
TEST_ACCOUNT_USERNAME = unicode(u'mâț mițișor')
TEST_ACCOUNT_PASSWORD = unicode(u'Baroșanu42!')
TEST_ACCOUNT_GROUP = unicode(u'g mâțmițișor')
# FIXME:2106:
# Replace hard-coded constant with posixID()
TEST_ACCOUNT_UID = 2000
TEST_ACCOUNT_GID = 2010
TEST_ACCOUNT_GROUP_WIN = unicode(u'Users')
TEST_ACCOUNT_USERNAME_OTHER = unicode(u'miț motan')
TEST_ACCOUNT_PASSWORD_OTHER = unicode(u'altapara')
# FIXME:2106:
# Replace hard-coded constant with posixID()
TEST_ACCOUNT_UID_OTHER = 2001
TEST_ACCOUNT_GID_OTHER = 2011
TEST_ACCOUNT_GROUP_OTHER = unicode(u'g mițmotan')

# Centrify testing account.
TEST_ACCOUNT_CENTRIFY_USERNAME = unicode(u'centrify-user')
TEST_ACCOUNT_CENTRIFY_PASSWORD = unicode(u'Parola01!')
TEST_ACCOUNT_CENTRIFY_UID = 1363149908

# Another test group to test an user belonging to multiple groups.
TEST_ACCOUNT_GROUP_ANOTHER = u'g-another-test'
# FIXME:2106:
# Replace hard-coded constant with posixID()
TEST_ACCOUNT_GID_ANOTHER = 2012

# Domain controller helpers.
TEST_PDC = unicode(u'\\\\CHEVAH-DC')
TEST_DOMAIN = unicode(u'chevah')
TEST_ACCOUNT_USERNAME_DOMAIN = unicode(u'domain test-user')
TEST_ACCOUNT_PASSWORD_DOMAIN = unicode(u'qwe123QWE')
TEST_ACCOUNT_GROUP_DOMAIN = unicode(u'domain test_group')

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


if process_capabilities.os_name == 'solaris':
    TEST_ACCOUNT_HOME_PATH = u'/export/home/' + TEST_ACCOUNT_USERNAME
    TEST_ACCOUNT_HOME_PATH_OTHER = (
        u'/export/home/' + TEST_ACCOUNT_USERNAME_OTHER)
else:
    TEST_ACCOUNT_HOME_PATH = u'/home/' + TEST_ACCOUNT_USERNAME
    TEST_ACCOUNT_HOME_PATH_OTHER = u'/home/' + TEST_ACCOUNT_USERNAME_OTHER

TEST_USERS = {
    u'normal': TestUser(
        name=TEST_ACCOUNT_USERNAME,
        posix_uid=TEST_ACCOUNT_UID,
        posix_gid=TEST_ACCOUNT_GID,
        primary_group_name=TEST_ACCOUNT_GROUP,
        posix_home_path=TEST_ACCOUNT_HOME_PATH,
        home_group=TEST_ACCOUNT_GROUP,
        password=TEST_ACCOUNT_PASSWORD,
        ),
    u'other': TestUser(
        name=TEST_ACCOUNT_USERNAME_OTHER,
        posix_uid=TEST_ACCOUNT_UID_OTHER,
        posix_gid=TEST_ACCOUNT_GID_OTHER,
        primary_group_name=TEST_ACCOUNT_GROUP_OTHER,
        posix_home_path=TEST_ACCOUNT_HOME_PATH_OTHER,
        password=TEST_ACCOUNT_PASSWORD_OTHER,
        ),
    }

TEST_GROUPS = {
    u'normal': TestGroup(
        name=TEST_ACCOUNT_GROUP,
        posix_gid=TEST_ACCOUNT_GID,
        members=[TEST_ACCOUNT_USERNAME, TEST_ACCOUNT_USERNAME_OTHER],
        ),
    u'other': TestGroup(
        name=TEST_ACCOUNT_GROUP_OTHER,
        posix_gid=TEST_ACCOUNT_GID_OTHER,
        members=[TEST_ACCOUNT_USERNAME_OTHER],
        ),
    u'another': TestGroup(
        name=TEST_ACCOUNT_GROUP_ANOTHER,
        posix_gid=TEST_ACCOUNT_GID_ANOTHER,
        members=[TEST_ACCOUNT_USERNAME],
        ),
    }


def setup_access_control(users, groups):
    """
    Create testing environment access control.

    Add users, groups, create temporary folders and other things required
    by the testing system.
    """
    for group in groups.values():
        os_administration.addGroup(group)

    for user in users.values():
        os_administration.addUser(user)

    for group in groups.values():
        os_administration.addUsersToGroup(group, group.members)


def teardown_access_control(users, groups):
    """
    Revert changes from setup_access_control.

    It aggregates all teardown errors and report them at exit.
    """
    # First remove the accounts as groups can not be removed first
    # since they are blocked by accounts.
    errors = []
    for user in users.values():
        try:
            os_administration.deleteUser(user)
        except Exception as error:
            errors.append(error)

    for group in groups.values():
        try:
            os_administration.deleteGroup(group)
        except Exception as error:
            errors.append(error)

    if errors:
        raise AssertionError(errors)
