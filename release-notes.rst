Release notes for chevah.compat
===============================


0.55.4 - 22/08/2019
-------------------

* Update for short os names in brink.


0.55.3 - 21/08/2019
-------------------

* Fix py3 exception in nose_runner script.


0.55.2 - 21/08/2019
-------------------

* Remove support for `Contains`.
* Fix print function in nose_runner script.


0.55.1 - 17/06/2019
-------------------

* system_users.userExist now raised a CompatError when it fails to check the
  existence of an user.


0.55.0 - 12/05/2019
-------------------

* Updated testing text generator to include upper and lower characters.


0.54.1 - 08/05/2019
-------------------

* Remove TODOs for Solaris/AIX/HPUX as there is no plan to fix them.
* Fix test case teardown.


0.54.0 - 15/04/2019
-------------------

* Fix reactor debug mode.
* Fix assertEqual str vs unicode check.


0.53.0 - 03/04/2019
-------------------

* Fix command line argument parsing when using multiprocessiong.


0.52.5 - 26/03/2019
-------------------

* Fix previous base version on Chevah PyPi.


0.52.4 - 24/03/2019
-------------------

* getHomeFolder now always returns a path without the trailing separater.
* Update Twisted reactor cleanup code to show the tasks from the queue.


0.52.3 - 04/10/2018
-------------------

* Use same modified date on Windows for folder iteration as with getAttributes.


0.52.2 - 04/10/2018
-------------------

* Virtual folders always shadow the real folders.


0.52.1 - 03/10/2018
-------------------

* Don't follow links when getting the attributes for iterated folder.
* Use impersonation when getting the attributes during the folder iteration.


0.52.0 - 03/10/2018
-------------------

* Return attributes in folder iterator.


0.51.1 - 20/09/2018
-------------------

* Add path to more OSError raised on Windows.


0.51.0 - 19/09/2018
-------------------

* When opening a file, if the OS error has no associated path, add the path
  the the exception.


0.50.6 - 26/06/2018
-------------------

* Use start of current year for date of virtual folders.


0.50.5 - 22/06/2018
-------------------

* Fix detection of virtual path for nested virtual paths.
* Add macOS on the list of case-insensitive path handling.


0.50.4 - 21/06/2018
-------------------

* Disable the filesystem overlay functionality. You can no longer mix virtual
  with non-virtual paths.
* The LocalFilesystem now fails to initialized if a virtual path overlaps an
  existing folder.
* Operation will fail if they are executed on a path which looks like a virtual
  path but has no direct mapping.
* Add case insensitive behaviour for Windows.


0.50.3 - 17/06/2018
-------------------

* Fix getAttributes and getStatus operations for root segments.


0.50.2 - 16/06/2018
-------------------

* Restrict any mutating operation on the virtual path itself or for parts
  of the virtual path.
* Fix listing of deep virtual path which are not overlaid.


0.50.1 - 15/06/2018
-------------------

* Fix listing of virtual path which are overlaid
* Fix folder iteration with unicode.


0.50.0 - 15/06/2018
-------------------

* Add support for virtual directories as a way to allow explicit access to
  selected folders outside of the locked home folder.
* Fix skipOnCondition to run the tests when condition is meet.


0.49.3 - 08/05/2018
-------------------

* Fix ILocalFilesystem.getSegmentsFromRealPath on Windows when dealing with
  long UNC paths for locked filesystems.
  In previous releases a long UNC was erroneously considered outside of the
  base path.


0.49.2 - 02/05/2018
-------------------

* ILocalFilesystem.getAttributes on Windows raise an error for broken links
  and return the size and modified date of the linked file.


0.49.1 - 02/05/2018
-------------------

* ILocalFilesystem.exist no longer follows links.


0.49.0 - 30/04/2018
-------------------

* Add support for working with UNC paths and symbolic links to Windows shares.


0.48.0 - 15/04/2018
-------------------

* Raise OSError when trying to set permissions on Windows,
  instead of AttributeError.
  This should have a behaviour closer to Unix.


0.47.0 - 08/03/2018
-------------------

* Iterate the reactor with a timeout and not with None.
  When iterating with None we have observed that not all tasks are executed
  by the reactor, especially closing the connections.
* Add helper functions to create temporary file and folders with auto cleanup.
* Add helpers for spinning the reactor in various conditions.


0.46.0 - 19/12/2017
-------------------

* Add option to ignore thread names during the tearDown of ChevahTestCase.


0.45.2 - 08/11/2017
-------------------

* Fix getAttributes for broken link on Windows to return file not found.


0.45.1 - 27/10/2017
-------------------

* Add removed methods in 0.45.0.


0.45.0 - 27/10/2017
-------------------

* Remove usage of future and use six.


0.44.4 - 24/09/2017
-------------------

* Fix cleanup to call the cleanups in reverse order which they were added.


0.44.3 - 06/08/2017
-------------------

* Update MD5 checksum to match the changes in getFileMD5Sum.


0.44.2 - 06/08/2017
-------------------

* Bump version due to strange behaviour of buildslaves.


0.44.1 - 06/08/2017
-------------------

