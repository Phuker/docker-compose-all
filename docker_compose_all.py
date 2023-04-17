#!/usr/bin/env python3
# encoding: utf-8

"""
A very simple Docker cluster management tool, recursively search and control all Docker Compose projects in a directory.
https://github.com/Phuker/docker-compose-all
"""

import os
import sys
import argparse
import logging
import atexit
import time
import subprocess
import shlex
from datetime import timedelta


__version__ = '0.2.1'
logger = logging.getLogger(__name__)
shell_args = None

VERSION_STR_SHORT = f'docker-compose-all version {__version__}'
VERSION_STR_LONG = f'docker-compose-all version {__version__}\n{__doc__.strip()}'

# https://docs.docker.com/compose/compose-file/03-compose-file/
DOCKER_COMPOSE_FILENAME_SET = {
    'compose.yaml',
    'compose.yml',
    'docker-compose.yaml',
    'docker-compose.yml',
}

# default docker-compose command
COMMAND_STOP = ['docker-compose', 'stop']
COMMAND_DOWN = ['docker-compose', 'down', '--rmi', 'all']
COMMAND_BUILD = ['docker-compose', 'build', '--pull']
COMMAND_UP = ['docker-compose', 'up', '-d']
COMMAND_PS = ['docker-compose', 'ps']
COMMAND_TOP = ['docker-compose', 'top']
COMMAND_CLEAN_NETWORKS = ('Removing all unused networks', ['docker', 'network', 'prune', '-f'])
COMMAND_CLEAN_IMAGES = ('Remove unused images', ['docker', 'image', 'prune', '-f'])
COMMAND_CLEAN_BUILDER = ('Remove build cache', ['docker', 'builder', 'prune', '-f'])
COMMANDS_CLEAN = [
    COMMAND_CLEAN_NETWORKS,
    COMMAND_CLEAN_IMAGES,
    COMMAND_CLEAN_BUILDER,
]


def _assert(expr, msg=''):
    if not expr:
        raise AssertionError(msg)


def _init_logging():
    logging_stream = sys.stdout
    logging_format = '\x1b[1m%(asctime)s [%(levelname)s]:\x1b[0m%(message)s'
    logging_level = logging.INFO

    if logging_stream.isatty():
        logging_date_format = '%H:%M:%S'
    else:
        logging_date_format = '%Y-%m-%d %H:%M:%S %z'

    logging.basicConfig(
        level=logging_level,
        format=logging_format,
        datefmt=logging_date_format,
        stream=logging_stream,
    )

    logging.addLevelName(logging.CRITICAL, '\x1b[31m{}\x1b[39m'.format(logging.getLevelName(logging.CRITICAL)))
    logging.addLevelName(logging.ERROR, '\x1b[31m{}\x1b[39m'.format(logging.getLevelName(logging.ERROR)))
    logging.addLevelName(logging.WARNING, '\x1b[33m{}\x1b[39m'.format(logging.getLevelName(logging.WARNING)))
    logging.addLevelName(logging.INFO, '\x1b[36m{}\x1b[39m'.format(logging.getLevelName(logging.INFO)))
    logging.addLevelName(logging.DEBUG, '\x1b[36m{}\x1b[39m'.format(logging.getLevelName(logging.DEBUG)))


def _parse_args():
    global shell_args

    default_docker_files_dir = '.'

    parser = argparse.ArgumentParser(
        description=VERSION_STR_LONG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=True
    )

    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument('--restart', action='store_true', help='Completely rebuild and rerun all. Including the following steps: stop, down, build, up, ps.')
    group.add_argument('--stop', action='store_true', help='Stop all containers')
    group.add_argument('--down', action='store_true', help='Make all down. Stop and remove containers, networks, images')
    group.add_argument('--build', action='store_true', help='Rebuild all')
    group.add_argument('--up', action='store_true', help='Make all up')
    group.add_argument('--ps', action='store_true', help='Each ps')
    group.add_argument('--top', action='store_true', help='List all process')

    dc_opt_group = parser.add_argument_group('docker-compose options')
    dc_opt_group.add_argument('--dokill', action='store_true', help='Run "docker-compose kill" instead of "docker-compose stop"')
    dc_opt_group.add_argument('--normi', action='store_true', help='Do NOT remove Docker images when running "docker-compose down"')
    dc_opt_group.add_argument('--nopull', action='store_true', help='Do NOT pull images when running "docker-compose build"')
    dc_opt_group.add_argument('--doclean', action='store_true', help='Clean up before exit, if no error. Remove ALL unused networks, images and build cache. WARN: This may cause data loss.')

    parser.add_argument('docker_files_dir', metavar='dir_path', nargs='?', default=default_docker_files_dir, help=f'A directory which contains Docker Compose projects, default: {default_docker_files_dir!r}')

    parser.add_argument('-V', '--version', action='store_true', help='Show version and exit')
    parser.add_argument('-v', '--verbose', action='count', default=0, help='Increase verbosity level (use -vv or more for greater effect)')

    shell_args = parser.parse_args()

    if shell_args.verbose >= 1:
        logging.root.setLevel(logging.DEBUG)
    
    shell_args.docker_files_dir = os.path.abspath(os.path.expanduser(shell_args.docker_files_dir))
    _assert(os.path.isdir(shell_args.docker_files_dir), f'Dir not found: {shell_args.docker_files_dir!r}')

    logger.debug('Command line arguments: %r', shell_args)

    if shell_args.version:
        print(VERSION_STR_LONG)
        sys.exit(0)


