#!/usr/bin/env python3
# encoding: utf-8

import sys
import os
import time
import logging
import subprocess
import argparse


__version__ = '0.1.7'
YAML_FILENAME = u'docker-compose.yml'
EXIT_ON_ERROR = False


logging_stream = sys.stdout
logging_format = '\033[1m%(asctime)s [%(levelname)s]:\033[0m%(message)s'

if 'DEBUG' in os.environ:
    logging_level = logging.DEBUG
else:
    logging_level = logging.INFO

if logging_stream.isatty():
    logging_date_format = '%H:%M:%S'
else:
    print('', file=logging_stream)
    logging_date_format = '%Y-%m-%d %H:%M:%S'

logging.basicConfig(
    level=logging_level,
    format=logging_format,
    datefmt=logging_date_format,
    stream=logging_stream,
)

logging.addLevelName(logging.CRITICAL, '\033[31m{}\033[39m'.format(logging.getLevelName(logging.CRITICAL)))
logging.addLevelName(logging.ERROR, '\033[31m{}\033[39m'.format(logging.getLevelName(logging.ERROR)))
logging.addLevelName(logging.WARNING, '\033[33m{}\033[39m'.format(logging.getLevelName(logging.WARNING)))
logging.addLevelName(logging.INFO, '\033[36m{}\033[39m'.format(logging.getLevelName(logging.INFO)))
logging.addLevelName(logging.DEBUG, '\033[36m{}\033[39m'.format(logging.getLevelName(logging.DEBUG)))


def check_system():
    logging.info('Checking docker & docker-compose installation')
    commands = [
        ['docker', '--version'],
        ['docker-compose', '--version'],
    ]

    for command in commands:
        try:
            subprocess.check_call(command)
        except Exception as e:
            logging.error('Error when running %s: %r %r', colored(repr(' '.join(command)), 'red', bold=True), type(e), str(e))
            return False

    return True


