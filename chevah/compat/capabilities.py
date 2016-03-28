# Copyright (c) 2012 Adi Roiban.
# See LICENSE for details.
"""
Common code for capabilities on all systems.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import os
import sys


def _get_os_name():
    """
    Return os name for current operating system.
    """
    family = sys.platform
    if family.startswith('linux'):
        return 'linux'
    elif family.startswith('win'):
        return 'windows'
    elif family.startswith('aix'):
        return 'aix'
    elif family.startswith('darwin'):
        return 'osx'
    elif family.startswith('sunos'):
        return 'solaris'
    elif family.startswith('hp-ux11'):
        return 'hpux'
    elif family.startswith('openbsd'):
        return 'openbsd'
    elif family.startswith('freebsd'):
        return 'freebsd'
    else:
        raise AssertionError('OS "%s" not supported.' % family)


class BaseProcessCapabilities(object):
    """
    Code shared by all `IProcessCapabilities`
    """

    os_family = os.name
    os_name = _get_os_name()