def colored(s, foreground, background=None, **kwargs):
    if kwargs.get('repr', False):
        s = repr(s)
    else:
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

    code = '\x1b[' + ';'.join(options) + 'm'
    code_end = '\x1b[0m'
    return code + s + code_end


def get_command_str(command):
    return ' '.join(shlex.quote(_) for _ in command)


def check_system():
    logger.info('Checking Docker & Docker Compose installation')
    commands = [
        ['docker', '--version'],
        ['docker-compose', '--version'],
    ]

    for command in commands:
        try:
            subprocess.check_call(command)
        except Exception as e:
            logger.error('Error when running %s: %r %r', colored(get_command_str(command), 'red', bold=True), type(e), e)
            return False

    return True


def scan_dirs(dir_path):
    """Scan and show Docker Compose projects"""

    docker_compose_dirs = []
    logger.info('Scanning %s ...', colored(dir_path, 'cyan', bold=True, repr=True))
    for top, __, files in os.walk(dir_path, followlinks=True):
        dir_path = os.path.abspath(top)

        if set(files) & DOCKER_COMPOSE_FILENAME_SET and dir_path not in docker_compose_dirs:
            logger.info('Found: %s', colored(dir_path, 'cyan', repr=True))
            docker_compose_dirs.append(dir_path)

    logger.info('Found %s Docker Compose projects', colored(len(docker_compose_dirs), 'default', bold=True))
    return docker_compose_dirs


def clean():
    logger.info('Cleanning up')
    for desc, command in COMMANDS_CLEAN:
        logger.info(desc)
        logger.info('Running %s', colored(get_command_str(command), 'green', bold=True))
        subprocess.call(command)


error_info_list = []
def all_run_commands(docker_compose_dirs, commands):
    error_dirs = []

    for command in commands:
        logger.info('Running %s in all Docker Compose projects', colored(get_command_str(command), 'green', bold=True))

        for i, dir_path in enumerate(docker_compose_dirs):
            logger.info('Running %s in %s (%d/%d)', colored(get_command_str(command), 'green'), colored(dir_path, 'green', repr=True), i + 1, len(docker_compose_dirs))
            if dir_path in error_dirs:
                logger.warning('Skiped because error happened')
                continue

            os.chdir(dir_path)
            try:
                subprocess.check_call(command)
            except subprocess.CalledProcessError as e:
                error_info = 'Dir: %r, Command: %s, Error: %r: %r' % (dir_path, get_command_str(command), type(e), e)
                logger.error(colored(error_info, 'red', bold=True))

                error_info_list.append(error_info)
                error_dirs.append(dir_path)


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


def update_docker_compose_commands():
    global COMMAND_DOWN, COMMAND_BUILD, COMMAND_STOP

    if shell_args.normi:
        COMMAND_DOWN = ['docker-compose', 'down']

    if shell_args.nopull:
        COMMAND_BUILD = ['docker-compose', 'build']

    if shell_args.dokill:
        COMMAND_STOP = ['docker-compose', 'kill']


def main():
    if sys.stdout.isatty():
        atexit.register(lambda: logger.info('Exiting'))
    else:
        atexit.register(lambda: logger.info('Exiting\n'))

    _start_time_stamp = time.time()
    atexit.register(lambda: logger.info('Time elapsed: %s', timedelta(seconds=int(time.time() - _start_time_stamp))))

    logger.info(colored(VERSION_STR_SHORT, 'default', bold=True))

    update_docker_compose_commands()

    # Run as root, after argparse (could show help)
    if not os.getuid() == 0:
        logger.critical('Need root privilege')
        sys.exit(1)
    else:
        logger.debug('Running as root')

    if not check_system():
        logger.error(colored('Docker & Docker Compose installation incomplete', 'red', bold=True))
        sys.exit(1)

    docker_compose_dirs = scan_dirs(shell_args.docker_files_dir)

    if shell_args.restart:
        all_restart(docker_compose_dirs)
    elif shell_args.down:
        all_down(docker_compose_dirs)
    elif shell_args.build:
        all_build(docker_compose_dirs)
    elif shell_args.up:
        all_up(docker_compose_dirs)
    elif shell_args.ps:
        all_ps(docker_compose_dirs)
    elif shell_args.top:
        all_top(docker_compose_dirs)
    elif shell_args.stop:
        all_stop(docker_compose_dirs)
    
    if len(error_info_list) > 0:
        logger.info('After run all commands, errors:')
        for error_info in error_info_list:
            logger.error(colored(error_info, 'red', bold=True))
        
        if shell_args.doclean:
            logger.warning('Skip clean because error happened')
        
        logger.info('Command %s exit with some error', colored(get_command_str(sys.argv), 'default', bold=True))
        sys.exit(1)
    else:
        if shell_args.doclean:
            clean()

        logger.info('Command %s exit with no error', colored(get_command_str(sys.argv), 'default', bold=True))


def _main():
    _init_logging()
    _parse_args()

    try:
        main()
    except Exception as e:
        logger.exception('%r: %r', type(e), e)
        sys.exit(1)


if __name__ == '__main__':
    _main()
