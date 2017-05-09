# Copyright (c) 2012 Adi Roiban.
# See LICENSE for details.
'''Common interfaces used by Chevah products.'''
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from zope.interface import Interface, Attribute


class IDaemon(Interface):
    """
    Daemon creates a Unix daemon process.

    To stop the daemon you must send the KILL signal.
    """

    preserve_standard_streams = Attribute(
        """
        True if standard streams (input, output, error) should be redirected
        to the new daemon process.
        """)

    detach_process = Attribute('True if process should detach from console.')

    def __init__(options):
        """
        Initialize with the command line options.
        """

    def launch():
        """
        Start the daemon.
        """

    def onInitialize():
        """
        Called before forking the process.
        """

    def getOpenFiles():
        """
        Return a list with files that should be kept open while starting
        the daemon.
        """

    def onStart():
        """
        Called after forking the process.
        """

    def onStop(exit_code):
        """
        Called before exiting the forked process.
        """


class IProcess(Interface):
    """
    A process represents a running Chevah application.

    It can include a service, a local administration server and other
    utilities that are required by the application.

    The name is somehow misleading as the IProcess can trigger and contain
    multiple OS processes or threads.
    """

    def start():
        """
        Start the process.
        """

    def stop():
        """
        Stops the process.

        Stopping the process will end product execution.
        """

    def configure(configuration_path, configuration_file):
        """
        Configure the process.

        `configuration_path` and `configuration_file` are mutually exclusive
        parameters.
        """


class IProcessCapabilities(Interface):
    """
    Provides information about current process capabilities.
    """

    os_family = Attribute('General family of OS. nt or posix')
    os_name = Attribute(
        'Name of operating system. Ex: windows, linux, aix, solaris.')

    impersonate_local_account = Attribute(
        'True if it can impersonate any local account.')
    create_home_folder = Attribute(
        'True if it can create home folders for any local account.')
    get_home_folder = Attribute(
        'True if it can retrieve home folders for any local account.')
    symbolic_link = Attribute(
        'True if it supports symbolic links.')
    pam = Attribute(
        'True if it supports PAM authentication.')


class IHasImpersonatedAvatar(Interface):
    """
    Avatar which can be impersonated.
    """

    name = Attribute(u'Name/ID of this avatar.')
    token = Attribute(
        '''
        Token obtained after authentication.

        Only used on Windows. This is required for impersonating Windows
        local and active directory accounts.

        This attribute is `None` on Unix systems.
        ''')

    use_impersonation = Attribute(
        u'True if this avatar should be impersonated.')

    def getImpersonationContext():
        """
        Context manager for impersonating operating system functions.
        """


class IFileSystemAvatar(IHasImpersonatedAvatar):
    """
    Avatar for interacting with the filesystem.
    """

    home_folder_path = Attribute(u'Path to home folder')
    root_folder_path = Attribute(u'Path to root folder')
    lock_in_home_folder = Attribute(
        '''
        True if filesystem access should be limited to home folder.
        ''')


class IOSUsers(Interface):
    """
    Non-object oriented methods for retrieving system accounts.
    """

    def getHomeFolder(username, token=None):
        """
        Get home folder for local (or NIS) user.
        """

    def userExists(username):
        """
        Returns `True` if username exists on this system.
        """

    def authenticateWithUsernameAndPassword(username, password):
        """
        Check the username and password against local accounts.

        Returns a tuple of (result, token).
        `result` is `True` if credentials are accepted, False otherwise.
        `token` is None on Unix system and a token handler on Windows.
        """

    def pamWithUsernameAndPassword(username, password, service='login'):
        """
        Check username and password using PAM.

        Returns True if credentials are accepted, False otherwise.
        """

    def dropPrivileges(username):
        """
        Change process privileges to `username`.

        Return `ChangeUserException` if current process has no permissions for
        switching to user.
        """

    def executeAsUser(username, token):
        """
        Returns a context manager for changing current process privileges
        to `username`.

        Return `ChangeUserException` is there are no permissions for
        switching to user.
        """

    def isUserInGroups(username, groups, token):
        """
        Return true if `username` or 'token' is a member of `groups`.
        """

    def getPrimaryGroup(username):
        """
        Return the primary group for username.
        """


