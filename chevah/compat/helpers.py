# Copyright (c) 2012 Adi Roiban.
# See LICENSE for details.
"""
Any methods from here is a sign of bad design.
"""

from chevah.compat.exceptions import (
    CompatError,
    )


def _(string):
    '''Placeholder for future gettext integration.'''
    return string


class NoOpContext(object):
    """
    A context manager that does nothing.
    """

    def __enter__(self):
        '''Do nothing.'''
        return self

    def __exit__(self, exc_type, exc_value, tb):
        '''Just propagate errors.'''
        return False


def raise_failed_to_add_group(group, path, message=u''):
    '''Helper for raising the exception from a single place.'''
    raise CompatError(1017,
        _(u'Failed to add group "%s" for "%s". %s' % (
            group, path, message)))


def raise_failed_to_get_home_folder(username, text):
    '''Helper for raising the exception from a single place.'''
    raise CompatError(1014,
        _(u'Could not get home folder for user "%s". %s' % (
            username, text)))


def raise_failed_to_get_primary_group(username):
    '''Helper for raising the exception from a single place.'''
    raise CompatError(1015, _(
        u'Failed to get primary group for user "%s"' % (username)))


def raise_failed_to_set_owner(owner, path, message=u''):
    '''Helper for raising the exception from a single place.'''
    raise CompatError(1016,
        _(u'Failed to set owner to "%s" for "%s". %s' % (
            owner, path, message)))
