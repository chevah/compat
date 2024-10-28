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
    if family.startswith('win'):
        return 'windows'
    if family.startswith('aix'):
        return 'aix'
    if family.startswith('darwin'):
        return 'osx'
    if family.startswith('sunos'):
        return 'solaris'
    if family.startswith('hp-ux11'):
        return 'hpux'
    if family.startswith('openbsd'):
        return 'openbsd'
    if family.startswith('freebsd'):
        return 'freebsd'
    raise AssertionError(f'OS "{family}" not supported.')


def _get_cpu_type():
    """
    Return the CPU type as used in the brink.sh script.
    """
    base = platform.processor()

    if not base:
        base = platform.machine()

    if base == 'aarch64':  # pragma: no cover
        return 'arm64'

    if base == 'x86_64':
        return 'x64'

    if base == 'i686':
        return 'x86'

    return base


class BaseProcessCapabilities:
    """
    Code shared by all `IProcessCapabilities`
    """

    os_family = os.name
    os_name = _get_os_name()
    cpu_type = _get_cpu_type()
