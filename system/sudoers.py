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
    - Add or remove kernel modules from blacklist.
notes:
    - This module works on Debian and Ubuntu
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
requirements: []
'''

EXAMPLES = '''
# Give sudo permissions to 'john' from all hosts for all commands
- sudoers: name=john state=present

# Give sudo permissions to group 'bananas' from all hosts for all commands
- sudoers: group=bananas state=present
'''

SUDOERS_PATH='/etc/sudoers'

class Sudoers(object):
    def __init__(self, name, kind):
        self.name = name
        self.kind = kind

    def get_pattern(self):
        if self.kind == 'user':
            return '^%s ALL=(ALL) ALL$' % self.name
        elif self.kind == 'group':
            return '^%%%s ALL=(ALL) ALL$' % self.name

    def readlines(self):
        f = open(SUDOERS_PATH, 'r')
        lines = f.readlines()
        f.close()
        return lines

    def kind_listed(self):
        try:
            lines = self.readlines()
        except IOError:
            module.fail_json(msg="%s is missing or not readable" % SUDOERS_PATH)       
        pattern = self.get_pattern()

        for line in lines:
            stripped = line.strip()
            if stripped.startswith('#'):
                continue

            if re.match(pattern, stripped):
                return True

        return False

    def remove_user(self):
        lines = self.readlines()
        pattern = self.get_pattern()

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
            f.write('%s ALL=(ALL) ALL\n' % self.name)
        elif self.kind == 'group':
            f.write('%%%s ALL=(ALL) ALL\n' % self.name)


def main():
    module = AnsibleModule(
        argument_spec=dict(
            name=dict(required=False),
            group=dict(required=False),
            state=dict(required=False, choices=['present', 'absent'],
                       default='present'),
            blacklist_file=dict(required=False, default=None)
        ),
        supports_check_mode=False,
        required_one_of=[['name', 'group']],
        mutually_exclusive = [['name', 'group']]
    )

    args = dict(changed=False, failed=False,
                name=module.params['name'], state=module.params['state'],
                group=module.params['group'])

    if args['name']:
        sudoers = Sudoers(args['name'], kind='user')
    elif args['group']:
        sudoers = Sudoers(args['group'], kind='group')

    if sudoers.kind_listed():
        if args['state'] == 'absent':
            sudoers.remove_user()
            args['changed'] = True
    else:
        if args['state'] == 'present':
            sudoers.add_user()
            args['changed'] = True

    module.exit_json(**args)

# import module snippets
from ansible.module_utils.basic import *
main()
