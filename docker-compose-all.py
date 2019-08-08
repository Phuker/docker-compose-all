#!/usr/bin/env python
# encoding: utf-8

import sys
import os
import time
import logging
import subprocess
import argparse


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s]:%(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    stream=sys.stdout
)


# run as root
if not os.getuid() == 0:
    logging.critical('Need root privilege.')
    sys.exit(1)
else:
    logging.debug('Running as root.')


YAML_FILENAME = u'docker-compose.yml'
EXIT_ON_ERROR = False


def check_system():
    commands = [
        ['docker', '--version'],
        ['docker-compose', '--version'],
    ]

    for command in commands:
        try:
            subprocess.check_call(command)
        except Exception as e:
            logging.error('Error when running %s: %s %s', repr(command), repr(type(e)), repr(str(e)))
            return False

    return True


def colored(s, foreground, background=None, **kwargs):
    s = str(s)
    foreground_color_table = {
        'red': '31',
        'green': '32',
        'yellow': '33',
        'cyan': '36',
    }
    background_color_table = {
        'black': '40',
    }
    options = []

    if kwargs.get('bold', False):
        options.append('1')
    if kwargs.get('reverse', False):
        options.append('7')

    options.append(foreground_color_table.get(foreground, '39'))
    if not background is None:
        options.append(background_color_table.get(background, '49'))

    code = '\033[' + ';'.join(options) + 'm'
    code_end = '\033[0m'
    return code + s + code_end


def scan_dirs(docker_files_dir):
    docker_compose_dirs = []
    logging.info('Scanning %s...', colored(repr(docker_files_dir), 'yellow', bold=True))
    for top, dirs, files in os.walk(docker_files_dir, followlinks=True):
        docker_compose_dir = os.path.abspath(top)

        if YAML_FILENAME in files and docker_compose_dir not in docker_compose_dirs:
            logging.info('Found: %s', colored(repr(docker_compose_dir), 'cyan', bold=True))
            docker_compose_dirs.append(docker_compose_dir)

    logging.info('Count: %s', colored(len(docker_compose_dirs), 'yellow', bold=True))
    return docker_compose_dirs


def clean():
    logging.info('Removing all unused image')
    command = ['docker', 'image', 'prune', '-f']
    logging.info('Running %s', colored(repr(command),'green',bold=True))
    subprocess.call(command)

    logging.info('Removing all unused network')
    command = ['docker', 'network', 'prune', '-f']
    logging.info('Running %s', colored(repr(command), 'green', bold=True))
    subprocess.call(command)


COMMAND_DOWN = ['docker-compose', 'down', '--rmi', 'all']
COMMAND_BUILD = ['docker-compose', 'build', '--pull']
COMMAND_UP = ['docker-compose', 'up', '-d']
COMMAND_PS = ['docker-compose', 'ps']
COMMAND_TOP = ['docker-compose', 'top']
COMMAND_STOP = ['docker-compose', 'stop']

errors = []
error_dirs = []
def all_run_commands(docker_compose_dirs, commands):
    dir_count = len(docker_compose_dirs)
    for command in commands:
        logging.info('Running %s in all docker compoes dirs', colored(repr(command), 'green', reverse=True))

        for dir_index in xrange(dir_count):
            docker_compose_dir = docker_compose_dirs[dir_index]
            logging.info('Running %s in %s (%d/%d)',
                         colored(repr(command), 'green', bold=True),
                         colored(repr(docker_compose_dir), 'green', bold=True),
                         dir_index + 1,
                         dir_count
                         )
            if docker_compose_dir in error_dirs:
                logging.info('Skiped because error happened')
                continue

            os.chdir(docker_compose_dir)
            print ''
            try:
                subprocess.check_call(command)
            except subprocess.CalledProcessError as e:
                logging.error(str(e))
                error_info = '%s %s %s' % (repr(docker_compose_dir), repr(command), repr(str(e)))
                errors.append(error_info)
                error_dirs.append(docker_compose_dir)
                logging.error(colored(error_info, 'red', bold=True))
                if EXIT_ON_ERROR:
                    print 'EXIT_ON_ERROR. Exiting.'
                    sys.exit(1)
            print ''


def all_restart(docker_compose_dirs):
    commands = [
        COMMAND_DOWN,
        COMMAND_BUILD,
        COMMAND_UP,
        COMMAND_PS,
    ]
    all_run_commands(docker_compose_dirs, commands)
    clean()


def all_down(docker_compose_dirs):
    all_run_commands(docker_compose_dirs, [COMMAND_DOWN])


def all_build(docker_compose_dirs):
    all_run_commands(docker_compose_dirs, [COMMAND_BUILD])


def all_up(docker_compose_dirs):
    all_run_commands(docker_compose_dirs, [COMMAND_UP])


def all_ps(docker_compose_dirs):
    all_run_commands(docker_compose_dirs, [COMMAND_PS])


def all_top(docker_compose_dirs):
    all_run_commands(docker_compose_dirs, [COMMAND_TOP])


def all_stop(docker_compose_dirs):
    all_run_commands(docker_compose_dirs, [COMMAND_STOP])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Control all docker compose projects from a directory.',
        epilog='https://github.com/Phuker',
        add_help=True
    )
    group = parser.add_mutually_exclusive_group()
    #group.add_argument('--show', action="store_true", help="Show all")
    group.add_argument('--restart',  action="store_true", help="Completely rebuild and rerun all")
    group.add_argument('--down', action="store_true", help="Make all down")
    group.add_argument('--build', action="store_true", help="Rebuild all")
    group.add_argument('--up', action="store_true", help="Make all up")
    group.add_argument('--ps', action="store_true", help="Each ps")
    group.add_argument('--top', action="store_true", help="List all process")
    group.add_argument('--stop', action="store_true", help="All stop")

    parser.add_argument('docker_files_dir', metavar="DIR", help="Directory contains all docker-compose files")
    args = parser.parse_args()

    encoding = sys.stdin.encoding
    if encoding is None or encoding == '' or encoding.lower() == 'ascii':
        encoding = "UTF-8"

    docker_files_dir = args.docker_files_dir
    docker_files_dir = os.path.abspath(os.path.expanduser(docker_files_dir))
    docker_files_dir = unicode(docker_files_dir, encoding)

    if not os.path.isdir(docker_files_dir):
        error_info = '%s is not a valid directory' % (repr(docker_files_dir), )
        logging.error(colored(error_info, 'red', bold=True))
        logging.info('Exit')
        sys.exit(1)

    if not check_system():
        error_info = 'docker & docker-compose installation incomplete'
        logging.error(colored(error_info, 'red', bold=True))
        logging.info('Exit')
        sys.exit(1)

    docker_compose_dirs = scan_dirs(docker_files_dir) # scan and show

    if args.restart:
        all_restart(docker_compose_dirs)
    elif args.down:
        all_down(docker_compose_dirs)
    elif args.build:
        all_build(docker_compose_dirs)
    elif args.up:
        all_up(docker_compose_dirs)
    elif args.ps:
        all_ps(docker_compose_dirs)
    elif args.top:
        all_top(docker_compose_dirs)
    elif args.stop:
        all_stop(docker_compose_dirs)

    if len(errors) > 0:
        logging.info('Commands all run, some error:')
        for error_info in errors:
            logging.error(colored(error_info, 'red', bold=True))
        logging.info('Exiting with some commands error')
        sys.exit(1)
    else:
        logging.info('Exiting')


