Release notes for chevah.compat
===============================


0.20.0 - 14/05/2014
-------------------

* Unify errors for file operations on folder and for folder operations on
  files.


0.19.1 - 06/05/2014
-------------------

* Report errors when removing test user's home folder and raise an exception.
* Cache Windows user token value.
* Security fix: getHomeFolder called with an invalid username/token
  combination.


0.19.0 - 17/04/2014
-------------------

* Fix domain test account's home folder removal.
* Fix creating symbolic links on Windows when impersonating.
* Separate Windows OS administration helpers.
* Add support for granting/revoking user rights/privileges on Windows for the
  testing infrastructure.


0.18.1 - 24/03/2014
-------------------

* LocalFilesystem.exists() now returns false on Windows for broken links.


0.18.0 - 24/03/2014
-------------------

* Raise CompatError in getSegmentsFromRealPath if path is outside of home
  folder.


0.17.1 - 20/03/2014
-------------------

* Update build system to latest buildbot.
* Convert WindowsError from deleteFile into OSError and convert error code
  for file not found.


0.17.0 - 04/03/2014
-------------------

* Add support for reading symbolic links on Windows.


0.16.0 - 04/03/2014
-------------------

* Add support for creating symbolic links on Windows.


0.15.0 - 04/03/2014
-------------------

* Add support for detecting symbolic link capabilities.


0.14.0 - 04/03/2014
-------------------

* Refactor file/folder/link attributes retrieval.
* Add 'link' and 'file' attributes to LocalFilesystem.getAttributes().
* Remove follow_symlinks from LocalFilesystem.getAttributes().
* Add LocalFilesystem.getStatus() method.


0.13.5 - 04/03/2014
-------------------

* Use latest brink and linters.
* Fix cleanup on account administration on AIX and OSX.


0.13.4 - 13/01/2014
-------------------

* Fix getSegmentsFromRealPath on Windows.


0.13.3 - 13/01/2014
-------------------

* Fix ILocalFilesystem.openFile declaration.


0.13.2 - 13/01/2014
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
