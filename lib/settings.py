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
    '''
    Settings wrapper
    '''

    config: ConfigParser = ConfigParser()
    '''
    INI parser
    '''

    su_program: str = 'sudo'
    '''
    sudo/doas
    '''

    autorun: bool = False
    '''
    If the install should run automatically
    '''

    aurman_path: str = '/tmp/aurman'
    '''
    Where to clone packages
    '''

    log_path: str = '/tmp/aurman.log'
    '''
    Where to store log file
    '''

    review_pkgbuild: bool = False
    '''
    Always review PKGBUILD
    '''

    def __init__(self, FILE: str = '/etc/aurman.conf') -> None:
        self.config.read(FILE)
        self.su_program = self.config.get('General', 'SU_PROGRAM', fallback='sudo')
        self.autorun = self.config.getboolean('General', 'AUTORUN', fallback=False)
        self.aurman_path = self.config.get('General', 'AURMAN_PATH', fallback='/tmp/aurman')
        self.log_path = self.config.get('General', 'LOG_PATH', fallback='/tmp/aurman.log')
        self.review_pkgbuild = self.config.getboolean('Install', 'REVIEW_PKGBUILD', fallback=False)

    def __repr__(self) -> str:
        return f"[General]\n"\
            f"  SU Program: {self.su_program}\n"\
            f"  Autorun: {self.autorun}\n"\
            f"  AURMan path: {self.aurman_path}\n"\
            f"  Log path: {self.log_path}"
