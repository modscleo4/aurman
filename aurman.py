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
from os import path, unlink
import re
import requests
import sys
import subprocess

from aurmanlib import aur, pacman
from aurmanlib.spinner import Spinner
from aurmanlib.settings import Settings

settings: Settings = Settings()


class AURManException(Exception):
    pass


@dataclass(eq=True)
class Package:
    id: int
    name: str
    description: str
    version: str
    maintainer: str
    base_package: str
    dependencies: list[str]
    make_dependencies: list[str]
    opt_dependencies: list[str]
    check_dependencies: list[str]
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
        self.base_package = pkginfo['PackageBase']
        self.dependencies = pkginfo['Depends']
        self.make_dependencies = pkginfo['MakeDepends']
        self.opt_dependencies = pkginfo['OptDepends']
        self.check_dependencies = pkginfo['CheckDepends']
        self.aur_dependencies = []

        if parse_dependencies:
            aur_deps: list[str] = []
            for pkg in self.dependencies + self.make_dependencies + self.check_dependencies:
                pkg = parse_version(pkg)
                if pacman.search_pacman(pkg):
                    continue

                aur_deps.append(pkg)

            if aur_deps:
                self.aur_dependencies += [Package(p) for p in aur.get_aur_package_info(aur_deps) if p]

    def __repr__(self) -> str:
        return (f"  Package: {self.name}\n" +
                f"  Description: {self.description}\n" +
                f"  Version: {self.version}\n" +
                f"  Maintainer: {self.maintainer}\n" +
                f"  Dependencies: {', '.join(self.dependencies + [f'{x} (make)' for x in self.make_dependencies] + [f'{x} (check)' for x in self.check_dependencies]) or 'None'}")

    def __gt__(self, other: Package) -> bool:
        return self.popularity > other.popularity

    def get_aur_deps(self) -> list[Package]:
        return [p for p in (self.aur_dependencies + [x.get_aur_deps() for x in self.aur_dependencies]) if p]


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
    PKG_PATH = f'{settings.aurman_path}/{pkg}'

    if pacman.search_pacman(pkg):
        if dependency:
            return True

        if (settings.autorun or input(f' :: The package {pkg} is on PacMan. Install from there? [Y/n]: ').lower() != 'n'):
            procout = subprocess.run([settings.su_program, 'pacman',  '-Su', '--asdeps', '--needed', pkg])
            if procout.returncode != 0:
                print(f'Error installing {pkg} from PacMan.')
                return False

            return True

    pkginfo = aur.get_aur_package_info([pkg])[0]
    if not pkginfo:
        print(f'Package {pkg} not found.')
        if (input(f' :: Search {pkg} on AUR? [Y/n]: ').lower() == 'n'):
            raise AURManException(f'Package {pkg} not found.')

        pkginfo = aur.get_aur_package_info([search_package(pkg, True)])[0]

    with Spinner():
        package: Package = Package(pkginfo)

    if package.version == pacman.get_package_version(pkg):
        print(f" => Skipping {pkg}: Already installed and updated (version {package.version}).")
        return True

    print(package)
    print('')

    if (dependency or settings.autorun or input(f' :: Continue installation of {pkg}? [Y/n]: ').lower() != 'n'):
        if deps := package.get_aur_deps():
            print(f' => Processing dependencies of {pkg}...')
            for dep in deps:
                if not install_package(dep.name, True):
                    return False

        procout = subprocess.run(['git', 'clone', f'https://aur.archlinux.org/{package.base_package}.git', PKG_PATH])
        if procout.returncode:
            print(f'Could not clone {pkg} from git.')
            return False

        procout = subprocess.run(
            ['makepkg', '--needed', '-sir'] +
            (['--asdeps'] if dependency else []) +
            (['--noconfirm'] if settings.autorun else []), cwd=PKG_PATH)
        if procout.returncode:
            print(f'Failed to install package {pkg}. Cleaning up.')

            procout = subprocess.run(['rm',  '-rf', PKG_PATH])
            if procout.returncode != 0:
                print(f'Error removing {pkg} build files.')

            return False

        procout = subprocess.run(['rm',  '-rf', PKG_PATH])
        if procout.returncode != 0:
            print(f'Error removing {pkg} build files.')

    return True


def update_packages():
    pkgs = aur.aur_installed_packages()
    for [pkg, ver] in pkgs:
        pkginfo = aur.get_aur_package_info([pkg])[0]
        if not pkginfo:
            continue

        if pkginfo['Version'] != ver:
            install_package(pkg)


def list_packages():
    print("\n".join(map(lambda x: f'{x[0]}: {x[1]}', aur.aur_installed_packages())))


def update_package_cache(cache_version: bool = False) -> bool:
    STEP = 200
    if path.exists(f'{settings.aurman_path}/packages.gz'):
        unlink(f'{settings.aurman_path}/packages.gz')

    with open(f'{settings.aurman_path}/packages.gz', 'wb') as f:
        procout = subprocess.run(['curl', 'https://aur.archlinux.org/packages.gz'], cwd=settings.aurman_path, stdout=f)
        if procout.returncode != 0:
            return False

    procout = subprocess.run(['gzip', '-cd', 'packages.gz'], cwd=settings.aurman_path, stdout=subprocess.PIPE)
    if procout.returncode != 0:
        return False

    packages = procout.stdout.decode().strip().split("\n")[1:]
    packages.sort()

    with open(f'{settings.aurman_path}/packages.txt', 'w') as f:
        for i in range(0, len(packages) - 1, STEP):
            pkgs = packages[i:i + STEP]
            if cache_version:
                pkginfo = aur.get_aur_package_info(pkgs)
                for pkg in pkginfo:
                    f.write(f"{pkg['Name']}: {pkg['Version']}\n")
            else:
                for pkg in pkgs:
                    f.write(f"{pkg}\n")

    return True


def main(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog='aurman',
                                     usage='%(prog)s [options]',
                                     description='Python 3 AUR CLI Manager',
                                     epilog='Based on AUR RPC interface. Made by Modscleo4.')

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-y', help='update package cache', action='store_true')
    group.add_argument('-S', help='install provided packages', nargs='+', metavar='pkg')
    group.add_argument('-Q', help='list installed packages', action='store_true')
    group.add_argument('-s', help='search provided packages on AUR', nargs='+', metavar='pkg')
    group.add_argument('-u', help='update installed packages', action='store_true')

    arguments = parser.parse_args()

    try:
        if arguments.y:
            if not update_package_cache():
                return 1
        elif arguments.S:
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
    except Exception as e:
        print(f"FATAL: Unknown Exception\n\n{e}", file=sys.stderr)

    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