class IFilesystemNode(Interface):
    """
    A node from the filesystem.

    It will not allow access ouside of avatar's root folder.
    """
    def __init__(avatar, segments=None):
        """
        It is initialized with an :class:`IFileSystemAvatar` and an optional
        list of `segments`.

        The segments represent the path inside avatar's root folder.
        If segments are None, the avatar's home folder will be used.
        """

    name = Attribute(
        """
        Name of this node.
        """)

    path = Attribute(
        """
        Path inside the rooted filesystem.
        """)

    absolute_path = Attribute(
        """
        Path in the absolute filesystem.
        """)

    def getParent():
        """
        Return the :class:`IPath` for parent.

        Returns `None` is this is the root.
        """

    def getChild(name):
        """
        Return the :class:`IPath` for child with `name`.

        Raise ChildNotFound if child does not exists.
        """

    def getNewChild(name):
        """
        Return the :class:`IPath` for child with `name`.

        Raise ChildAlreadyExists if child exists.
        """

    def getChildren():
        """
        Return the list of all :class:`IPath` children.
        """

    def isRoot():
        """
        True if this node is the root of the avatar's filesystem.
        """

    def isFolder():
        """
        True if node is a folder.
        """

    def isFile():
        """
        True if node is a file.
        """

    def isLink():
        """
        True if node is link.
        """

    def exists():
        """
        True if node exists.
        """

    def makeFolder():
        """
        Create this node as an empty folder.
        """

    def makeFile():
        """
        Create this node as an empty file.

        You can also use :meth:`openForWriting` and :meth:`openForAppending`
        to create a new file.
        """

    def delete(recursive=False):
        """
        Delete this node.

        If node is a folder and `recursive` is `True` it will delete all
        folder content.
        """

    def openForReading():
        """
        Return a file object for reading.
        """

    def openForWriting():
        """
        Return a file object for writing.
        """

    def openForAppending():
        """
        Return a file object for appending.
        """

    def getSize():
        """
        Return the size in bytes.
        """

    # copyTo(segments)
    # renameTo(segments)
    # # Only on Unix
    # def linkTo(segments) linkFrom(segments)
    # def readLink()

    # getAttributes
    # setAttributes

    # getOwner()
    # setOwner()

    # getUsers()
    # addUsers()
    # hasUser()
    # removeUsers()