* Better version reporting for AIX.
* Update the build system for Alpine and to work better with `test_remote`.
* Use hexdigest in getFileMD5Sum.


0.44.0 - 01/08/2017
-------------------

* Remove port listening helpers.
* Update to latest Solaris on 32bit.
* Add support for OS detection in test case and no longer use hostname
  to detect the OS.


0.43.3 - 08/05/2017
-------------------

* Initialize the test case with a non-Unicode drop user name.


0.43.2 - 05/05/2017
-------------------

* Fix OpenBSD/FreeBSD password authentication.


0.43.1 - 04/05/2017
-------------------

* Fix bad shadow change in previous release.


0.43.0 - 04/05/2017
-------------------

* Fix assertIsNotEmpty with deep Unicode data.
* Add minimal support for OpenBSD and FreeBSD.


0.42.1 - 01/05/2017
-------------------

* Fix assertion in chevah testcase.


0.42.0 - 01/05/2017
-------------------

* Remove HTTP context test helper.
* Add iterator for getting the members of a folder.


0.41.1 - 21/02/2017
-------------------

* Fix cleanup code to not fail if a delayed called was already canceled.


0.41.0 - 09/02/2017
-------------------

* The default timeout used to wait for a deferred is now defined by the test
  class instance.


0.40.0 - 27/01/2017
-------------------

* Fix the mess created in 0.37.0 where compat as also installing
  the chevah.empirical namespace and conflicting with the empirical package.


0.39.0 - 27/01/2017
-------------------

* Impersonating local accounts is determined by the availability of
  SeImpersonatePrivilege on Windows.


0.38.0 - 24/01/2017
-------------------

* Add conditional for skipping tests depending on availability of
  administrator privileges
* Update empirical to the latest version


0.37.0 - 23/01/2017
-------------------

* Move chevah.empirical to compat.


0.36.0 - 13/11/2016
-------------------

* Add API for opening a file in write mode for updating. With seek enabled and
  without truncation.


0.35.0 - 17/05/2016
-------------------

* Fix getStatus on Windows to support files that are kept open by other
  processes.


0.34.0 - 18/10/2015
-------------------

* Add dedicated PAM method to authenticate based on username and password.


0.33.0 - 24/11/2015
-------------------

* Fix checking password stored in /etc/passwd in AIX.


0.32.0 - 24/11/2015
-------------------

* Remove dependencies from setup.py as we have POSIX only deps which fail on
  Windows.


0.31.2 - 17/11/2015
-------------------

* Remove dependencies from setup.py as we have POSIX only deps which fail on
  Windows.


0.31.1 - 17/11/2015
-------------------

* Refactor group impersonation to use initgroups() rather than
  getgroups/setgroups.


0.31.0 - 08/10/2015
-------------------

* Add node_id, owner and group to IFileAttributes.
* Add comparison between IFileAttributes.


0.30.1 - 22/05/2015
-------------------

* Fix userExists on Unix to not read /etc/passwd as root.


0.30.0 - 26/04/2015
-------------------

* Initial code update for Python 3 support.


0.29.0 - 17/04/2015
-------------------

* Populate sys.argv with Unicode values on Windows.


0.28.1 - 11/03/2015
-------------------

* Add support for HP-UX in OS administration.
* Disable PAM support for HP-UX.


0.28.0 - 17/02/2015
-------------------

* Update support for HP-UX.


0.27.1 - 15/02/2015
-------------------

* Record dependencies in setup.py.


0.27.0 - 15/02/2015
-------------------

* Remove twisted as a dependency.


0.26.0 - 02/12/2014
-------------------

* Add `touch` and `copyFile` method to Filesystem.


0.25.2 - 13/11/2014
-------------------

* Fix deleteFile on Windows to delete files which are read-only.


0.25.1 - 29/10/2014
-------------------

* Fix deleteFolder(recursive) on Windows to delete files which are read-only.


0.25.0 - 04/10/2014
-------------------

* Update Unix daemon to use instance variables for detach_process and
  preserve_standard_streams.


0.24.0 - 04/10/2014
-------------------

* Update to support OS X again.


0.23.1 - 29/09/2014
-------------------

* Fix setting GID for file replace operation in OS administration.


0.23.0 - 27/09/2014
-------------------

* Refactor getAttributes to return a IFileAttributes object, instead of a
  tuple.
* getAttributes no longer allow filtering attributes. All attributes are
  populated in the returned object.


0.22.0 - 04/07/2014
-------------------

* Re-enable support for Solaris 10.


0.21.2 - 29/05/2014
-------------------

* Fix getFolderContent to raise ENOENT when folder does not exists on windows.
* Rename manufacture to mk.


0.21.1 - 22/05/2014
-------------------

* getTestUser returns None if the user is not found (undefined),
* Treat error.filename as an optional attribute of WindowsError.


0.21.0 - 19/05/2014
-------------------

* Remove test user home folders only when necessary.


0.20.2 - 14/05/2014
-------------------

* Force converted IOError to OSError to have text encoded as UTF-8.


0.20.1 - 14/05/2014
-------------------

* Fix conversion of IOError to OSError.


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