def colored(s, foreground, background=None, **kwargs):
    s = str(s)
    foreground_color_table = {
        'red': '31',
        'green': '32',
        'yellow': '33',
        'blue': '34',
        'cyan': '36',
        'white': '37',
        'default': '39',
    }
    background_color_table = {
        'black': '40',
        'default': '49',
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
    logging.info('Scanning %s...', colored(repr(docker_files_dir), 'cyan', bold=True))
    for top, __, files in os.walk(docker_files_dir, followlinks=True):
        docker_compose_dir = os.path.abspath(top)

        if YAML_FILENAME in files and docker_compose_dir not in docker_compose_dirs:
            logging.info('Found: %s', colored(repr(docker_compose_dir), 'cyan'))
            docker_compose_dirs.append(docker_compose_dir)

    logging.info('Found %s docker compose projects', colored(len(docker_compose_dirs), 'default', bold=True))
    return docker_compose_dirs


# default docker-compose command
COMMAND_STOP = ['docker-compose', 'stop']
COMMAND_DOWN = ['docker-compose', 'down', '--rmi', 'all']
COMMAND_BUILD = ['docker-compose', 'build', '--pull']
COMMAND_UP = ['docker-compose', 'up', '-d']
COMMAND_PS = ['docker-compose', 'ps']
COMMAND_TOP = ['docker-compose', 'top']
COMMAND_CLEAN_NETWORKS = ('Removing all unused networks', ['docker', 'network', 'prune', '-f'])
COMMAND_CLEAN_IMAGES = ('Removing all unused images', ['docker', 'image', 'prune', '-f'])
COMMAND_CLEAN_VOLUMES = ('Removing all unused local volumes', ['docker', 'volume', 'prune', '-f'])
COMMANDS_CLEAN = [
    COMMAND_CLEAN_NETWORKS,
    COMMAND_CLEAN_IMAGES,
]


def clean():
    logging.info('Cleanning up')
    for desc, command in COMMANDS_CLEAN:
        logging.info(desc)
        logging.info('Running %s', colored(repr(' '.join(command)), 'green', bold=True))
        subprocess.call(command)


errors = []
error_dirs = []
def all_run_commands(docker_compose_dirs, commands):
    dir_count = len(docker_compose_dirs)
    for command in commands:
        logging.info('Running %s in all docker compose projects', colored(repr(' '.join(command)), 'green', bold=True))

        for dir_index in range(dir_count):
            docker_compose_dir = docker_compose_dirs[dir_index]
            logging.info('Running %s in %s (%d/%d)',
                         colored(repr(' '.join(command)), 'green'),
                         colored(repr(docker_compose_dir), 'green'),
                         dir_index + 1,
                         dir_count
                         )
            if docker_compose_dir in error_dirs:
                logging.warning('Skiped because error happened')
                continue

            os.chdir(docker_compose_dir)
            try:
                subprocess.check_call(command)
            except subprocess.CalledProcessError as e:
                logging.error(str(e))
                error_info = 'Dir: %r Command: %r Error: %r, %r' % (docker_compose_dir, ' '.join(command), type(e), str(e))
                errors.append(error_info)
                error_dirs.append(docker_compose_dir)
                logging.error(colored(error_info, 'red', bold=True))
                if EXIT_ON_ERROR:
                    print('EXIT_ON_ERROR. Exiting.', file=logging_stream)
                    sys.exit(1)


def all_restart(docker_compose_dirs):
    commands = [
        COMMAND_STOP,
        COMMAND_DOWN,
        COMMAND_BUILD,
        COMMAND_UP,
        COMMAND_PS,
    ]
    all_run_commands(docker_compose_dirs, commands)


def all_down(docker_compose_dirs):
    all_run_commands(docker_compose_dirs, [COMMAND_STOP, COMMAND_DOWN])


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


def parse_docker_compose_options(args):
    global COMMAND_DOWN, COMMAND_BUILD, COMMAND_STOP, COMMANDS_CLEAN

    if args.normi:
        COMMAND_DOWN = ['docker-compose', 'down']

    if args.nopull:
        COMMAND_BUILD = ['docker-compose', 'build']

    if args.dokill:
        COMMAND_STOP = ['docker-compose', 'kill']
    
    if not args.normv:
        COMMANDS_CLEAN.append(COMMAND_CLEAN_VOLUMES)


def parse_args():
    parser = argparse.ArgumentParser(
        description='A very simple Docker cluster management tool, recursively search and control all Docker Compose projects in a directory.',
        epilog='https://github.com/Phuker',
        add_help=True
    )
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument('--restart',  action="store_true", help="Completely rebuild and rerun all. Including the following steps: stop, down, build, up, ps.")
    group.add_argument('--stop', action="store_true", help="Stop all containers")
    group.add_argument('--down', action="store_true", help="Make all down. Stop and remove containers, networks, images")
    group.add_argument('--build', action="store_true", help="Rebuild all")
    group.add_argument('--up', action="store_true", help="Make all up")
    group.add_argument('--ps', action="store_true", help="Each ps")
    group.add_argument('--top', action="store_true", help="List all process")
    

    dc_opt_group = parser.add_argument_group('docker-compose options')
    dc_opt_group.add_argument('--dokill', action='store_true', help='Run "docker-compose kill" instead of "docker-compose stop"')
    dc_opt_group.add_argument('--normi', action='store_true', help='Do NOT remove docker images when running "docker-compose down"')
    dc_opt_group.add_argument('--nopull', action='store_true', help='Do NOT pull images when running "docker-compose build"')
    dc_opt_group.add_argument('--doclean', action='store_true', help='Clean up before exit, if no error. Remove ALL unused images, networks, volumes. WARN: This may cause data loss.')
    dc_opt_group.add_argument('--normv', action='store_true', help='Do NOT remove ALL unused volumes when "--doclean"')

    parser.add_argument('docker_files_dir', metavar="DIR", help="A directory which contains docker-compose projects")
    args = parser.parse_args()

    return args


def main():
    _welcome_str = f'docker-compose-all version {__version__}'
    print(colored(_welcome_str, 'default', bold=True), file=logging_stream)

    _start_time_stamp = time.time()

    args = parse_args()
    parse_docker_compose_options(args)

    # Run as root, after argparse (could show help)
    if not os.getuid() == 0:
        logging.critical('Need root privilege.')
        sys.exit(1)
    else:
        logging.debug('Running as root.')

    docker_files_dir = args.docker_files_dir
    docker_files_dir = os.path.abspath(os.path.expanduser(docker_files_dir))

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
        logging.info('After run all commands, errors:')
        for error_info in errors:
            logging.error(colored(error_info, 'red', bold=True))
        
        if args.doclean:
            logging.warning('Skip clean because error happened')
        
        logging.info('Time elapsed: %.2fs', time.time() - _start_time_stamp)
        logging.info('Command %s exit with some error', colored(repr(' '.join(sys.argv)), 'default', bold=True))
        sys.exit(1)
    else:
        if args.doclean:
            clean()

        logging.info('Time elapsed: %.2fs', time.time() - _start_time_stamp)
        logging.info('Command %s exit with no error', colored(repr(' '.join(sys.argv)), 'default', bold=True))


if __name__ == "__main__":
    main()
