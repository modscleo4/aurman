#!/usr/bin/python3

"""
A Python 3 Arch Linux AUR CLI Manager

Copyright 2021 Dhiego Cassiano Fogaça Barbosa <modscleo4@outlook.com>

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

AURMAN_PATH = '/tmp/aurman'

import sys
import requests
import subprocess
import argparse

class AURManException(Exception):
    pass


def search_pacman(pkg: str) -> bool:
    return subprocess.run(['pacman', '-Ss', f'^{pkg}$'], stdout=subprocess.DEVNULL).returncode == 0


def get_package_version(pkg: str) -> int:
    out = subprocess.run(['pacman', '-Qs', f'^{pkg}$'], stdout=subprocess.PIPE)
    if out.returncode != 0:
        return -1

    return out.stdout.decode().split(' ')[1].strip()


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
    if search_pacman(pkg):
        if dependency:
            return True

        print(f'The package {pkg} is on PacMan. Installing from there...')

        if subprocess.run(['sudo', 'pacman',  '-Su', '--needed', pkg]).returncode != 0:
            print(f'Error installing {pkg} from PacMan.')
            return False

        return True

    res = requests.get(f'https://aur.archlinux.org/rpc?v=5&type=info&arg[]={pkg}')
    if res.status_code != 200:
        print('FATAL: Could not connect to AUR.')
        raise AURManException('AUR Connection error.')

    result = res.json()

    if result['resultcount'] == 0:
        print(f'Package {pkg} not found.')
        if (input(f'Search {pkg} on AUR? [Y/n]: ').lower() != 'n'):
            raise AURManException('Package not found.')

        pkg = search_package(pkg, True)

    pkginfo = result['results'][0]
    if pkginfo['Version'] == get_package_version(pkg):
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
        print('Parsing dependencies...')
        for dep in pkginfo['Depends']:
            install_package(dep, True)

        print('')

    if (input(f'Continue installation of {pkg}? [Y/n]: ').lower() != 'n'):
        gitclone = subprocess.run(['git', 'clone', f'https://aur.archlinux.org/{pkg}.git', f'{AURMAN_PATH}/{pkg}'])
        if gitclone.returncode != 0:
            print(f'Could not clone {pkg} from git.')
            return False

        makepkg = subprocess.run(['makepkg', '-si', '--needed', '-p', '--asdeps' if dependency else ''], cwd=f'{AURMAN_PATH}/{pkg}')
        if makepkg.returncode != 0:
            print(f'Failed to install package {pkg}. Cleaning up.')

            if subprocess.run(['rm',  '-rf', f'{AURMAN_PATH}/{pkg}']).returncode != 0:
                print(f'Error removing {pkg} build files.')

            return False

        if subprocess.run(['rm',  '-rf', f'{AURMAN_PATH}/{pkg}']).returncode != 0:
            print(f'Error removing {pkg} build files.')

    return True


def main(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog='aurman', usage='%(prog)s [options] package_name', description='Python 3 AUR CLI Manager', epilog='Based on AUR RPC interface. Made by Modscleo4.')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-S', help='install provided packages', nargs='+')
    group.add_argument('-Q', help='search provided packages on AUR', nargs='+')

    arguments = parser.parse_args()

    if arguments.S != None:
        try:
            for pkg in arguments.S:
                if not install_package(pkg):
                    return 1
        except AURManException as e:
            print(e, file=sys.stderr)

    else:
        try:
            for pkg in arguments.Q:
                if not search_package(pkg):
                    return 1
        except AURManException as e:
            print(e, file=sys.stderr)

    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
