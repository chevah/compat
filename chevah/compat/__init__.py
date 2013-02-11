# Copyright (c) 2010 Adi Roiban.
# See LICENSE for details.
# The names from this module as a bit against the rules.
'''
Code for portable functions.
'''
from __future__ import with_statement

__metaclass__ = type

__all__ = []

import os

if os.name == 'posix':
    from chevah.compat.unix_users import (
        UnixDefaultAvatar,
        UnixHasImpersonatedAvatar,
        UnixUsers,
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

elif os.name == 'nt':

    from chevah.compat.nt_users import (
        NTDefaultAvatar,
        NTHasImpersonatedAvatar,
        NTUsers,
        )
    from chevah.compat.nt_filesystem import NTFilesystem

    system_users = NTUsers()
    LocalFilesystem = NTFilesystem
    process_capabilities = NTFilesystem.process_capabilities
    HasImpersonatedAvatar = NTHasImpersonatedAvatar
    DefaultAvatar = NTDefaultAvatar

else:
    raise AssertionError('Operating system "%s" not supported.' % (os.name))

local_filesystem = LocalFilesystem(avatar=DefaultAvatar())
