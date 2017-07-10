Chevah Compat Development Guide
===============================


Remote test
-----------

You should specify the builder name to run the tests::

    $ ./paver.sh test_remote ubuntu-1204-32 --wait SOME_TEST

You can trigger a remote session by using this code instead of the regular
`import pdb; pdb.set_trace`::

    from chevah.compat.testing import rt
    rt()

By default it will listen on port 9999 and you can connect using telnet.
You will need access to the VPN as you will connect directly to the slave.



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
