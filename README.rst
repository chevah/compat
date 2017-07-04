chevah-compat
=============

.. image:: https://codecov.io/gh/chevah/compat/branch/master/graph/badge.svg
  :target: https://codecov.io/gh/chevah/compat

Chevah OS Compatibility Layer.

Depends on:

* pam - for pam authenticaiton
* arpy - for loading libraries on AIX.


Unified interface for working with operating system accounts on Unix
and Windows, see IOSUsers.

Support for staring Unix daemon and installing and starting Windows services.

Importing this module on Windows will populate the sys.argv with Unicode
values.

Unified interface for working with operating system file systems provides:

* Unicode
* allow impersonated filesystem access
* allow chrooted filesystem access
* single internal path separator: always '/'.
* listing root folder. On Windows '/' will list all
  available drives. '/c/' will list c:\\ content.
* setting/getting filesystem node owner/groups.
* open file in various modes: read-only, write-only, append,
