# Copyright (c) 2012 Adi Roiban.
# See LICENSE for details.
'''Common interfaces used by Chevah products.'''

from zope.interface import Interface, Attribute


class IDaemon(Interface):
    '''Daemon creates a unix daemon process.

    To stop the damone you must send the KILL signal. No dedicated method
    is available for stoping the daemon itself.
    '''

    def __init__(options):
        '''Initialize the set command line options.'''

    def initialize():
        '''Initialize the process.'''

    def launch(self):
        '''Start the daemon.'''

    def start(self):
        '''Start the process.'''

    def stop():
        '''Stop the process.'''


class IProcess(Interface):
    '''A process represent a running Chevah application.

    It can include a service, a local administration server and other
    utilities that are required by the application.

    The name is somehow misleading as the IProcees can trigger and contain
    multiple OS processes or threads.
    '''

    server_class = Attribute('Class user for launching main server process.')
    configuration_class = Attribute(
        'Class user for configuring the process.')

    def start():
        '''Start the process.'''

    def stop():
        '''Stops the process.

        Stopping the process will end product exection.
        '''

    def configure(configuration_path, configuration_file):
        '''Configure the process.

        `configuration_path` and `configuration_file` are mutualy exclusive
        parameters.
        '''

    def logProcessStart():
        '''Log the product starting event.'''

    def logProcessStop():
        '''Log the propduct stopping event.'''

    def logListenError(error):
        '''Log the error of listening for incomming connections.'''


class IProcessCapabilities(Interface):
    '''Provides information about current process capabilites.'''

    impersonate_local_account = Attribute(
        'True if it can impersoante any local account.')
    create_home_folder = Attribute(
        'True if it can create home folders for any local account.')
    get_home_folder = Attribute(
        'True if it can retrieve home folders for any local account.')


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
        u'True if this avatar should be impersoanted.')

    def getImpersonationContext():
        """
        Context manager for impersonating operating system functions.
        """


class IAvatarBase(IHasImpersonatedAvatar):
    """
    Base Avatar for all Chevah services.

    This avatar will be used by various adaptors to make it usable for each
    service.

    It should store all user configuration options.
    """

    name = Attribute(u'Name/ID of this avatar.')
    peer = Attribute(u'The remote peer associated to this avatar.')

    home_folder_path = Attribute(u'Path to home folder')
    root_folder_path = Attribute(u'Path to root folder')
    lock_in_home_folder = Attribute(
        '''
        True if filesystem access should be limited to home folder.
        ''')

    def getCopy():
        """
        Gets copy of this avatar.
        """


class IOSUsers(Interface):
    '''
    Non-object oriented methods for retrieving system accounts.
    '''

    def getSuperAvatar(avatar):
        '''Create a super user/Administrator avatar.'''

    def getHomeFolder(username, token=None):
        '''Get home folder for local (or NIS) user.'''

    def userExists(username):
        '''Returns `True` if username exists on this system.'''

    def authenticateWithUsernameAndPassword(username, password):
        '''Check the username and password agains local accounts.

        Returns a tuple of (result, token).
        `result` is `True` if credentials are accepted, False otherwise.
        `token` is None on Unix system and a tokenhandler on Windows.
        '''

    def dropPrivileges(username):
        '''Change process privileges to `username`.

        Return `ChangeUserException` if current process has no permissions for
        switching to user.
        '''

    def executeAsUser(username, token=None):
        '''Returns a context manager for chaning current process privileges
        to `username`.

        Return `ChangeUserException` is there are no permissions for
        switching to user.
        '''

    def isUserInGroups(username, groups, token=None):
        '''Return true if `username` or 'token' is a member of `groups`.'''

    def getPrimaryGroup(username):
        '''Return the primary group for username.'''


class IFilesystemNode(Interface):
    """
    A node from the filesystem.

    It will not allow access ouside of avatar's root folder.
    """
    def __init__(avatar, segments=None):
        """
        It is initialized with an :class:`IFilesystemAvatar` and an optional
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
        Path inside the rooted filesytem.
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

    def getChilds():
        """
        Return the list of all :class:`IPath` childs.
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
    # def linkTo(segments):
    # def readLink():

    # getAttributes
    # setAttributes

    # getOwner()
    # setOwner()

    # getUsers()
    # addUsers()
    # hasUser()
    # removeUsers()


