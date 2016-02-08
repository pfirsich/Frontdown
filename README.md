# Frontdown

## Overview
Frontdown is an open source hardlink backup tool/script under the GPLv3 license. It is written in Python 3.5.

At the moment it is only usable on Windows, but should be able to be ported to Linux/Mac with not much effort, if anyone is interested in doing this.

It's inception arose out of the lack of good open source backup solutions that meet the following requirements:
* No proprietary container/archive format - because you want to use the tools you already have and know to use to browse and operate on your backups.
* Versioning, but not full snapshots everytime - preferably backups using hardlinks
* Generate a report inbetween, so that I have a chance to review any operation on the file system before it occurs.
* Be versatile - don't just have one mode of operation and make me use multiple backup tools
* Just do the backup - No background service for fancy scheduling and automation throughout, but just a program that backups my stuff when I want it to and is relatively easy to use

I also wanted it to handle opened/locked files using Volume Shadow Copy (VSS), but since I myself don't have too much need for it, I did not look into it yet.

I'm aware that you have to be at least minimally tech-savvy to use Frontdown, since you have to edit your configuration files yourself and start it on the command line using Python and even though I am already using it for my personal backups, I still suspect some bugs lingering because of non-real world and inbred testing, so that I would doubly advice to be a little knowledgable about Python and computers before using it.

## Usage / Quickstart
backup.py, the main program takes only one argument, a JSON configuration file. An example of such a configuration file, that also includes the default values and should therefore **not be edited** you can see in [default.config.json](https://github.com/pfirsich/Frontdown/blob/master/default.config.json). 
It also includes some comments on all the possible values, so that you should definitely have a proper look at it.

A more thorough documentation will be worked on as soon as a single soul on this planet shows interest in using this program.

## Contributing / Contact
If you have any questions, feedback, feature requests, fixes or contributions of any kind, feel free to write me a mail (apart 
from using the issue tracker or sending a pull request of course): <joelschum@gmail.com>. Any contributions are much a appreciated!
