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


DOCUMENTATION = '''
---
module: sudoers
author: Alberto Re
version_added: 1.7.2
short_description: manage sudoers on system
description:
    - Add/remove users and groups from sudoers
options:
    name:
        required: true
        description:
            - Name of the user to add or edit
    state:
        required: false
        default: "present"
        choices: [ present, absent ]
        description:
            - Whether the entry should exist.  When C(absent), removes
              the sudoers entry.
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

SUDOERS_PATH='/etc/sudoers'

class Sudoers(object):
    def __init__(self, name, kind, host, password_required):
        self.name = name
        self.kind = kind
        self.host = host
        self.password_required = password_required

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

        pattern += ' ALL$'
        return pattern

    def readlines(self):
        f = open(SUDOERS_PATH, 'r')
        lines = f.readlines()
        f.close()
        return lines

    def kind_listed(self, exactly=False):
        try:
            lines = self.readlines()
        except IOError:
            module.fail_json(msg="%s is missing or not readable" % SUDOERS_PATH)       
        if exactly:
            pattern = self.get_strict_pattern()
            print 'strict pattern: %s' % pattern
        else:
            pattern = self.get_large_pattern()
            print 'large pattern: %s' % pattern

        for line in lines:
            stripped = line.strip()
            if stripped.startswith('#'):
                continue

            if re.match(pattern, stripped):
                return True

        return False

    def remove_user(self):
        lines = self.readlines()
        pattern = self.get_large_pattern()

        try:
            f = open(SUDOERS_PATH, 'w')

            for line in lines:
                if not re.match(pattern, line.strip()):
                    f.write(line)
            f.close()
        except IOError:
            module.fail_json(msg="%s is not writable" % SUDOERS_PATH)       

    def add_user(self):
        f = open(SUDOERS_PATH, 'a')
        if self.kind == 'user':
            entry = '%s' % self.name
        elif self.kind == 'group':
            entry = '%%%s' % self.name

        entry += ' %s=(ALL)' % self.host

        if not self.password_required:
            entry += ' NOPASSWD:'

        entry += ' ALL\n'
        f.write(entry)
        f.close()


def main():
    module = AnsibleModule(
        argument_spec=dict(
            name=dict(required=False),
            group=dict(required=False),
            host=dict(required=False, default='ALL'),
            state=dict(required=False, choices=['present', 'absent'],
                       default='present'),
            backup=dict(required=False, default=False),
            password_required=dict(required=False, default=True)
        ),
        supports_check_mode=False,
        required_one_of=[['name', 'group']],
        mutually_exclusive = [['name', 'group']]
    )

    args = dict(changed=False, failed=False,
                name=module.params['name'], state=module.params['state'],
                group=module.params['group'], backup=module.params['backup'],
                host=module.params['host'], nopasswd=module.params['password_required'])

    if args['name']:
        sudoers = Sudoers(args['name'], kind='user', host=args['host'], password_required=args['nopasswd'])
    elif args['group']:
        sudoers = Sudoers(args['group'], kind='group', host=args['host'], password_required=args['nopasswd'])

    is_listed = sudoers.kind_listed()
    is_listed_exactly= sudoers.kind_listed(True)

    if is_listed and args['state'] == 'absent':
        if args['backup']:
            module.backup_local(SUDOERS_PATH)
        sudoers.remove_user()
        args['changed'] = True
    elif is_listed and not is_listed_exactly and args['state'] == 'present':
        # to be optimized
        if args['backup']:
            module.backup_local(SUDOERS_PATH)
        sudoers.remove_user()
        sudoers.add_user()
        args['changed'] = True
    elif not is_listed and args['state'] == 'present':
        if args['backup']:
            module.backup_local(SUDOERS_PATH)
        sudoers.add_user()
        args['changed'] = True

    module.exit_json(**args)

# import module snippets
from ansible.module_utils.basic import *
main()
