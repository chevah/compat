# Copyright (c) 2012 Adi Roiban.
# See LICENSE for details.
'''
Portable implementation of operating system administration.

For not this code should only be used to help with testing and is not
designed to be used in production.
'''
from __future__ import with_statement
import os
import random
import subprocess
import sys

from chevah.compat import (
    LocalFilesystem,
    system_users,
    SuperAvatar,
    )


def execute(command, input_text=None, output=None,
        ignore_errors=False, verbose=False):
    if verbose:
        print 'Calling: %s' % command

    if output is None:
        output = subprocess.PIPE

    process = subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=output)
    (stdoutdata, stderrdata) = process.communicate(input_text)

    exit_code = process.returncode
    if exit_code != 0:
        if verbose:
            print u'Failed to execute %s\n%s' % (command, stderrdata)
        if not ignore_errors:
            sys.exit(exit_code)

    return (exit_code, stdoutdata)


class OSUser(object):
    '''An object storing all user information.'''

    def __init__(self, name, uid, gid=None, home_path=None, home_group=None,
                shell=None, shadow=None, password=None):
        if home_path is None:
            home_path = u'/tmp'

        if shell is None:
            shell = u'/bin/sh'

        if shadow is None:
            shadow = '!'

        self.name = name
        self.uid = uid
        self.gid = gid
        self.home_path = home_path
        self.home_group = home_group
        self.shell = shell
        self.shadow = shadow
        self.password = password


class OSGroup(object):
    '''An object storing all user information.'''

    def __init__(self, name, gid, members=None, password=None):

        if members is None:
            members = []

        self.name = name
        self.gid = gid
        self.members = members
        self.password = password


