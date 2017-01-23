# Copyright (c) 2011 Adi Roiban.
# See LICENSE for details.
"""
Package with code that helps with testing.

Here are a few import shortcuts.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from future import standard_library

from chevah.empirical.testcase import (
    ChevahTestCase,
    )
from chevah.empirical.mockup import factory

# Update Py3 modules.
standard_library.install_aliases()
# Export to new names.
EmpiricalTestCase = ChevahTestCase
mk = factory
