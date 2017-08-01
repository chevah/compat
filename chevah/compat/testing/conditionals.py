# Copyright (c) 2012 Adi Roiban.
# See LICENSE for details.
"""
Decorators used for testing.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from functools import wraps
from nose import SkipTest
from socket import gethostname
from unittest import TestCase
import sys

from chevah.compat import process_capabilities
from chevah.compat.testing.testcase import ChevahTestCase


def skipOnCondition(callback, message):
    """
    Helper to decorate skip class or methods based on callback results.

    This case is inspired by Python unittest implementation.
    """
    def inner(test_item):
        if not (
            isinstance(test_item, type) and
            issubclass(test_item, TestCase)
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

        return result

    return inner


def onOSFamily(family):
    """
    Run test only if current os is from `family`.
    """
    def check_os_family():
        return process_capabilities.os_family != family.lower()

    return skipOnCondition(
        check_os_family, 'OS family "%s" not available.' % family)


def onOSName(name):
    """
    Run test only if current os is `name` or is in one from `name` list.
    """
    if not isinstance(name, list) and not isinstance(name, tuple):
        name = [name.lower()]
    else:
        name = [item.lower() for item in name]

    def check_os_name():
        return process_capabilities.os_name not in name

    return skipOnCondition(
        check_os_name, 'OS name "%s" not available.' % name)


def onCapability(name, value):
    """
    Run test only if capability with `name` equals `value`.
    """
    capability = getattr(process_capabilities, name)

    def check_capability():
        return capability != value

    return skipOnCondition(
        check_capability, 'Capability "%s" not present.' % name)


def onAdminPrivileges(present):
    """
    Run test only if administrator privileges match the `present` value on
    the machine running the tests.

    For the moment only Windows 2003 and Windows XP build slaves execute the
    tests suite with a regular account.
    """
    hostname = gethostname()
    is_running_as_normal = ChevahTestCase.os_version in ['nt-5.1', 'nt-5.2']

    def check_administrator():
        if present:
            return is_running_as_normal

        return not is_running_as_normal

    return skipOnCondition(
        check_administrator,
        'Administrator privileges not present on "%s".' % (hostname,)
        )


def skipOnPY3():
    """
    Skip tests on Python 3 or Python 2 in forward compatibility.
    """
    return skipOnCondition(
        lambda: sys.flags.py3k_warning,
        'Python 2 only test.',
        )