class OSAdministration(object):

    def __init__(self):
        self.name = self.getName()
        self.fs = LocalFilesystem(SuperAvatar())

    def getName(self):
        '''Return the name of the platform.'''
        name = sys.platform
        if name.startswith('linux'):
            name = 'linux'
        elif name.startswith('aix'):
            name = 'aix'
        elif name == 'darwin':
            name = 'osx'
        elif name.startswith('sunos'):
            name = 'solaris'
        elif name.startswith('win32'):
            name = 'windows'
        else:
            name = None

        if name is None:
            raise AssertionError('Unsupported platform: ' + sys.platform)

        return name

    def addGroup(self, group):
        '''Add the group to the local operating system.'''
        add_user_method = getattr(self, '_addGroup_' + self.name)
        add_user_method(group)

    def _addGroup_unix(self, group):
        group_segments = ['etc', 'group']
        group_line = u'%s:x:%d:' % (group.name, group.gid)
        gshadow_segments = ['etc', 'gshadow']
        gshadow_line = u'%s:!::' % (group.name)

        self._appendUnixEntry(group_segments, group_line)

        if self.fs.exists(gshadow_segments):
            self._appendUnixEntry(gshadow_segments, gshadow_line)

        # Wait for group to be available.
        self._getUnixGroup(group.name)

    def _getUnixGroup(self, name):
        """
        Return grp data for group with `name`.
        """
        import grp
        import time
        name_encoded = name.encode('utf-8')
        for iterator in xrange(5):
            for group in grp.getgrall():
                if group[0] == name_encoded:
                    return group
            time.sleep(0.5)

        raise AssertionError('Failed to create group %s' % (
            name.encode('utf-8')))

    def _addGroup_aix(self, group):
        group_name = group.name.encode('utf-8')
        execute(['sudo', 'mkgroup', 'id=' + str(group.gid), group_name])

    def _addGroup_linux(self, group):
        self._addGroup_unix(group)

    def _addGroup_osx(self, group):
        groupdb_name = u'/Groups/' + group.name
        execute([
            'sudo', 'dscl', '.', '-create', groupdb_name,
            'gid', str(group.gid),
            'passwd', '"*"',
            ])

    def _addGroup_solaris(self, group):
        self._addGroup_unix(group)

    def _addGroup_windows(self, group):
        """
        Add a group to Windows local system.
        """
        import win32net
        data = {
            'name': group.name,
        }
        win32net.NetLocalGroupAdd(None, 0, data)

    def addUsersToGroup(self, group, users=None):
        '''Add the group to the local operating system.'''
        if users is None:
            users = []

        add_user_method = getattr(self, '_addUsersToGroup_' + self.name)
        add_user_method(group, users)

    def _addUsersToGroup_unix(self, group, users):
        segments = ['etc', 'group']
        members = u','.join(users)
        self._changeUnixEntry(
            segments=segments,
            name=group.name,
            field=4,
            value_when_empty=members,
            value_to_append=u',' + members,
            )

    def _addUsersToGroup_aix(self, group, users):
        if not len(users):
            return

        group_name = group.name.encode('utf-8')
        members_list = ','.join(users)
        members_list = 'users=' + members_list
        members_list = members_list.encode('utf-8')
        execute(['sudo', 'chgroup', members_list, group_name])

    def _addUsersToGroup_linux(self, group, users):
        self._addUsersToGroup_unix(group, users)

    def _addUsersToGroup_osx(self, group, users):
        groupdb_name = u'/Groups/' + group.name
        for member in users:
            execute([
                'sudo', 'dscl', '.', '-append', groupdb_name,
                'GroupMembership', member,
                ])

    def _addUsersToGroup_solaris(self, group, users):
        self._addUsersToGroup_unix(group, users)

    def _addUsersToGroup_windows(self, group, users):
        """
        Add `users` to group.
        """
        import win32net
        members_info = []
        for member in users:
            members_info.append({
                'domainandname': member
                })
        win32net.NetLocalGroupAddMembers(None, group.name, 3, members_info)

    def addUser(self, user):
        '''Add the user and set the corresponding passwords.'''
        add_user_method = getattr(self, '_addUser_' + self.name)
        add_user_method(user)

        if user.password:
            self.setUserPassword(user.name, user.password)

    def _addUser_unix(self, user):
        group = OSGroup(name=user.name, gid=user.uid)
        self._addGroup_linux(group)

        passwd_segments = ['etc', 'passwd']
        passwd_line = (
            u'%s:x:%d:%d::%s:%s' % (
                user.name, user.uid, user.gid, user.home_path, user.shell))

        shadow_segments = ['etc', 'shadow']
        shadow_line = u'%s:!:15218:0:99999:7:::' % (user.name)

        self._appendUnixEntry(passwd_segments, passwd_line)

        if self.fs.exists(shadow_segments):
            self._appendUnixEntry(shadow_segments, shadow_line)

        if user.home_path != u'/tmp':
            execute(['sudo', 'mkdir', user.home_path.encode('utf-8')])
            execute(
                ['sudo', 'chown', str(user.uid),
                    user.home_path.encode('utf-8'),
                ])
            if user.home_group:
                # On some Unix system we can change group as unicode,
                # so we get the ID and change using the group ID.
                group = self._getUnixGroup(user.home_group)
                execute(
                    ['sudo', 'chgrp', str(group[2]),
                        user.home_path.encode('utf-8'),
                    ])
            else:
                execute(
                    ['sudo', 'chgrp', str(user.uid),
                        user.home_path.encode('utf-8'),
                    ])

        self._waitForUser(user.name)

    def _waitForUser(self, name):
        """
        Wait for user to be visible in the system.
        """
        import pwd
        import time
        name_encoded = name.encode('utf-8')
        for iterator in xrange(5):
            try:
                pwd.getpwnam(name_encoded)
                return
            except KeyError:
                pass
            time.sleep(0.5)

        raise AssertionError('Failed to create group %s' % (
            name.encode('utf-8')))

    def _addUser_aix(self, user):
        # AIX will only allow creating users with shells from
        # /etc/security/login.cfg.
        user_shell = user.shell
        if user.shell == '/bin/false':
            user_shell = '/bin/sh'

        user_name = user.name.encode('utf-8')
        execute([
            'sudo', 'mkuser',
            'id=' + str(user.uid),
            'home=' + user.home_path.encode('utf-8'),
            'shell=' + user_shell,
            user_name,
            ])
        if user.home_group:
            execute(
                ['sudo', 'chgrp', user.home_group.encode('utf-8'),
                user.home_path.encode('utf-8')
                ])

    def _addUser_linux(self, user):
        self._addUser_unix(user)

    def _addUser_osx(self, user):
        userdb_name = u'/Users/' + user.name
        home_folder = u'/Users/' + user.name
        execute([
            'sudo', 'dscl', '.', '-create', userdb_name,
            'UserShell', '/bin/bash',
            ])
        execute([
            'sudo', 'dscl', '.', '-create', userdb_name,
            'UniqueID', str(user.uid),
            ])
        execute([
            'sudo', 'dscl', '.', '-create', userdb_name,
            'PrimaryGroupID', str(user.gid),
            ])
        execute([
            'sudo', 'dscl', '.', '-create', userdb_name,
            'NFSHomeDirectory', home_folder,
            ])

        # Create home folder.
        execute(['sudo', 'mkdir', home_folder])
        execute(['sudo', 'chown', user.name, home_folder])
        execute(['sudo', 'chgrp', user.gid, home_folder])

        if user.home_group:
            execute(['sudo', 'chgrp', user.home_group, user.home_path])
        else:
            execute(['sudo', 'chgrp', user.name, home_folder])

    def _addUser_solaris(self, user):
        self._addUser_unix(user)

    def _addUser_windows(self, user, create_profile=True):
        """
        Create an local Windows account.

        When `create_profile` is True, this method will also try to create
        the home folder. Otherwise the user is created, but the home
        folder does not exists until the first login or when profile
        is explicitly created in other part.
        """
        import win32net
        import win32netcon
        user_info = {
            'name': user.name,
            'password': user.password,
            'priv': win32netcon.USER_PRIV_USER,
            'home_dir': None,
            'comment': None,
            'flags': win32netcon.UF_SCRIPT,
            'script_path': None,
        }
        win32net.NetUserAdd(None, 1, user_info)
        if user.password and create_profile:
            result, token = system_users.authenticateWithUsernameAndPassword(
                username=user.name, password=user.password)
            system_users._createLocalProfile(username=user.name, token=token)

    def setUserPassword(self, username, password):
        set_password_method = getattr(self, '_setUserPassword_' + self.name)
        set_password_method(username, password)

    def _setUserPassword_unix(self, username, password):
        import crypt
        ALPHABET = (
            '0123456789'
            'abcdefghijklmnopqrstuvwxyz'
            'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
            )
        salt = ''.join(random.choice(ALPHABET) for i in range(8))
        shadow_password = crypt.crypt(
            password.encode('utf-8'),
            '$1$' + salt + '$',
            )

        segments = ['etc', 'shadow']
        self._changeUnixEntry(
            segments=segments,
            name=username,
            field=2,
            value_to_replace=shadow_password,
            )

    def _setUserPassword_aix(self, username, password):
        input_text = username.encode('utf-8') + ':' + password.encode('utf-8')
        execute(
            command=['sudo', 'chpasswd', '-c'],
            input_text=input_text,
            )

    def _setUserPassword_linux(self, username, password):
        self._setUserPassword_unix(username, password)

    def _setUserPassword_osx(self, username, password):
        userdb_name = u'/Users/' + username
        execute([
            'sudo', 'dscl', '.', '-passwd', userdb_name,
            password,
            ])

    def _setUserPassword_solaris(self, username, password):
        self._setUserPassword_unix(username, password)

    def _setUserPassword_windows(self, username, password):
        """
        On Windows we can not change the password without having the
        old password.

        For not this works, but this code is not 100% valid.
        """
        try:
            import win32net
            win32net.NetUserChangePassword(None, username, password, password)
        except:
            print 'Failed to set password "%s" for user "%s".' % (
                password, username)
            raise

    def deleteUser(self, user):
        '''Delete user from the local operating system.'''
        delete_user_method = getattr(self, '_deleteUser_' + self.name)
        delete_user_method(user)

    def _deleteUser_unix(self, user):
        self._deleteUnixEntry(
            kind='user',
            name=user.name,
            files=[['etc', 'passwd'], ['etc', 'shadow']])

        group = OSGroup(name=user.name, gid=user.uid)
        self._deleteGroup_linux(group)

        if not u'tmp' in user.home_path:
            execute(['sudo', 'rm', '-rf', user.home_path.encode('utf-8')])

    def _deleteUser_aix(self, user):
        execute(['sudo', 'rmuser', '-p', user.name.encode('utf-8')])

        if not u'tmp' in user.home_path:
            execute(['sudo', 'rm', '-rf', user.home_path.encode('utf-8')])

    def _deleteUser_linux(self, user):
        self._deleteUser_unix(user)

    def _deleteUser_osx(self, user):
        userdb_name = u'/Users/' + user.name
        execute(['sudo', 'dscl', '.', '-delete', userdb_name])

        if not u'tmp' in user.home_path:
            home_folder = u'/Users/' + user.name
            execute(['sudo', 'rm', '-rf', home_folder])

    def _deleteUser_solaris(self, user):
        self._deleteUser_unix(user)

    def _deleteUser_windows(self, user):
        """
        Removes an account from Windows together.

        Home folder is not removed.
        """
        import win32net
        try:
            win32net.NetUserDel(None, user.name)
        except win32net.error, (number, context, message):
            # Ignore user not found error.
            if number != 2221:
                raise

        # /tmp is assigned for Users without a home folder and we don't
        # want to delete this folder.
        # We can not reliably get home folder on all Windows version, so
        # we assume that home folders for other accounts are siblings to
        # the home folder of the current account.
        # FIXME:927:
        # We need to look for a way to delete homefolders with unicode
        # names.
        if not u'tmp' in user.home_path:
            home_base = os.path.dirname(os.getenv('USERPROFILE'))
            home_path = os.path.join(home_base, user.name)
            subprocess.call(
                'cmd.exe /C rmdir /S /Q "' + home_path.encode('utf-8') + '"',
                shell=True)

    def deleteGroup(self, group):
        '''Delete group from the local operating system.'''
        delete_group_method = getattr(self, '_deleteGroup_' + self.name)
        delete_group_method(group)

    def _deleteGroup_unix(self, group):
        self._deleteUnixEntry(
            kind='group',
            name=group.name,
            files=[['etc', 'group'], ['etc', 'gshadow']])

    def _deleteGroup_aix(self, group):
        execute(['sudo', 'rmgroup', group.name.encode('utf-8')])

    def _deleteGroup_linux(self, group):
        self._deleteGroup_unix(group)

    def _deleteGroup_osx(self, group):
        groupdb_name = u'/groups/' + group.name
        execute(['sudo', 'dscl', '.', '-delete', groupdb_name])

    def _deleteGroup_solaris(self, group):
        self._deleteGroup_unix(group)

    def _deleteGroup_windows(self, group):
        """
        Remove a group from Windows local system.
        """
        import win32net
        win32net.NetLocalGroupDel(None, group.name)

    def _appendUnixEntry(self, segments, new_line):
        '''Add the new_line to the end of `segments`.'''
        temp_segments = segments[:]
        temp_segments[-1] = temp_segments[-1] + '-'
        content = self._getFileContent(segments)
        opened_file = self.fs.openFileForWriting(temp_segments, utf8=True)
        try:
            for line in content:
                opened_file.write(line + '\n')
            opened_file.write(new_line + '\n')
        finally:
            opened_file.close()

        self._replaceFile(temp_segments, segments)

    def _deleteUnixEntry(self, files, name, kind):
        '''Delete a generic unix entry with 'name' from all `files`.'''
        exists = False
        for segments in files:

            if not self.fs.exists(segments):
                continue

            exists = False
            temp_segments = segments[:]
            temp_segments[-1] = temp_segments[-1] + '-'

            content = self._getFileContent(segments)
            opened_file = self.fs.openFileForWriting(
                temp_segments, utf8=True)
            try:

                for line in content:
                    entry_name = line.split(':')[0]
                    if entry_name == name:
                        exists = True
                        continue
                    opened_file.write(line + '\n')
            finally:
                if opened_file:
                    opened_file.close()

            if exists:
                self._replaceFile(temp_segments, segments)

        if not exists:
            raise AssertionError((
                'No such %s: %s' % (kind, name)).encode('utf-8'))

    def _changeUnixEntry(self, segments, name, field,
            value_when_empty=None, value_to_append=None,
            value_to_replace=None,
            ):
        '''Update entry 'name' with a new value or an appened value.

        Field is the number of entry filed to update, counting with 1.
        '''
        exists = False
        temp_segments = segments[:]
        temp_segments[-1] = temp_segments[-1] + '-'

        content = self._getFileContent(segments)
        opened_file = self.fs.openFileForWriting(
            temp_segments, utf8=True)
        try:
            for line in content:
                fields = line.split(':')
                field_name = fields[0]
                if name == field_name:
                    exists = True

                    if fields[field - 1] == '':
                        if value_when_empty:
                            fields[field - 1] = value_when_empty
                        elif value_to_replace:
                            fields[field - 1] = value_to_replace
                        else:
                            pass
                    elif value_to_append:
                        fields[field - 1] = (
                            fields[field - 1] + value_to_append)
                    elif value_to_replace:
                        fields[field - 1] = value_to_replace
                    else:
                        pass

                    new_line = u':'.join(fields)
                else:
                    new_line = line

                opened_file.write(new_line + '\n')
        finally:
                opened_file.close()

        if exists:
            self._replaceFile(temp_segments, segments)
        else:
            raise AssertionError(u'No such entry: %s' % (name))

    def _replaceFile(self, from_segments, to_segments):
        (uid, gid, permissions) = self.fs.getAttributes(
            to_segments, ('uid', 'gid', 'permissions'))
        self.fs.setAttributes(
            from_segments,
            {'permissions': permissions,
            'uid': uid,
            'gid': gid,
            })
        self.fs.rename(from_segments, to_segments)

    def _getFileContent(self, segments):
        """
        Return a list of all lines from file.
        """
        opened_file = self.fs.openFileForReading(segments, utf8=True)
        content = []
        try:
            for line in opened_file:
                content.append(line.rstrip())
        finally:
            opened_file.close()

        return content


# Create the singleton.
os_administration = OSAdministration()
