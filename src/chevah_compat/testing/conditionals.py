# Copyright (c) 2012 Adi Roiban.
# See LICENSE for details.
"""
Decorators used for testing.
"""

from functools import wraps
from socket import gethostname
from unittest import TestCase

from nose import SkipTest

from chevah_compat import process_capabilities
from chevah_compat.testing.testcase import ChevahTestCase

_SUPPORTED_OS_FAMILIES = ['posix', 'nt']

_SUPPORTED_OS_NAMES = ['linux', 'windows', 'aix', 'osx']


def skipOnCondition(callback, message):
    """
    Helper to decorate skip class or methods based on callback results.

    This case is inspired by Python unittest implementation.
    """

    def inner(test_item):
        if not (
            isinstance(test_item, type) and issubclass(test_item, TestCase)
        ):
            # Only raise SkipTest in methods.
            @wraps(test_item)
            def wrapper(*args, **kwargs):
                if callback():
                    raise SkipTest(message)
                return test_item(*args, **kwargs)

            result = wrapper
        else:
            result = test_item

        if callback():
            result.__unittest_skip__ = True
            result.__unittest_skip_why__ = message
        else:
            already_skipped = getattr(result, '__unittest_skip__', False)
            if not already_skipped:
                result.__unittest_skip__ = False

        return result

    return inner


def onOSFamily(family):
    """
    Run test only if current os is from `family`.
    """
    if family not in _SUPPORTED_OS_FAMILIES:
        raise AssertionError(f'Unknow os family: {family}')

    def check_os_family():
        return process_capabilities.os_family != family

    return skipOnCondition(
        check_os_family,
        f'OS family "{family}" not available.',
    )


def onOSName(name):
    """
    Run test only if current os is `name` or is in one from `name` list.
    """
    if not isinstance(name, list) and not isinstance(name, tuple):
        name = [name.lower()]
    else:
        name = [item.lower() for item in name]

    for os_name in name:
        if os_name not in _SUPPORTED_OS_NAMES:
            raise AssertionError(f'Unknow os name: {os_name}')

    def check_os_name():
        return process_capabilities.os_name not in name

    return skipOnCondition(check_os_name, f'OS name "{name}" not available.')


def onCapability(name, value):
    """
    Run test only if capability with `name` equals `value`.
    """
    capability = getattr(process_capabilities, name)

    def check_capability():
        return capability != value

    return skipOnCondition(
        check_capability,
        f'Capability "{name}" not present.',
    )


def onAdminPrivileges(present):
    """
    Run test only if administrator privileges match the `present` value on
    the machine running the tests.

    Only valid on Windows.

    For the moment only Windows 2003 and Windows XP build slaves execute the
    tests suite with a regular account.

    Only local or buildbot runs have all the admin privileges setup.
    """
    hostname = gethostname()
    is_running_as_normal = (
        ChevahTestCase.os_family != 'nt'
        or ChevahTestCase.os_version in ['nt-5.1', 'nt-5.2']
        or ChevahTestCase.TEST_LANGUAGE == 'FR'
        or ChevahTestCase.ci_name
        not in [
            ChevahTestCase.CI.LOCAL,
            ChevahTestCase.CI.BUILDBOT,
            ChevahTestCase.CI.GITHUB,
        ]
    )

    def is_normal_user():
        if present:
            return is_running_as_normal

        return not is_running_as_normal

    return skipOnCondition(
        is_normal_user,
        f'Administrator privileges not present on "{hostname}".',
    )
