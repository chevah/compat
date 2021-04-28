chevah-compat
=============

.. image:: https://codecov.io/gh/chevah/compat/branch/master/graph/badge.svg
  :target: https://codecov.io/gh/chevah/compat

.. image:: https://github.com/chevah/compat/workflows/GitHub-CI/badge.svg
  :target: https://github.com/chevah/compat/actions

.. image:: https://travis-ci.com/chevah/compat.svg?branch=master
  :target: https://travis-ci.com/github/chevah/compat


Chevah OS Compatibility Layer.

Depends on:

* pam - for pam authentication
* arpy - for loading libraries on AIX.

Only Python 2.7 is supported for now.

Unified interface for working with operating system accounts on Unix
and Windows, see IOSUsers.

Support for starting Unix daemons.

Importing this module on Windows populates sys.argv with Unicode values.

The unified interface for working with operating system file systems provides:

* Unicode
* allowing impersonated filesystem access
* allowing chrooted filesystem access
* single internal path separator: always '/'.
* listing root directory (on Windows, '/' lists all available drives,
  while '/c/' lists drive c:)
* setting/getting filesystem node owner/groups
* open files in various modes: read-only, write-only, append.
