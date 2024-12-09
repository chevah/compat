# Copyright (c) 2024 Adi Roiban.
# See LICENSE for details.
"""
Fixtures for pytest run mode.
"""

import pytest

from chevah_compat.tests.elevated import setup_package, teardown_package


@pytest.fixture(scope='session', autouse=True)
def setup_package_elevated_pytest():
    """
    Just wraps pynose elevated package setup to pytest fixtures.

    Mare sure the name does not start with `pytest` as this is reserved
    for the pytest framework.
    """
    setup_package()
    yield
    teardown_package()
