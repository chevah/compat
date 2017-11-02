# Copyright (c) 2012 Adi Roiban.
# See LICENSE for details.
"""
Portable implementation of operating system administration.

For not this code should only be used to help with testing and is not
designed to be used in production.

AIX
---

AIX security sub-system is a bit more complex than Linux and it keeps a lot of
files in /etc/security. This is why we use only system command for managing
users and groups on AIX.

Default groups and users have a maximum length of 9. Check `lsattr -El sys0`
for `max_logname`. Can be changed with `chdev -l sys0 -a max_logname=128`.

"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from six.moves import range
from contextlib import contextmanager
import os
import codecs
import random
import socket
import subprocess
import sys
import time

from chevah.compat import (
    LocalFilesystem,
    process_capabilities,
    system_users,
    SuperAvatar,
    )
from chevah.compat.winerrors import ERROR_NONE_MAPPED


def execute(command, input_text=None, output=None, ignore_errors=True):
    """
    Execute a command having stdout redirected and using 'input_text' as
    input.
    """
    verbose = False

    if verbose:
        print('Calling: %s' % command)

    if output is None:
        output = subprocess.PIPE

    command = [part for part in command]

    process = subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=output)
    (stdoutdata, stderrdata) = process.communicate(input_text)

    exit_code = process.returncode
    if exit_code != 0:
        if verbose:
            print(u'Failed to execute %s\n%s' % (command, stderrdata))

        if not ignore_errors:
            sys.exit(exit_code)

    return (exit_code, stdoutdata)


class OSAdministrationUnix(object):

    shadow_segments = ['etc', 'shadow']
    passwd_segments = ['etc', 'passwd']
    group_segments = ['etc', 'group']
    gshadow_segments = ['etc', 'gshadow']

    def __init__(self):
        self.name = process_capabilities.os_name
        self.fs = LocalFilesystem(SuperAvatar())

    def addGroup(self, group):
        """
        Add the group to the local computer or domain.
        """
        add_group_method = getattr(self, '_addGroup_' + self.name)
        add_group_method(group=group)

    def _addGroup_unix(self, group):
        group_line = u'%s:x:%d:' % (group.name, group.gid)
        gshadow_line = u'%s:!::' % (group.name)

        self._appendUnixEntry(self.group_segments, group_line)

        if self.fs.exists(self.gshadow_segments):
            self._appendUnixEntry(self.gshadow_segments, gshadow_line)

        # Wait for group to be available.
        self._getUnixGroup(group.name)

    def _getUnixGroup(self, name):
        """
        Get unix group entry, retrying if group is not available yet.
        """
        import grp
        name_encoded = codecs.encode(name, 'utf-8')

        # Try to get the group in list of all groups.
        group_found = False
        for iterator in range(1000):
            if group_found:
                break
            for group in grp.getgrall():
                if group[0] == name_encoded:
                    group_found = True
                    break
            time.sleep(0.1)

        if not group_found:
            raise AssertionError('Failed to get group from all: %s' % (
                name_encoded))

        # Now we find the group in list of all groups, but
        # we need to make sure it is also available to be
        # retrieved by name.
        for iterator in range(1000):
            try:
                return grp.getgrnam(name_encoded)
            except KeyError:
                # Group not ready yet.
                pass
            time.sleep(0.1)

        raise AssertionError(
            'Group found in all, but not available by name %s' % (
                name_encoded))

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

    def _addGroup_hpux(self, group):
        self._addGroup_unix(group)

    def _addGroup_freebsd(self, group):
        group_name = group.name.encode('utf-8')
        execute([
            'sudo', 'pw', 'groupadd',
            '-g', str(group.gid),
            '-n', group_name,
            ])

    def _addGroup_openbsd(self, group):
        group_name = group.name.encode('utf-8')
        execute([
            'sudo', 'groupadd',
            '-g', str(group.gid),
            group_name,
            ])

    def addUsersToGroup(self, group, users=None):
        """
        Add the users to the specified group.
        """
        if users is None:
            users = []

        add_user_method = getattr(self, '_addUsersToGroup_' + self.name)
        add_user_method(group=group, users=users)

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

    def _addUsersToGroup_hpux(self, group, users):
        self._addUsersToGroup_unix(group, users)

    def _addUsersToGroup_freebsd(self, group, users):
        if not len(users):
            return

        group_name = group.name.encode('utf-8')
        members_list = ','.join(users)
        execute([
            'sudo', 'pw', 'groupmod', group_name,
            '-M', members_list.encode('utf-8')])

    def _addUsersToGroup_openbsd(self, group, users):
        group_name = group.name.encode('utf-8')
        for user in users:
            execute([
                'sudo', 'usermod', '-G', group_name, user.encode('utf-8')])

    def addUser(self, user):
        """
        Add the user and set the corresponding passwords to local computer
        or domain.
        """
        add_user_method = getattr(self, '_addUser_' + self.name)

        add_user_method(user=user)
        if user.password:
            self.setUserPassword(user=user)

    def _addUser_unix(self, user):
        # Prevent circular import.
        from chevah.compat.testing import TestGroup
        group = TestGroup(name=user.name, posix_gid=user.uid)
        self._addGroup_unix(group)

        values = (
            user.name, user.uid, user.gid, user.posix_home_path, user.shell)
        passwd_line = u'%s:x:%d:%d::%s:%s' % values

        shadow_line = u'%s:!:15218:0:99999:7:::' % (user.name)

        self._appendUnixEntry(self.passwd_segments, passwd_line)

        if self.fs.exists(self.shadow_segments):
            # Only write shadow if exists.
            self._appendUnixEntry(self.shadow_segments, shadow_line)

        # Wait for user to be available before creating home folder.
        self._getUnixUser(user.name)

        if user.posix_home_path == u'/tmp':
            return

        encoded_home_path = user.posix_home_path.encode('utf-8')
        execute(['sudo', 'mkdir', encoded_home_path])
        execute([
            'sudo', 'chown', str(user.uid),
            encoded_home_path,
            ])
        if user.home_group:
            # On some Unix system we can change group as unicode,
            # so we get the ID and change using the group ID.
            group = self._getUnixGroup(user.home_group)
            execute([
                'sudo', 'chgrp', str(group[2]),
                encoded_home_path,
                ])
        else:
            execute([
                'sudo', 'chgrp', str(user.uid),
                encoded_home_path,
                ])

    def _getUnixUser(self, name):
        """
        Get Unix user entry, retrying if user is not available yet.
        """
        import pwd
        name_encoded = name.encode('utf-8')
        for iterator in range(1000):
            try:
                user = pwd.getpwnam(name_encoded)
                return user
            except (KeyError, OSError) as e:
                pass
            time.sleep(0.2)
        raise AssertionError(
            'Could not get user %s: %s' % (name_encoded, e))

    def _addUser_aix(self, user):
        # AIX will only allow creating users with shells from
        # /etc/security/login.cfg.
        user_shell = user.shell
        if user.shell == '/bin/false':
            user_shell = '/bin/sh'

        user_name = user.name.encode('utf-8')
        command = [
            'sudo', 'mkuser',
            'id=' + str(user.uid),
            'home=' + user.posix_home_path.encode('utf-8'),
            'shell=' + user_shell,
            ]

        if user.primary_group_name:
            command.append('pgrp=' + user.primary_group_name)

        command.append(user_name)

        execute(command)
        if user.home_group:
            execute([
                'sudo', 'chgrp', user.home_group.encode('utf-8'),
                user.posix_home_path.encode('utf-8')
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
        execute(['sudo', 'chgrp', str(user.gid), home_folder])

        if user.home_group:
            execute(['sudo', 'chgrp', user.home_group, user.posix_home_path])
        else:
            execute(['sudo', 'chgrp', user.name, home_folder])

    def _addUser_solaris(self, user):
        self._addUser_unix(user)

    def _addUser_hpux(self, user):
        self._addUser_unix(user)

    def _addUser_freebsd(self, user):
        user_name = user.name.encode('utf-8')
        home_path = user.posix_home_path.encode('utf-8')
        command = [
            'sudo', 'pw', 'user', 'add', user_name,
            '-u', str(user.uid),
            '-d', home_path,
            '-s', user.shell.encode('utf-8'),
            '-m',
            ]
        # Only add gid if required.
        if user.uid != user.gid:
            command.extend(['-g', str(user.gid)])

        execute(command)

        if user.home_group:
            execute([
                'sudo', 'chgrp', user.home_group.encode('utf-8'), home_path])

    def _addUser_openbsd(self, user):
        home_path = user.posix_home_path.encode('utf-8')
        command = [
            'sudo', 'useradd',
            '-u', str(user.uid).encode('utf-8'),
            '-d', home_path,
            '-s', user.shell.encode('utf-8'),
            ]

        if user.posix_home_path != '/tmp':
            command.append('-m'),

        # Only add gid if required.
        if user.uid != user.gid:
            command.extend(['-g', str(user.gid)])

        command.append(user.name.encode('utf-8'))

        execute(command)

        # Wait a bit for the user to be created.
        time.sleep(0.2)

        if user.home_group:
            execute([
                'sudo', 'chgrp', user.home_group.encode('utf-8'), home_path])

    def setUserPassword(self, user):
        """
        Set a password for the user. The password is an attribute of the
        'user'.
        """
        set_password_method = getattr(self, '_setUserPassword_' + self.name)
        set_password_method(user)

    def _setUserPassword_unix(self, user):
        """
        Set a password for the `user` on Unix.


        The password is an attribute of the 'user'.

        This function is common for Unix compliant OSes.
        It is implemented by writing directly to shadow or passwd file.
        """
        if self.fs.exists(self.shadow_segments):
            return self._setUserPassword_shadow(user, self.shadow_segments)
        else:
            return self._setUserPassword_passwd(user, self.passwd_segments)

    def _setUserPassword_shadow(self, user, segments):
        """
        Set a password in shadow file.
        """
        import crypt
        ALPHABET = (
            '0123456789'
            'abcdefghijklmnopqrstuvwxyz'
            'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
            )
        salt = ''.join(random.choice(ALPHABET) for i in range(8))
        shadow_password = crypt.crypt(
            user.password.encode('utf-8'),
            '$1$' + salt + '$',
            )

        self._changeUnixEntry(
            segments=segments,
            name=user.name,
            field=2,
            value_to_replace=shadow_password,
            )

    def _setUserPassword_passwd(self, user, segments):
        """
        Set a password in passwd file.
        """
        import crypt
        ALPHABET = (
            '0123456789'
            'abcdefghijklmnopqrstuvwxyz'
            'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
            )
        salt = ''.join(random.choice(ALPHABET) for i in range(2))
        passwd_password = crypt.crypt(
            user.password.encode('utf-8'), salt)
        self._changeUnixEntry(
            segments=segments,
            name=user.name,
            field=2,
            value_to_replace=passwd_password,
            )

    def _setUserPassword_aix(self, user):
        """
        Set a password for the user on AIX. The password is an attribute
        of the 'user'.
        """
        input_text = u'%s:%s' % (user.name, user.password)
        execute(
            command=['sudo', 'chpasswd', '-c'],
            input_text=input_text.encode('utf-8'),
            )

    def _setUserPassword_linux(self, user):
        """
        Set a password for the user on Linux. The password is an attribute
        of the 'user'.
        """
        self._setUserPassword_unix(user)

    def _setUserPassword_osx(self, user):
        """
        Set a password for the user on Mac OS X. The password is an attribute
        of the 'user'.
        """
        userdb_name = u'/Users/' + user.name
        execute([
            'sudo', 'dscl', '.', '-passwd', userdb_name,
            user.password,
            ])

    def _setUserPassword_solaris(self, user):
        """
        Set a password for the user on Solaris. The password is an attribute
        of the 'user'.
        """
        self._setUserPassword_unix(user)

    def _setUserPassword_hpux(self, user):
        self._setUserPassword_unix(user)

    def _setUserPassword_freebsd(self, user):
        execute(
            command=[
                'sudo',
                'pw', 'mod', 'user', user.name.encode('utf-8'), '-h', '0',
                ],
            input_text=user.password.encode('utf-8'),
            )

    def _setUserPassword_openbsd(self, user):
        code, out = execute(
            command=['encrypt'],
            input_text=user.password.encode('utf-8'),
            )

        execute(
            command=[
                'sudo',
                'usermod', '-p', out.strip(), user.name.encode('utf-8'),
                ],
            )

    def deleteUser(self, user):
        """
        Delete user from the local operating system.
        """
        delete_user_method = getattr(self, '_deleteUser_' + self.name)
        delete_user_method(user)

    def deleteHomeFolder(self, user):
        """
        Removes user's home folder if outside temporary folder.
        """
        if user.posix_home_path and user.posix_home_path.startswith(u'/tmp'):
            return

        delete_folder_method = getattr(self, '_deleteHomeFolder_' + self.name)
        delete_folder_method(user)

    def _deleteHomeFolder_linux(self, user):
        self._deleteHomeFolder_unix(user)

    def _deleteHomeFolder_solaris(self, user):
        self._deleteHomeFolder_unix(user)

    def _deleteHomeFolder_hpux(self, user):
        self._deleteHomeFolder_unix(user)

    def _deleteHomeFolder_aix(self, user):
        self._deleteHomeFolder_unix(user)

    def _deleteHomeFolder_freebsd(self, user):
        self._deleteHomeFolder_unix(user)

    def _deleteHomeFolder_openbsd(self, user):
        self._deleteHomeFolder_unix(user)

    def _deleteHomeFolder_unix(self, user):
        encoded_home_path = user.posix_home_path.encode('utf-8')
        execute(['sudo', 'rm', '-rf', encoded_home_path])

    def _deleteHomeFolder_osx(self, user):
        home_folder = u'/Users/%s' % user.name
        execute(['sudo', 'rm', '-rf', home_folder])

    def _deleteUser_unix(self, user):
        self._deleteUnixEntry(
            kind='user',
            name=user.name,
            files=[['etc', 'passwd'], ['etc', 'shadow']])

        # Prevent circular import.
        from chevah.compat.testing import TestGroup
        group = TestGroup(name=user.name, posix_gid=user.uid)
        self._deleteGroup_unix(group)
        self.deleteHomeFolder(user)

    def _deleteUser_aix(self, user):
        execute(['sudo', 'rmuser', '-p', user.name.encode('utf-8')])
        self.deleteHomeFolder(user)

    def _deleteUser_linux(self, user):
        self._deleteUser_unix(user)

    def _deleteUser_osx(self, user):
        userdb_name = u'/Users/' + user.name
        execute(['sudo', 'dscl', '.', '-delete', userdb_name])
        self.deleteHomeFolder(user)

    def _deleteUser_solaris(self, user):
        self._deleteUser_unix(user)

    def _deleteUser_hpux(self, user):
        self._deleteUser_unix(user)

    def _deleteUser_freebsd(self, user):
        execute(['sudo', 'pw', 'userdel', user.name.encode('utf-8')])
        self.deleteHomeFolder(user)

    def _deleteUser_openbsd(self, user):
        execute(['sudo', 'userdel', user.name.encode('utf-8')])
        self.deleteHomeFolder(user)

    def deleteGroup(self, group):
        """
        Delete group from the local operating system.
        """
        delete_group_method = getattr(self, '_deleteGroup_' + self.name)
        delete_group_method(group=group)

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

    def _deleteGroup_hpux(self, group):
        self._deleteGroup_unix(group)

    def _deleteGroup_freebsd(self, group):
        execute(['sudo', 'pw', 'group', 'del', group.name.encode('utf-8')])

    def _deleteGroup_openbsd(self, group):
        execute(['sudo', 'groupdel', group.name.encode('utf-8')])

    def _appendUnixEntry(self, segments, new_line):
        """
        Add the new_line to the end of `segments`.
        """
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
        """
        Delete a generic unix entry with 'name' from all `files`.
        """
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

    def _changeUnixEntry(
        self, segments, name, field,
        value_when_empty=None, value_to_append=None,
        value_to_replace=None,
            ):
        """
        Update entry 'name' with a new value or an appended value.
        Field is the number of entry filed to update, counting with 1.
        """
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
        attributes = self.fs.getAttributes(to_segments)
        self.fs.setAttributes(
            from_segments,
            {
                'mode': attributes.mode,
                'uid': attributes.uid,
                'gid': attributes.gid,
                },
            )
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


class OSAdministrationWindows(OSAdministrationUnix):
    """
    Windows specific implementation for OS administration.
    """

    def addGroup(self, group):
        """
        Add a group to Windows local system.
        """
        import win32net
        data = {'name': group.name}
        try:
            win32net.NetLocalGroupAdd(group.pdc, 0, data)
        except Exception as error:  # pragma: no cover
            raise AssertionError(
                'Failed to add group %s in domain %s. %s' % (
                    group.name, group.pdc, error))

    def addUsersToGroup(self, group, users=None):
        """
        Add `users` to group.
        """
        if users is None:
            users = []

        import win32net
        members_info = []
        for member in users:
            members_info.append({
                'domainandname': member
                })
        try:
            win32net.NetLocalGroupAddMembers(
                group.pdc, group.name, 3, members_info)
        except Exception as error:  # pragma: no cover
            raise AssertionError(
                'Failed to add to group %s users %s. %s' % (
                    group.name, users, error))

    def addUser(self, user):
        """
        Create an local Windows account.

        When `user.windows_create_local_profile` is True, this method will
        also try to create the home folder.

        Otherwise the user is created, but the home folder does not exists
        until the first login or when profile is explicitly created in other
        part.
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

        win32net.NetUserAdd(user.pdc, 1, user_info)
        if user.windows_create_local_profile:
            if not user.password:  # pragma: no cover
                raise AssertionError('You must provide a password.')

            system_users._createLocalProfile(
                username=user.upn, token=user.token)

        user.windows_sid = self._getUserSID(user)

        if user.windows_required_rights:
            self._grantUserRights(user, user.windows_required_rights)

    def setUserPassword(self, user):
        """
        On Windows we can not change the password without having the
        old password.

        For not this works, but this code is not 100% valid.
        """
        # NetUserChangePassword works a little different that other
        # Net* functions. In order to work on local computer it requires
        # that the first argument be the computer name and not 'None'
        # like the rest of Net* functions.
        pdc = user.pdc
        if not pdc:
            pdc = socket.gethostname()

        try:
            import win32net
            win32net.NetUserChangePassword(
                pdc, user.name, user.password, user.password)
        except Exception:  # pragma: no cover
            print('Failed to set password "%s" for user "%s" on pdc "%s".' % (
                user.password, user.name, pdc))
            raise

    def deleteUser(self, user):
        """
        Removes an account from Windows together.
        Home folder is not removed.
        """
        if user.windows_required_rights:
            self._revokeUserRights(user, user.windows_required_rights)

        import win32net
        try:
            win32net.NetUserDel(user.pdc, user.name)
        except win32net.error as error:  # pragma: no cover
            # Ignore user not found error.
            (number, context, message) = error
            # Ignore user not found error.
            if number != ERROR_NONE_MAPPED:
                raise

        if user.windows_create_local_profile:
            self.deleteHomeFolder(user)

    def deleteHomeFolder(self, user):
        """
        Remove home folder for specified user, raise an error if operation
        not successful.
        """
        # We can not reliably get home folder on all Windows version, so
        # we assume that home folders for other accounts are siblings to
        # the home folder of the current account.
        home_base = os.path.dirname(os.getenv('USERPROFILE'))
        profile_folder_path = os.path.join(home_base, user.name)

        # FIXME:927:
        # We need to look for a way to delete home folders with unicode
        # names.
        command = u'rmdir /S /Q "%s"' % profile_folder_path
        result = subprocess.call(command.encode('utf-8'), shell=True)
        if result != 0:  # pragma: no cover
            message = u'Unable to remove folder [%s]: %s\n%s.' % (
                result, profile_folder_path, command)
            raise AssertionError(message.encode('utf-8'))

    def deleteGroup(self, group):
        """
        Remove a group from Windows local system.
        """
        import win32net
        win32net.NetLocalGroupDel(group.pdc, group.name)

    @contextmanager
    def _openLSAPolicy(self):
        """
        Context manager for opening LSA policy token in ALL ACCESS mode.
        """
        import win32security
        policy_handle = None
        try:
            policy_handle = win32security.LsaOpenPolicy(
                '', win32security.POLICY_ALL_ACCESS)

            yield policy_handle
        finally:
            if policy_handle:
                win32security.LsaClose(policy_handle)

    def _getUserSID(self, user):
        """
        Return the security id for user with `username`.

        Raises an error if user cannot not be found.
        """
        import win32security
        try:
            result = win32security.LookupAccountName('', user.name)
            user_sid = result[0]
        except win32security.error:  # pragma: no cover
            message = u'User %s could not be found.' % (user.name)
            raise AssertionError(message.encode('utf-8'))

        return user_sid

    def _grantUserRights(self, user, rights):
        """
        Grants `rights` to `user`.
        """
        import win32security
        with self._openLSAPolicy() as policy_handle:
            win32security.LsaAddAccountRights(
                policy_handle, user.windows_sid, rights)
            user._invalidateToken()

    def _revokeUserRights(self, user, rights):
        """
        Revokes `rights` from `user`.
        """
        import win32security
        with self._openLSAPolicy() as policy_handle:
            win32security.LsaRemoveAccountRights(
                policy_handle, user.windows_sid, 0, rights)
            user._invalidateToken()


# Create the singleton.
if process_capabilities.os_name == 'windows':
    os_administration = OSAdministrationWindows()
else:
    os_administration = OSAdministrationUnix()
