#!/usr/bin/python3

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

from __future__ import annotations

import argparse
from dataclasses import dataclass
import re
import requests
import sys
import subprocess

import aur
import pacman
from spinner import Spinner

# Where to clone packages
AURMAN_PATH = '/tmp/aurman'


class AURManException(Exception):
    pass


@dataclass(eq=True)
class Package:
    id: int
    name: str
    description: str
    version: str
    maintainer: str
    dependencies: list[str]
    aur_dependencies: list[Package]
    popularity: float

    def __init__(self, pkginfo, parse_dependencies: bool = True) -> None:
        if not 'Depends' in pkginfo:
            pkginfo['Depends'] = []

        if not 'MakeDepends' in pkginfo:
            pkginfo['MakeDepends'] = []

        if not 'OptDepends' in pkginfo:
            pkginfo['OptDepends'] = []

        if not 'CheckDepends' in pkginfo:
            pkginfo['CheckDepends'] = []

        self.id = pkginfo['ID']
        self.name = pkginfo['Name']
        self.description = pkginfo['Description']
        self.version = pkginfo['Version']
        self.maintainer = pkginfo['Maintainer']
        self.popularity = pkginfo['Popularity']
        self.dependencies = pkginfo['Depends']
        self.make_dependencies = pkginfo['MakeDepends']
        self.opt_dependencies = pkginfo['OptDepends']
        self.check_dependencies = pkginfo['CheckDepends']
        self.aur_dependencies = []

        if parse_dependencies:
            for pkg in self.dependencies + self.make_dependencies + self.check_dependencies:
                pkg = parse_version(pkg)
                if pacman.search_pacman(pkg):
                    continue

                self.aur_dependencies.append(Package(aur.get_aur_package_info(pkg)))

    def __repr__(self) -> str:
        return (f"  Package: {self.name}\n" +
                f"  Description: {self.description}\n" +
                f"  Version: {self.version}\n" +
                f"  Maintainer: {self.maintainer}\n" +
                f"  Dependencies: {', '.join(self.dependencies + [f'{x} (make)' for x in self.make_dependencies] + [f'{x} (check)' for x in self.check_dependencies]) or 'None'}")

    def __gt__(self, other: Package) -> bool:
        return self.popularity > other.popularity

    def get_aur_deps(self):
        return [x for x in (self.aur_dependencies + [x.get_aur_deps() for x in self.aur_dependencies]) if x]


class SearchResult(Package):
    def __repr__(self) -> str:
        return (f"  ID: {self.id}\n" +
                f"  Package: {self.name}\n" +
                f"  Description: {self.description}\n" +
                f"  Version: {self.version}\n" +
                f"  Maintainer: {self.maintainer}\n" +
                f"  Popularity: {self.popularity}")


def parse_version(pkg):
    match = re.search('^[^<>=!]*', pkg)
    return match.group() if match else ''


def search_package(q: str, select: bool = False) -> str:
    res = requests.get(f'https://aur.archlinux.org/rpc?v=5&type=search&arg={q}')
    if res.status_code != 200:
        raise AURManException('Could not connect to AUR.')

    result = res.json()
    if result['resultcount']:
        raise AURManException(f'Package {q} not found.')

    results: list[Package] = [SearchResult(x, False) for x in result['results']]
    results.sort(reverse=True)

    print(f'Search results for {q}:')
    for package in results:
        print(package)
        print()

    if select:
        while True:
            pkg = input(' :: Please type the desired package name: ')
            if [x for x in results if x.name == pkg]:
                return pkg

            print(f'Package {pkg} not found in search results.')

    return ''


def install_package(pkg: str, dependency: bool = False) -> bool:
    PKG_PATH = f'{AURMAN_PATH}/{pkg}'

    if pacman.search_pacman(pkg):
        if dependency:
            return True

        if (input(f' :: The package {pkg} is on PacMan. Install from there? [Y/n]: ').lower() != 'n'):
            procout = subprocess.run(['sudo', 'pacman',  '-Su', '--needed', pkg])
            if procout.returncode != 0:
                print(f'Error installing {pkg} from PacMan.')
                return False

            return True

    pkginfo = aur.get_aur_package_info(pkg)
    if not pkginfo:
        print(f'Package {pkg} not found.')
        if (input(f' :: Search {pkg} on AUR? [Y/n]: ').lower() == 'n'):
            raise AURManException(f'Package {pkg} not found.')

        pkginfo = aur.get_aur_package_info(search_package(pkg, True))

    # spinner.start()
    with Spinner():
        package: Package = Package(pkginfo)
    # spinner.stop()

    if package.version == pacman.get_package_version(pkg):
        print(f"Skipping {pkg}: Already installed and updated (version {package.version}).")
        return True

    print(package)
    print('')

    if (input(f' :: Continue installation of {pkg}? [Y/n]: ').lower() != 'n'):
        if deps := package.get_aur_deps():
            print('Processing dependencies...')
            for dep in deps:
                if not install_package(dep.name, True):
                    return False

        procout = subprocess.run(['git', 'clone', f'https://aur.archlinux.org/{pkg}.git', PKG_PATH])
        if procout.returncode:
            print(f'Could not clone {pkg} from git.')
            return False

        procout = subprocess.run(['makepkg', '--needed', '-si'], cwd=PKG_PATH)
        if procout.returncode:
            print(f'Failed to install package {pkg}. Cleaning up.')

            if subprocess.run(['rm',  '-rf', PKG_PATH]).returncode != 0:
                print(f'Error removing {pkg} build files.')

            return False

        procout = subprocess.run(['rm',  '-rf', PKG_PATH])
        if procout.returncode != 0:
            print(f'Error removing {pkg} build files.')

        if (package.make_dependencies and input(f' :: Remove {pkg} Make Dependencies? [Y/n]: ').lower() != 'n'):
            for dep in package.make_dependencies:
                if not pacman.remove_package(dep):
                    print(f'Error removing {dep}.')

        if (package.check_dependencies and input(f' :: Remove {pkg} Check Dependencies? [Y/n]: ').lower() != 'n'):
            for dep in package.check_dependencies:
                if not pacman.remove_package(dep):
                    print(f'Error removing {dep}.')

    return True


def update_packages():
    pkgs = aur.aur_installed_packages()
    for [pkg, ver] in pkgs:
        pkginfo = aur.get_aur_package_info(pkg)
        if not pkginfo:
            continue

        if pkginfo['Version'] != ver:
            install_package(pkg)


def list_packages():
    print("\n".join(map(lambda x: f'{x[0]}: {x[1]}', aur.aur_installed_packages())))


def main(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog='aurman',
                                     usage='%(prog)s [options]',
                                     description='Python 3 AUR CLI Manager',
                                     epilog='Based on AUR RPC interface. Made by Modscleo4.')

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-S', help='install provided packages', nargs='+', metavar='pkg')
    group.add_argument('-Q', help='list installed packages', action='store_true')
    group.add_argument('-s', help='search provided packages on AUR', nargs='+', metavar='pkg')
    group.add_argument('-u', help='update installed packages', action='store_true')

    arguments = parser.parse_args()

    try:
        if arguments.S:
            for pkg in arguments.S:
                if not install_package(pkg):
                    return 1
        elif arguments.Q:
            list_packages()
        elif arguments.s:
            for pkg in arguments.s:
                if not search_package(pkg):
                    return 1
        elif arguments.u:
            if not update_packages():
                return 1
    except AURManException as e:
        print(f'FATAL: {e}', file=sys.stderr)
    # except Exception as e:
    #    print(f"FATAL: Unknown Exception\n\n{e}", file=sys.stderr)

    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