class ILocalFilesystem(Interface):
    """
    Portable access to local filesystem.

    This is designed to provide a single interface for accessing local files.

    It is initialized by passing an avatar.
    If the avatar root_folder is `None` the filesystem will allow full access.

    It is designed to use `segments` instead of file and folder names.
    Segments are a list of folder names and file name, that represent a path.

    We have two types of paths.
     * Chevah Path
     * Real Path (Operating System Path)

    A Chevah Path is the unified representation of paths across all Chevah
    products. A Chevah Path uses the Posix filesystem conventions.
     * /some/path/ - path to a folder
     * /some/path  - path to a file

    An Operating System Path is the paht used by the operating system, and
    they differ from one os to another.
     * On Unix - /some/path
     * on Windows c:\some\path
    """

    avatar = Attribute('Avatar associated with this filesystem.')
    system_users = Attribute('Module for handling system users `IOSUsers`.')
    home_segments = Attribute('Segments for user home folder.')
    temp_segments = Attribute('Segments to temp folder.')

    def getRealPathFromSegments(segments):
        """
        Return the real path for the segments.
        """

    def getSegmentsFromRealPath(real_path):
        """
        Return the segments corresponding to an real absolute path.
        """

    def getAbsoluteRealPath(real_path):
        """
        Return the absolute real path from `real_path`.

        `real_path` is a path valid in the local operating system.
        """

    def getPath(segments):
        """
        Return the ChevahPath for the segment.

        It always uses the forward slash '/' as a separator.
        """

    def getSegments(path):
        """
        Return the segments from the root path to the passed `path`.

        `path` is a ChevahPath and can be a relative path of the home folder.
        """

    def isFile(segments):
        """
        Return True if segments points to a file.
        """

    def isFolder(segments):
        """
        Return True if segments points to a folder.
        """

    def isLink(segments):
        """
        Return True if segments points to a link.
        """

    def exists(segments):
        """
        Return True if segments points to an existing path.
        """

    def createFolder(segments, recursive):
        """
        Create a folder at the path specified by segments.

        If `recursive` is True it will try to create parent folder.
        If `recursive` is False and parent folder does not exists it will
        raise `OSError`.
        """

    def deleteFolder(segments, recursive):
        """
        Delete the folder at `segments`.
        If `recursive` is True the whole folder and its content will be
        deleted.
        If `resursice` is False and folder is not empty it will raise
        `OSError`.
        """

    def deleteFile(segments):
        """
        Delete the folder at `segments`.
        """

    def rename(from_segments, to_segments):
        """
        Rename file or folder.
        """

    def openFile(segments, flags, mode):
        """
        Return a file object for `segments`.

        `flags` and `mode` are used for os.open function.
        """

    def openFileForReading(segments, utf8=False):
        """
        Return a file object for reading the file.
        """

    def openFileForWriting(segments, utf8=False):
        """
        Return a file object for writing into the file.

        File is created if it does not exist.
        File is truncated if it exists.
        """

    def openFileForUpdating(segments, utf8=False):
        """
        Return a file object for writing into the file.

        File is not created if it does not exist.
        File is not truncated if it exists.
        """

    def openFileForAppending(segments, utf8=False):
        """
        Return a file object for writing at the end a file.

        File is created if it does not exists.
        """

    def getFileSize(segments):
        """
        Return the file size, in bytes.
        """

    def getFolderContent(segments):
        """
        Return a list of files and folders contained by folder.
        """

    def iterateFolderContent(segments):
        """
        Return an iterator for the name of each direct child of folder.
        """

    def getStatus(segments):
        """
        Return a status structure for segments, resolving symbolic
        links, an having the following members:

        st_mode - protection bits,
        st_uid - user id of owner,
        st_gid - group id of owner,
        st_size - size of file, in bytes,
        st_atime - time of most recent access,
        st_mtime - time of most recent content modification,
        """

    def getAttributes(segments):
        """
        Return a list of IFileAttributes for segment.
        """

    def setAttributes(segments, attributes):
        """
        Set `attributes` for segment.

        `attributes` is a dictionary of:
         * size -> s.st_size
         * uid -> s.st_uid
         * gid -> s.st_gid
         * mode -> s.st_mode
         * atime -> int(s.st_atime)
         * mtime -> int(s.st_mtime)
        """

    def readLink(segments):
        """
        Return the value of link at `segments'.
        """

    def makeLink(target_segments, link_segments):
        """
        Create a link at `link_segments` pointing to `target_segments`.
        """

    def setOwner(segments, owner):
        """
        Set file/folder owner.
        """

    def getOwner(segments):
        """
        Get file/folder owner
        """

    def addGroup(segments, group, permissions):
        """
        Add `group` to file/folder at `segments` using `permissions`.

        On Unix it will replace the current group and
        is equivalent to setGroup.
        """

    def removeGroup(segments, group):
        """
        Remove group from file/folder acl.

        On Unix it will only remove the group from extended acl.
        """

    def hasGroup(segments, group):
        """
        Return True if file at `segments` has group in ACL.
        """

    def touch(segments):
        """
        Create a new file at `segments` or update its modified date.
        """

    def copyFile(source_segments, destination_segments, overwrite=False):
        """
        Copy file from `source_segments` to `destination_segments`.

        If `destination_segments` is a folder, the file will be copied at
        `destination_segments/SOURCE_FILENAME`.

        If `destination_segments` already exists and `overwrite` is not `true`,
        copy will fail.
        """


class IFileAttributes(Interface):
    """
    Attributes for file or folder, independent of filesystem.
    """

    name = Attribute('Name of this member.')
    path = Attribute(
        'Absolute path of this member, as seen for the chrooted fs.')
    size = Attribute('Size in bytes.')
    is_file = Attribute('True if member is a file.')
    is_folder = Attribute('True if member is a folder.')
    is_link = Attribute('True if member is a symbolic link.')
    modified = Attribute('Timestamp at which content was last modified.')

    mode = Attribute('Protection bits. Unix specific.')
    hardlinks = Attribute('Number of hard links.')

    uid = Attribute('User ID or owner as integer.')
    gid = Attribute('Group ID as integer.')

    node_id = Attribute('ID inside the filesystem.')
    owner = Attribute('Name of the owner of this path.')
    group = Attribute('Name of the group to which this path is associated.')
