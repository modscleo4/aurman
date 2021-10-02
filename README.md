# AURMan
A Python 3 Arch Linux AUR CLI Manager

AURMan relies on `base-devel` (`git`, `curl`) so you don't need to install any other package except python3 to use it

The basic commands are:

| Command | Description                     |
|---------|---------------------------------|
| -y      | Update package cache            |
| -S      | Install provided packages       |
| -Q      | List installed packages         |
| -s      | Search provided packages on AUR |
| -u      | Update installed packages       |

The configuration file is `/etc/aurman.conf`.
