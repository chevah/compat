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


PAM
---

PAM test requires the chevah-pam-test PAM module to be enabled.

Create a file `/etc/pam.d/chevah-pam-test` with the following content::

    auth sufficient /srv/buildslave/pam_chevah_test.so
    account sufficient /srv/buildslave/pam_chevah_test.so

Build the `pam_chevah_test.so` with the code from:
https://github.com/chevah/simple-pam/tree/chevah-pam-test

The accepted credentials are: pam_user/test-pass.
`pam_user` account should be auto-created by the test runner.


TODO
----

* handler node permissions and attributes
* handler node content - write, read, copy or move file data
