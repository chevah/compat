# Copyright (c) 2010 Adi Roiban.
# See LICENSE for details.
"""
Tests for portable filesystem access.
"""
from chevah.compat.testing import (
    manufacture,
    TEST_ACCOUNT_GID,
    TEST_ACCOUNT_GROUP,
    TEST_DOMAIN,
    TEST_PDC,
    TestUser,
    )

from chevah.compat.administration import os_administration
from chevah.compat.testing import FileSystemTestCase
from chevah.compat.tests.mixin.filesystem import (
    SymbolicLinksMixin,
    SymbolicLinkTestCaseMixin,
    )


class SymbolicLinkTestCase(FileSystemTestCase, SymbolicLinkTestCaseMixin):
    """
    Common test case for symbolic link(s) tests.
    """

    @classmethod
    def setUpTestUser(cls):
        """
        Set-up OS user for symbolic link testing.

        User requires SE_CREATE_SYMBOLIC_LINK privilege on Windows OSes
        in order to be able to create symbolic links.

        We are using a custom user for which we make sure the right is present
        for these tests.
        """
        if cls.os_family != 'nt':
            raise AssertionError('Only Windows DC clients supported.')

        import win32security
        rights = (win32security.SE_CREATE_SYMBOLIC_LINK_NAME,)

        username = manufacture.string()
        user = TestUser(
            name=username,
            password=manufacture.string(),
            domain=TEST_DOMAIN,
            pdc=TEST_PDC,
            home_group=TEST_ACCOUNT_GROUP,
            home_path=u'/home/%s' % username,
            posix_uid=3000 + manufacture.number(),
            posix_gid=TEST_ACCOUNT_GID,
            create_profile=True,
            windows_required_rights=rights,
            )

        os_administration.addUser(user)

        return user


class TestSymbolicLink(SymbolicLinkTestCase, SymbolicLinksMixin):
    """
    Unit tests for `makeLink` for domain level accounts.
    """
