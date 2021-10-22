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

import subprocess


def search_pacman(pkg: str) -> bool:
    procout = subprocess.run(['pacman', '-Ss', f'^{pkg}$'], stdout=subprocess.DEVNULL)
    return procout.returncode == 0


def get_package_version(pkg: str) -> str:
    procout = subprocess.run(['pacman', '-Qs', f'^{pkg}$'], stdout=subprocess.PIPE)
    if procout.returncode != 0:
        return ''

    return procout.stdout.decode().split(' ')[1].strip()


def remove_package(pkg: str, SU_PROGRAM: str = 'sudo') -> bool:
    procout = subprocess.run([SU_PROGRAM, 'pacman', '-R', pkg])
    return procout.returncode == 0
