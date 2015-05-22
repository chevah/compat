# Copyright (c) 2013 Adi Roiban.
# See LICENSE for details.
"""
Constants for the compatibility layer.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

# Combine with another CSIDL to force the creation of the associated folder
# if it does not exist.
# See:
# http://msdn.microsoft.com/library/windows/desktop/bb762494%28v=vs.85%29.aspx
CSIDL_FLAG_CREATE = 0x8000

DEFAULT_FILE_MODE = 0o666
DEFAULT_FOLDER_MODE = 0o777

WINDOWS_PRIMARY_GROUP = u'Users'
