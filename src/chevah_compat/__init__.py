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

if os.name == 'posix':
    from chevah_compat.unix_users import (
        UnixDefaultAvatar,
        UnixHasImpersonatedAvatar,
        UnixUsers,
        UnixSuperAvatar,
    )
    from chevah_compat.unix_capabilities import UnixProcessCapabilities
    from chevah_compat.unix_filesystem import UnixFilesystem

    system_users = UnixUsers()
    process_capabilities = UnixProcessCapabilities()
    LocalFilesystem = UnixFilesystem
    HasImpersonatedAvatar = UnixHasImpersonatedAvatar
    DefaultAvatar = UnixDefaultAvatar
    SuperAvatar = UnixSuperAvatar

    # Unconditionally allow cryptography 3.2.1 with OpenSSL 1.0.2.
    os.environ['CRYPTOGRAPHY_ALLOW_OPENSSL_102'] = 'yes'

elif os.name == 'nt':
    from chevah_compat.nt_users import (
        NTDefaultAvatar,
        NTHasImpersonatedAvatar,
        NTUsers,
        NTSuperAvatar,
    )
    from chevah_compat.nt_capabilities import NTProcessCapabilities
    from chevah_compat.nt_filesystem import NTFilesystem

    system_users = NTUsers()
    process_capabilities = NTProcessCapabilities()
    LocalFilesystem = NTFilesystem
    HasImpersonatedAvatar = NTHasImpersonatedAvatar
    DefaultAvatar = NTDefaultAvatar
    SuperAvatar = NTSuperAvatar
else:
    raise AssertionError('Operating system "%s" not supported.' % (os.name))

from chevah_compat.posix_filesystem import FileAttributes  # noqa

# Silence the linter
FileAttributes

local_filesystem = LocalFilesystem(avatar=DefaultAvatar())
