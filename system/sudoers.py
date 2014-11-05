#!/usr/bin/python
# encoding: utf-8 -*-

# (c) 2014, Alberto Re <alberto.re@gmail.com>
#
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

import os
import re
import shutil


DOCUMENTATION = '''
---
module: sudoers
author: Alberto Re <alberto.re@gmail.com>
version_added: 1.8
short_description: basic management of sudoers configuration
description:
    - Add/remove users and groups from sudoers
    - Compatible with visudo (8) locking
    - Basic sanity checks (visudo -cf ) are done before writing changes
    - Could operate on the main sudoers file (if you feel brave) or in a
      custom one under sudoers.d
options:
    name:
        required: false
        description:
            - Name of the user to add or edit
    group:
        required: false
        description:
            - Name of the group to add or edit
    state:
        required: false
        default: "present"
        choices: [ present, absent ]
        description:
            - Whether the entry should exist.  When C(absent), removes
              the sudoers entry.
    host:
        required: false
        default: "ALL"
        description:
            - Host from which commands are allower for the user (or group).
              Could be an alias or a valid host(s) definition
    password_required:
        required: false
        default: yes
        choices: [ yes, no ]
        description:
            - Whether the user should provide a password or not when using sudo
    backup:
        required: false
        default: "no"
        choices: [ "yes", "no" ]
        description:
            - Create a backup file including the timestamp information so you can get
              the original file back if you somehow clobbered it incorrectly.
    cfg_file:
        required: false
        default: null
        description:
            - the name of the file under the sudoers.d directory to edit in
              place of the main configuration file
requirements: []
'''

EXAMPLES = '''
# Give sudo permissions to 'john' from all hosts for all commands
- sudoers: name=john state=present

# Give sudo permissions to group 'bananas' from all hosts for all commands
- sudoers: group=bananas state=present

# Give sudo permissions to 'lime' from all hosts for all commands and backup file prior to changes
- sudoers: name=lime state=present backup=yes

# Give sudo permissions to group 'watermeleons' from all hosts for all commands 
  without prompting for password and backup file prior to changes
- sudoers: group=watermeleons state=present backup=yes password_required=no

# Give sudo permissions to user 'cucumber' from host example.local for all commands
- sudoers: user=cucumber host=example.local state=present

'''

class Sudoers(object):
    """Basic class for sudoers manipulation
    """

    platform = 'Generic'
    distribution = None

    def __new__(cls, *args, **kwargs):
        return load_platform_subclass(Sudoers, args, kwargs)

    def __init__(self, name, kind, host, password_required,
                 commands, cfg_file):
        self.name = name
        self.kind = kind
        self.host = host
        self.password_required = password_required
        self.commands = commands
        self.cfg_file = cfg_file
        self.set_platform_specific_paths()
        if self.cfg_file:
            self.sudoers_path = '%s/%s' % (self.sudoers_dir_path, self.cfg_file)
        self.sudoers_tmp_path = '%s.tmp' % self.sudoers_path

    def set_platform_specific_paths(self):
        self.sudoers_path = '/etc/sudoers'
        self.sudoers_dir_path = '/etc/sudoers.d'

    def lock(self):
        if os.path.isfile(self.sudoers_tmp_path):
            raise IOError()
        # shutil also throws an IOError
        shutil.copyfile(self.sudoers_path, self.sudoers_tmp_path)
        os.chmod(self.sudoers_tmp_path, 0440)

    def rollback(self):
        os.remove(self.sudoers_tmp_path)

    def commit(self):
        if os.system('visudo -c -f %s' % self.sudoers_tmp_path) != 0:
            raise Exception('invalid syntax detected')

        shutil.move(self.sudoers_tmp_path, self.sudoers_path)

    def get_large_pattern(self):
        if self.kind == 'user':
            return '^%s' % self.name
        elif self.kind == 'group':
            return '^%%%s' % self.name

    def get_strict_pattern(self):
        if self.kind == 'user':
            pattern = '^%s' % self.name
        elif self.kind == 'group':
            pattern = '^%%%s' % self.name

        pattern += ' %s=' % self.host

        pattern += '\(ALL\)'

        if not self.password_required:
            pattern += ' NOPASSWD:'

        pattern += ' %s$' % self.commands
        return pattern

    def readlines(self):
        f = open(self.sudoers_path, 'r')
        lines = f.readlines()
        f.close()
        return lines

    def create_cfg_file(self):
        f = open(self.sudoers_path, 'w')
        f.close()

    def is_listed(self):
        (listed, listed_exactly) = (False, False)

        if self.cfg_file:
            if not os.path.isfile(self.sudoers_tmp_path):
                self.create_cfg_file()
            else:
                raise('%s is missing' % self.cfg_file)

        lines = self.readlines()
        large_pattern = self.get_large_pattern()
        strict_pattern = self.get_strict_pattern()

        for line in lines:
            stripped = line.strip()
            if stripped.startswith('#'):
                continue

            if re.match(strict_pattern, stripped):
                listed = True
                listed_exactly = True
            elif re.match(large_pattern, stripped):
                listed = True

        return (listed, listed_exactly)

    def remove_user(self):
        lines = self.readlines()
        pattern = self.get_large_pattern()

        f = open(self.sudoers_tmp_path, 'w')

        for line in lines:
            if not re.match(pattern, line.strip()):
                f.write(line)
        f.close()

    def add_user(self):
        f = open(self.sudoers_tmp_path, 'a')
        if self.kind == 'user':
            entry = '%s' % self.name
        elif self.kind == 'group':
            entry = '%%%s' % self.name

        entry += ' %s=(ALL)' % self.host

        if not self.password_required:
            entry += ' NOPASSWD:'

        entry += ' %s\n' % self.commands
        f.write(entry)
        f.close()

