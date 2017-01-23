# Copyright (c) 2012 Adi Roiban.
# See LICENSE for details.
"""
Decorators used for testing.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from nose import SkipTest
from functools import wraps
from unittest import TestCase

from chevah.compat import process_capabilities


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
