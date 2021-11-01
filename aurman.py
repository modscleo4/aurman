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
import logging
from os import path, unlink
from packaging import version
import requests
from simple_term_menu import TerminalMenu
import sys
import subprocess

from lib.util import AURManException, __version__
from lib import aur, pacman, util, gpg
from lib.spinner import Spinner
from lib.settings import Settings

settings: Settings = Settings()


logging.basicConfig(filename=settings.log_path, level=logging.DEBUG)


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
                pkg = util.remove_version_constraint(pkg)
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
                "  Dependencies: " + ', '.join(
                    [util.color_text(f"{x}", util.color_from_version(x)) for x in self.dependencies] +
                    [util.color_text(f"{x} (make)", util.color_from_version(x)) for x in self.make_dependencies] +
                    [util.color_text(f"{x} (check)", util.color_from_version(x)) for x in self.check_dependencies]) or 'None')

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


def search_package(q: str, select: bool = False) -> str:
    '''
    Searches for a package.
    '''
    res = requests.get(f"https://aur.archlinux.org/rpc?v=5&type=search&arg={q}")
    if res.status_code != 200:
        raise AURManException('Could not connect to AUR.')

    result = res.json()
    if not result['resultcount']:
        raise AURManException(f"Package {q} not found.")

    results: list[Package] = [SearchResult(x, False) for x in result['results']]
    results.sort(reverse=True)

    if select:
        return results[TerminalMenu(map(lambda x: f"{x.name}: {x.description}", results)).show()].name
    else:
        util.info(f"Search results for {q}: ")
        for package in results:
            print(package)
            print()

    return ''


