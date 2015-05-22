# Copyright (c) 2010 Adi Roiban.
# See LICENSE for details.
# The names from this module as a bit against the rules.
"""
Code for portable functions.
"""
from __future__ import with_statement
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import os
import sys

if os.name == 'posix':
    from chevah.compat.unix_users import (
        UnixDefaultAvatar,
        UnixHasImpersonatedAvatar,
        UnixUsers,
        UnixSuperAvatar,
        )
    from chevah.compat.unix_capabilities import (
        UnixProcessCapabilities,
        )
    from chevah.compat.unix_filesystem import UnixFilesystem

    system_users = UnixUsers()
    process_capabilities = UnixProcessCapabilities()
    LocalFilesystem = UnixFilesystem
    HasImpersonatedAvatar = UnixHasImpersonatedAvatar
    DefaultAvatar = UnixDefaultAvatar
    SuperAvatar = UnixSuperAvatar

elif os.name == 'nt':

    from chevah.compat.nt_users import (
        NTDefaultAvatar,
        NTHasImpersonatedAvatar,
        NTUsers,
        NTSuperAvatar,
        )
    from chevah.compat.nt_capabilities import NTProcessCapabilities
    from chevah.compat.nt_filesystem import NTFilesystem
    from chevah.compat.nt_unicode_argv import get_unicode_argv

    system_users = NTUsers()
    process_capabilities = NTProcessCapabilities()
    LocalFilesystem = NTFilesystem
    HasImpersonatedAvatar = NTHasImpersonatedAvatar
    DefaultAvatar = NTDefaultAvatar
    SuperAvatar = NTSuperAvatar

    # Path Unicode sys.argv on Windows.
    sys.argv = get_unicode_argv()

else:
    raise AssertionError('Operating system "%s" not supported.' % (os.name))

from chevah.compat.posix_filesystem import FileAttributes  # noqa
# Silence the linter
FileAttributes

local_filesystem = LocalFilesystem(avatar=DefaultAvatar())
