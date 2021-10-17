# A Python 3 Arch Linux AUR CLI Manager
#
# Copyright 2021 Dhiego Cassiano Fogaça Barbosa <modscleo4@outlook.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import requests
import subprocess

from aurman import AURManException


def get_aur_package_info(pkg: list[str]) -> list:
    res = requests.get('https://aur.archlinux.org/rpc?v=5&type=info' + ''.join([f'&arg[]={p}' for p in pkg]))
    if res.status_code != 200:
        raise AURManException('Could not connect to AUR.')

    result = res.json()

    if result['resultcount'] == 0:
        return []

    return result['results']


def aur_installed_packages() -> list[str]:
    out = subprocess.run(['pacman', '-Qm'], stdout=subprocess.PIPE)
    if out.returncode != 0:
        return -1

    return map(lambda x: x.split(' '), out.stdout.decode().strip().split("\n"))
