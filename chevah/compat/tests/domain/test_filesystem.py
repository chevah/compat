# Copyright (c) 2010 Adi Roiban.
# See LICENSE for details.
"""
Tests for portable filesystem access.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import win32security


from chevah.compat.testing import (
    mk,
    TEST_ACCOUNT_GROUP,
    TEST_DOMAIN,
    TEST_PDC,
    TestUser,
    )

from chevah.compat.testing.testcase import OSAccountFileSystemTestCase
from chevah.compat.tests.mixin.filesystem import SymbolicLinksMixin


class TestSymbolicLink(OSAccountFileSystemTestCase, SymbolicLinksMixin):
    """
    Unit tests for `makeLink` for domain level accounts.

    User requires SE_CREATE_SYMBOLIC_LINK privilege on Windows OSes
    in order to be able to create symbolic links.

    We are using a custom user for which we make sure the right is present
    for these tests.
    """

    CREATE_TEST_USER = TestUser(
        name=mk.string(),
        password=mk.string(),
        domain=TEST_DOMAIN,
        pdc=TEST_PDC,
        home_group=TEST_ACCOUNT_GROUP,
        posix_uid=mk.posixID(),
        posix_gid=mk.posixID(),
        create_local_profile=True,
        windows_required_rights=(win32security.SE_CREATE_SYMBOLIC_LINK_NAME,),
        )
