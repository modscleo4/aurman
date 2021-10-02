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

from configparser import ConfigParser


class Settings:
    config: ConfigParser = ConfigParser()

    # Sudo
    su_program: str = '/usr/bin/sudo'

    # If the install should run automatically
    autorun: bool = False

    # Where to clone packages
    aurman_path: str = '/tmp/aurman'

    def __init__(self, FILE: str = '/etc/aurman.conf') -> None:
        self.config.read(FILE)
        self.su_program = self.config.get('GENERAL', 'SU_PROGRAM', fallback='/usr/bin/sudo')
        self.autorun = self.config.getboolean('GENERAL', 'AUTORUN', fallback=False)
        self.aurman_path = self.config.get('GENERAL', 'AURMAN_PATH', fallback='/tmp/aurman')
