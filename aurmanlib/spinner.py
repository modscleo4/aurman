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
#
# From https://stackoverflow.com/a/58174909


import sys
import threading
import itertools
import time
from typing import Iterable


class Spinner:
    spinner: Iterable[str]
    delat: float
    busy: bool
    visible: bool
    _screen_lock: threading.Lock
    thread: threading.Thread

    def __init__(self, message: str = '', delay: float = 0.1):
        self.spinner = itertools.cycle(['-', '\\', '|', '/'])
        self.delay = delay
        self.busy = False
        self.visible = False
        sys.stdout.write(message)

    def write_next(self):
        with self._screen_lock:
            if not self.visible:
                sys.stdout.write(next(self.spinner))
                self.visible = True
                sys.stdout.flush()

    def remove_spinner(self, cleanup: bool = False):
        with self._screen_lock:
            if self.visible:
                sys.stdout.write('\b')
                self.visible = False
                if cleanup:
                    sys.stdout.write(' ')       # overwrite spinner with blank
                    sys.stdout.write('\r')      # move to next line
                sys.stdout.flush()

    def spinner_task(self):
        while self.busy:
            self.write_next()
            time.sleep(self.delay)
            self.remove_spinner()

    def __enter__(self):
        if sys.stdout.isatty():
            self._screen_lock = threading.Lock()
            self.busy = True
            self.thread = threading.Thread(target=self.spinner_task)
            self.thread.start()

    def __exit__(self, exception, value, tb):
        if sys.stdout.isatty():
            self.busy = False
            self.remove_spinner(cleanup=True)
        else:
            sys.stdout.write('\r')
