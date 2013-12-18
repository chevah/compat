chevah-compat
=============

Chevah OS Compatibility Layer.

Depends on:

* chevah.empirical - for testing
* pam - for pam authenticaiton
* arpy - for loading libraries on AIX.


Unified interface for working with operating system accounts on Unix
and Windows, see IOSUsers.

Support for staring Unix daemon and installing and starting Windows services.

Unified interface for working with operating system file systems provides:

* Unicode
* allow impersonated filesystem access
* allow chrooted filesystem access
* single internal path separator: always '/'.
* listing root folder. On Windows '/' will list all
  available drives. '/c/' will list c:\\ content.
* setting/getting filesystem node owner/groups.
* open file in various modes: read-only, write-only, append,


TODO
----

* handler node permissions and attributes
* handler node content - write, read, copy or move file data