class FreeBsdSudoers(Sudoers):
    """FreeBSD specific class
    """

    platform = 'FreeBSD'
    distribution = None

    def set_platform_specific_paths(self):
        self.sudoers_path = '/usr/local/etc/sudoers'
        self.sudoers_dir_path = '/usr/local/etc/sudoers.d'


def main():
    module = AnsibleModule(
        argument_spec=dict(
            name=dict(required=False, type='str', aliases=['user']),
            group=dict(required=False, type='str'),
            host=dict(required=False, default='ALL', type='str'),
            commands=dict(required=False, default='ALL', type='str'),
            state=dict(required=False, choices=['present', 'absent'],
                       default='present', type='str'),
            backup=dict(required=False, default='no', type='bool'),
            password_required=dict(required=False, default='yes', type='bool'),
            cfg_file=dict(required=False, default=None, type='str')
        ),
        supports_check_mode=False,
        required_one_of=[['name', 'group']],
        mutually_exclusive = [['name', 'group']]
    )

    args = dict(changed=False, failed=False,
                name=module.params['name'], state=module.params['state'],
                group=module.params['group'], backup=module.params['backup'],
                host=module.params['host'], password_required=module.params['password_required'],
                commands=module.params['commands'], cfg_file=module.params['cfg_file'])

    if args['name']:
        sudoers = Sudoers(args['name'], kind='user', host=args['host'],
                          password_required=args['password_required'],
                          commands=args['commands'], cfg_file=args['cfg_file'])
    elif args['group']:
        sudoers = Sudoers(args['group'], kind='group', host=args['host'],
                          password_required=args['password_required'],
                          commands=args['commands'], cfg_file=args['cfg_file'])

    try:
        (listed, listed_exactly) = sudoers.is_listed()
    except Exception, ex:
        module.fail_json(msg="sudoers file is missing, detailed error: %s" % str(ex))

    if listed and args['state'] == 'absent':
        try:
            sudoers.lock()
        except IOError:
            module.fail_json(msg="sudoers is locked by another user")

        if args['backup']:
            module.backup_local(sudoers.sudoers_path)

        try:
            sudoers.remove_user()
            sudoers.commit()
            args['changed'] = True
        except Exception, ex:
            sudoers.rollback()
            module.fail_json(msg="commit failed: %s" % str(ex))

    elif listed and not listed_exactly and args['state'] == 'present':
        try:
            sudoers.lock()
        except IOError:
            module.fail_json(msg="sudoers is locked by another user")

        if args['backup']:
            module.backup_local(sudoers.sudoers_path)

        try:
            sudoers.remove_user()
            sudoers.add_user()
            sudoers.commit()
            args['changed'] = True
        except Exception, ex:
            sudoers.rollback()
            module.fail_json(msg="commit failed: %s" % str(ex))

    elif not listed and args['state'] == 'present':
        try:
            sudoers.lock()
        except IOError:
            module.fail_json(msg="sudoers is locked by another user")

        if args['backup']:
            module.backup_local(sudoers.sudoers_path)

        try:
            sudoers.add_user()
            sudoers.commit()
            args['changed'] = True
        except Exception, ex:
            sudoers.rollback()
            module.fail_json(msg="commit failed: %s" % str(ex))

    module.exit_json(**args)

# import module snippets
from ansible.module_utils.basic import *
main()
