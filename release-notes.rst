Release notes for chevah.empirical
==================================


0.13.2 - 18/12/2013
-------------------

* Fix getSegmentsFromRealPath for locked filesystems.


0.13.1 - 18/12/2013
-------------------

* Update to latest empirical.


0.13.0 - 16/12/2013
-------------------

* Add os_type and os_family to process_capabilies.


0.12.3 - 10/12/2013
-------------------

* Move TEST_ACCOUNT_USERNAME_TEMP to server as it is only used there.
* Fix creation of accounts with default primary group.
* Don't stop to teardown users and groups on first error.


0.12.2 - 10/12/2013
-------------------

* Fix folder mask on AIX.


0.12.1 - 09/12/2013
-------------------

* Use lazy loading of pam module do mitigate the side effects generated when
  load pam library on AIX.


0.12.0 - 09/12/2013
-------------------

* Move os access control setup/teardown from empirical into compat.
* Fix support for AIX system.


0.11.0 - 01/12/2013
-------------------

* Upgrade to unique temporary folders based on latest empirical.
* Fix temporary segments for impersonated accounts.


0.10.6 - 17/09/2013
-------------------

* Wait 100 seconds for account creation.
* Wait 100 seconds for group creation.


0.10.5 - 17/09/2013
-------------------

* Wait 30 seconds 2nd API call for getting a group.


0.10.4 - 17/09/2013
-------------------

* Wait 10 seconds 2nd API call for getting a group.


0.10.3 - 17/09/2013
-------------------

* Wait 5 seconds for 2nd API call for getting a group.


0.10.2 - 16/09/2013
-------------------

* Try 2 different API calls to wait for group creation.


0.10.1 - 23/09/2013
-------------------

* Sync 0.9.2 with latest changes from 0.10.0.


0.9.2 - 04/08/2013
------------------

* Wait 10 seconds for account creation.


0.9.1 - 04/08/2013
------------------

* Ignore KeyError exception when waiting for account creation.