class ILocalFilesystem(Interface):
    '''Portable acces to local filesystem.

    This is designed to provide a single interface for accessing local files.

    It is initialized by passing an avatar.
    If the avatar root_folder is `None` the filesystem will allow full access.

    It is designed to use `segments` instead of file and folder names.
    Segments are a list of folder names and file name, that represent a path.

    We have two types of paths.
     * Chevah Path
     * Real Path (Operating System Path)

    A Chevah Path is the unified representation of paths across all Chevah
    products. A Chevah Path uses the Posix filesytem conventions.
     * /some/path/ - path to a folder
     * /some/path  - path to a file

    An Operating System Path is the paht used by the operating system, and
    they differ from one os to another.
     * On Unix - /some/path
     * on Windows c:\some\path
    '''

    avatar = Attribute('Avatar associated with this filesytem.')
    system_users = Attribute('Module for handling system users `IOSUsers`.')
    home_segments = Attribute('Segments for user home folder.')
    temp_segments = Attribute('Segments to temp folder.')

    _authentication_token = Attribute('Cached value')

    def getRealPathFromSegments(segments):
        '''Return the real path for the segments.'''

    def getSegmentsFromRealPath(real_path):
        '''Return the segments coresponding to an real absolute path.'''

    def getAbsoluteRealPath(real_path):
        '''Return the absolute real path from `real_path`.

        `real_path` is a path valid in the local operating system.
        '''

    def getPath(self, segments):
        '''Return the ChevahPath for the segment.

        It always uses the forward slash '/' as a separator.
        '''

    def getSegments(path):
        '''Return the segments from the root path to the passed `path`.

        `path` is a ChevahPath and can be a relative path of the home folder.
        '''

    def isFile(segments):
        '''Return True if segments points to a file.'''

    def isFolder(segments):
        '''Return True if segments points to a folder.'''

    def isLink(segments):
        '''Return True if segments points to a link.'''

    def exists(segments):
        '''Return True if segments points to an existing path.'''

    def createFolder(segments, recursive):
        '''Create a folder at the path specified by segments.

        If `recursive` is True it will try to create parent folder.
        If `recursive` is False and parent folder does not exists it will
        raise `OperationalException`.
        '''

    def deleteFolder(segments, recursive):
        '''Delete the folder at `segments`.
        If `recursive` is True the whole folder and its content will be
        deleted.
        If `resursice` is False and folder is not empty it will raise
        `OperationalException`.
        '''

    def deleteFile(segments):
        '''Delete the folder at `segments`.'''

    def rename(from_segments, to_segments):
        '''Rename file or folder.'''

    def openFile(self, segments, flags, mode):
        '''Return a file object for `segments`.

        `flags` and `mode` are used for os.open function.
        '''

    def openFileForReading(segments, utf8=False):
        '''Return a file object for reading the file.'''

    def openFileForWriting(segments, utf8=False):
        '''Return a file object for writing into the file.'''

    def openFileForAppending(segments, utf8=False):
        '''Return a file object for writing at the end a file.'''

    def getFileSize(segments):
        '''Return the file size, in bytes.'''

    def getFolderContent(segments):
        '''Return a list of files and folders contained by folder.'''

    def getAttributes(segments, attributes, follow_symlinks):
        '''Return a list of attributes for segment.

        Values are returned in the same order as attibutes list.
        Valid atrributes:
         * size
         * permissions
         * hardlinks
         * modified
         * owner
         * group
         * directory

        If no attributes are requests, it will return a raw access to the
        `stat` structure.
        If `follow_symlinks` it will return attributes for symlinks targets,
        not the symlink itself.
        '''

    def setAttributes(self, segments, attributes):
        '''Set `attributes` for segment.

        `attributes` is a dictionary of:
         * size -> s.st_size
         * uid -> s.st_uid
         * gid -> s.st_gid
         * permissions -> s.st_mode
         * atime -> int(s.st_atime)
         * mtime -> int(s.st_mtime)
        '''

    def readLink(segments):
        '''Return the value of link at `segments'.'''

    def makeLink(target_segments, link_segments):
        '''Create a link at `link_segments` pointing to `target_segments`.'''

    def setOwner(segments, owner):
        '''Set file/folder owner'''

    def getOwner(segments):
        '''Get file/folder owner'''

    def addGroup(segments, group, permissions):
        '''Add `group` to file/folder at `segments` using `permissions`.

        On Unix it will replace the current group and
        is equivalent to setGroup.
        '''

    def removeGroup(segments, group):
        '''Remove group from file/folder acl.

        On Unix it will only remove the group from extended acl.
        '''

    def hasGroup(segments, group):
        '''Return True if file at `segments` has group in ACL.'''


class IFilesystemNodeAttributes(Interface):
    """
    Attributes for file or folder.
    """

    name = Attribute('Name if this member.')
    size = Attribute('Size in bytes.')
    is_file = Attribute('True if member is a file.')
    is_folder = Attribute('True if member is a folder.')
    is_link = Attribute('True if member is a symbolic link.')
    # attributes = {
    #     'permissions': stats.st_mode,
    #     'hardlinks': stats.st_nlink,
    #     'modified': stats.st_mtime,
    #     'owner': str(stats.st_uid),
    #     'group': str(stats.st_gid),
    #     'uid': stats.st_uid,
    #     'gid': stats.st_gid,
    #     }
