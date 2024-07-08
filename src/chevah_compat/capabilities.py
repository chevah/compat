# Copyright (c) 2012 Adi Roiban.
# See LICENSE for details.
"""
Common code for capabilities on all systems.
"""

import os
import platform
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


def _get_cpu_type():
    """
    Return the CPU type as used in the brink.sh script.
    """
    base = platform.processor()

    if not base:
        base = platform.machine()

    if base == 'aarch64':  # noqa:cover
        return 'arm64'

    if base == 'x86_64':
        return 'x64'

    if base == 'i686':
        return 'x86'

    return base


class BaseProcessCapabilities(object):
    """
    Code shared by all `IProcessCapabilities`
    """

    os_family = os.name
    os_name = _get_os_name()
    cpu_type = _get_cpu_type()
