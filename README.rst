chevah-compat
=============

.. image:: https://codecov.io/gh/chevah/compat/branch/master/graph/badge.svg
  :target: https://codecov.io/gh/chevah/compat

.. image:: https://github.com/chevah/compat/workflows/ci/badge.svg
  :target: https://github.com/chevah/compat/actions/workflows/ci.yml


Chevah OS Compatibility Layer for Python 3.

Unified interface for working with operating system accounts on Unix
and Windows, see IOSUsers.

The unified interface for working with operating system file systems provides:

* Unicode
* allowing impersonated filesystem access
* allowing chrooted filesystem access
* single internal path separator: always '/'.
* listing root directory (on Windows, '/' lists all available drives,
  while '/c/' lists drive c:)
* setting/getting filesystem node owner/groups
* open files in various modes: read-only, write-only, append.