def install_packages(pkg: str, show_pkgbuild: bool = False, dependency: bool = False) -> bool:
    '''
    Install a package.
    '''
    PKG_PATH = f"{settings.aurman_path}/{pkg}"

    if pacman.search_pacman(pkg):
        if dependency:
            return True

        if settings.autorun or util.prompt(f"The package {pkg} is on pacman. Install from there?"):
            procout = subprocess.run([settings.su_program, 'pacman',  '-Su', '--asdeps', '--needed', pkg])
            if procout.returncode != 0:
                util.error(f"Error installing {pkg} from pacman.")
                return False

            return True

    pkginfos = aur.get_aur_package_info([pkg])
    if not pkginfos:
        util.warning(f"Package {pkg} not found.")
        if not util.prompt(f"Search {pkg} on AUR?"):
            raise AURManException(f"Package {pkg} not found.")

        pkginfos = aur.get_aur_package_info([search_package(pkg, True)])

    pkginfo = pkginfos[0]

    with Spinner():
        package: Package = Package(pkginfo)

    force: bool = False
    try:
        if version.parse(package.version) <= version.parse(ver := pacman.get_package_version(package.name)):
            if not util.prompt(f"The package {package.name} is already updated. Continue anyway?", default='n'):
                util.warning(f"Skipping {package.name}: Already installed and updated (version {ver}).")
                return True
            force = True
    except:
        raise AURManException(f"Invalid version info for package {package.name}.")

    print(package)
    print('')

    if dependency or settings.autorun or util.prompt(f"Continue installation of {package.name}?"):
        procout = subprocess.run(['rm',  '-rf', PKG_PATH], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        if deps := package.get_aur_deps():
            util.info(f"Processing dependencies of {package.name}...")
            for dep in deps:
                if not install_packages(dep.name, show_pkgbuild, dependency=True):
                    return False

        procout = subprocess.run(['git', 'clone', f"https://aur.archlinux.org/{package.base_package}.git", PKG_PATH])
        if procout.returncode:
            util.error(f"Could not clone {package.name} from git.")
            return False

        if show_pkgbuild:
            procout = subprocess.run(['less', 'PKGBUILD'], cwd=PKG_PATH)
            if not util.prompt(f"Continue installation of {package.name}?"):
                return False

        procout = subprocess.run(
            ['makepkg', '-sir'] +
            (['--needed'] if not force else []) +
            (['--asdeps'] if dependency else []) +
            (['--noconfirm'] if settings.autorun else []), cwd=PKG_PATH)
        if procout.returncode:
            util.error(f"Failed to install package {package.name}. Cleaning up.")

            procout = subprocess.run(['rm',  '-rf', PKG_PATH])
            if procout.returncode != 0:
                util.error(f"Error removing {package.name} build files.")

            return False

        procout = subprocess.run(['rm',  '-rf', PKG_PATH])
        if procout.returncode != 0:
            util.error(f"Error removing {package.name} build files.")

        return True

    return False


def update_packages():
    '''
    Updates all installed packages.
    '''
    STEP = 200

    aur_packages: list[list[str]] = aur.aur_installed_packages()
    if not aur_packages:
        return False

    packages: list[Package] = []
    for i in range(0, len(aur_packages) - 1, STEP):
        pkgs = [x[0] for x in aur_packages[i:i + STEP]]
        packages += [Package(_, False) for _ in aur.get_aur_package_info(pkgs)]

    to_update: list[Package] = [x for x in packages if version.parse(next((_[1] for _ in aur_packages if _[0] == x.name))) < version.parse(x.version)]
    if not to_update:
        util.info('No packages to update.')
        return True

    util.info('The following packages will be updated: ' + ', '.join(map(lambda x: x.name, to_update)))

    for package in to_update:
        if not install_packages(package.name, show_pkgbuild=settings.review_pkgbuild):
            return False


def list_packages():
    '''
    List all AUR installed packages.
    '''
    STEP = 200

    aur_packages: list[list[str]] = aur.aur_installed_packages()
    if not aur_packages:
        return False

    packages: list[Package] = []
    for i in range(0, len(aur_packages) - 1, STEP):
        pkgs = [x[0] for x in aur_packages[i:i + STEP]]
        packages += [Package(_, False) for _ in aur.get_aur_package_info(pkgs)]

    print("\n".join(map(lambda x: f"{x.name}: " + util.color_text(ver := next((_[1] for _ in aur_packages if _[0] == x.name)), util.COLORS.white if (version.parse(ver) >= version.parse(x.version)) else util.COLORS.magenta), packages)))


def update_package_cache(cache_version: bool = False) -> bool:
    '''
    Updates the package cache (packages.txt).
    '''
    STEP = 200
    if path.exists(f"{settings.aurman_path}/packages.gz"):
        unlink(f"{settings.aurman_path}/packages.gz")

    with open(f"{settings.aurman_path}/packages.gz", 'wb') as f:
        procout = subprocess.run(['curl', 'https://aur.archlinux.org/packages.gz'], cwd=settings.aurman_path, stdout=f)
        if procout.returncode != 0:
            return False

    procout = subprocess.run(['gzip', '-cd', 'packages.gz'], cwd=settings.aurman_path, stdout=subprocess.PIPE)
    if procout.returncode != 0:
        return False

    packages = procout.stdout.decode().strip().split("\n")[1:]
    packages.sort()

    with open(f"{settings.aurman_path}/packages.txt", 'w') as f:
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


def show_config() -> bool:
    print(settings)
    return True


def main(args: list[str]) -> int:
    '''
    Entry point for aurman.
    '''
    parser = argparse.ArgumentParser(prog=args[0],
                                     usage='%(prog)s [options]',
                                     description='Python 3 AUR CLI Manager',
                                     epilog='Based on AUR RPC interface. Made by Modscleo4.')

    parser.add_argument('-v', '--version', action='version', version='%(prog)s ' + __version__)
    parser.add_argument('-i', help='show PKGBUILD before install', action='store_true')

    group = parser.add_argument_group('AUR options')
    exc_group = group.add_mutually_exclusive_group(required=True)
    exc_group.add_argument('-c', '--config', help='show current settings', action='store_true')
    exc_group.add_argument('-y', help='update package cache', action='store_true')
    exc_group.add_argument('-S', help='install provided packages', nargs='+', metavar='pkg')
    exc_group.add_argument('-Q', '--query', help='list installed packages', action='store_true')
    exc_group.add_argument('-s', help='search provided packages on AUR', nargs='+', metavar='pkg')
    exc_group.add_argument('-u', '--upgrade', help='update installed packages', action='store_true')
    exc_group.add_argument('--gpg', help='import the provided GPG keys', nargs='+', metavar='key')

    arguments = parser.parse_args()

    try:
        if arguments.config:
            if not show_config():
                return 1
        elif arguments.y:
            if not update_package_cache():
                return 1
        elif arguments.S:
            for pkg in arguments.S:
                if not install_packages(pkg, show_pkgbuild=settings.review_pkgbuild or arguments.i):
                    return 1
        elif arguments.query:
            list_packages()
        elif arguments.s:
            for pkg in arguments.s:
                if not search_package(pkg):
                    return 1
        elif arguments.upgrade:
            if not update_packages():
                return 1
        elif arguments.gpg:
            for key in arguments.gpg:
                if not gpg.import_key(key):
                    return 1
    except AURManException as e:
        util.error(f"FATAL: {e}", file=sys.stderr)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logging.exception(e, exc_info=True, stack_info=True, extra={'prog': 'aurman'})

    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
