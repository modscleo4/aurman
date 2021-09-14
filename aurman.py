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

import argparse
import subprocess
import requests
import sys

import aur
import pacman

# Where to clone packages
AURMAN_PATH = '/tmp/aurman'


class AURManException(Exception):
    pass


def search_package(q: str, select: bool = False) -> str:
    res = requests.get(f'https://aur.archlinux.org/rpc?v=5&type=search&arg={q}')
    if res.status_code != 200:
        print('FATAL: Could not connect to AUR.')
        raise AURManException('AUR Connection error.')

    result = res.json()
    if result['resultcount'] == 0:
        print(f'Package {q} not found.')
        raise AURManException('Package not found.')

    print(f'Search results for {q}:')

    result['results'].sort(reverse=True, key=lambda x: x['Popularity'])

    for pkginfo in result['results']:
        print(f"  ID: {pkginfo['ID']}")
        print(f"  Package: {pkginfo['Name']}")
        print(f"  Description: {pkginfo['Description']}")
        print(f"  Version: {pkginfo['Version']}")
        print(f"  Maintainer: {pkginfo['Maintainer']}")
        print(f"  Popularity: {pkginfo['Popularity']}")
        print('')

    if select:
        while True:
            pkg = input('Please type the desired package name: ')
            if len(list(filter(lambda p: p['Name'] == pkg, result['results']))) != 0:
                return pkg

            print(f'Package {pkg} not found in search results.')

    return ''


def install_package(pkg: str, dependency: bool = False) -> bool:
    PKG_PATH = f'{AURMAN_PATH}/{pkg}'

    if pacman.search_pacman(pkg):
        if dependency:
            return True

        if (input(f'The package {pkg} is on PacMan. Install from there? [Y/n]: ').lower() != 'n'):
            procout = subprocess.run(['sudo', 'pacman',  '-Su', '--needed', pkg])
            if procout.returncode != 0:
                print(f'Error installing {pkg} from PacMan.')
                return False

            return True

    pkginfo = aur.get_aur_package_info(pkg)
    if pkginfo is None:
        print(f'Package {pkg} not found.')
        if (input(f'Search {pkg} on AUR? [Y/n]: ').lower() != 'n'):
            raise AURManException('Package not found.')

        pkg = search_package(pkg, True)

    if pkginfo['Version'] == pacman.get_package_version(pkg):
        print(f"Skipping {pkg}: Already installed and updated (version {pkginfo['Version']}).")
        return True

    if not 'Depends' in pkginfo:
        pkginfo['Depends'] = []

    print(f"  Package: {pkginfo['Name']}")
    print(f"  Description: {pkginfo['Description']}")
    print(f"  Version: {pkginfo['Version']}")
    print(f"  Maintainer: {pkginfo['Maintainer']}")
    print(f"  Dependencies: {', '.join(pkginfo['Depends'])}")
    print('')

    if pkginfo['Depends']:
        print('Processing dependencies...')
        for dep in pkginfo['Depends']:
            install_package(dep, True)

        print('')

    if (input(f'Continue installation of {pkg}? [Y/n]: ').lower() != 'n'):
        procout = subprocess.run(['git', 'clone', f'https://aur.archlinux.org/{pkg}.git', PKG_PATH])
        if procout.returncode != 0:
            print(f'Could not clone {pkg} from git.')
            return False

        procout = subprocess.run(['makepkg', '--needed', '-si'], cwd=PKG_PATH)
        if procout.returncode != 0:
            print(f'Failed to install package {pkg}. Cleaning up.')

            if subprocess.run(['rm',  '-rf', PKG_PATH]).returncode != 0:
                print(f'Error removing {pkg} build files.')

            return False

        procout = subprocess.run(['rm',  '-rf', PKG_PATH])
        if procout.returncode != 0:
            print(f'Error removing {pkg} build files.')

    return True


def update_packages():
    pkgs = aur.aur_installed_packages()
    for [pkg, ver] in pkgs:
        pkginfo = aur.get_aur_package_info(pkg)
        if pkginfo != None:
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
        if arguments.S != None:
            for pkg in arguments.S:
                if not install_package(pkg):
                    return 1
        elif arguments.Q:
            list_packages()
        elif arguments.s != None:
            for pkg in arguments.s:
                if not search_package(pkg):
                    return 1
        elif arguments.u:
            if not update_packages():
                return 1
    except AURManException as e:
        print(f'FATAL: {e}', file=sys.stderr)
    except Exception as e:
        print(f"FATAL: Unknown Exception\n\n{e}", file=sys.stderr)

    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
