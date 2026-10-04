#!/usr/bin/env python3
# encoding: utf-8

"""
Recursively scan a directory for Docker Compose projects and run docker compose in every project found.
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

from . import __version__


PROGRAM_NAME: str = 'docker-compose-all'

VERSION_STR_SHORT: str = f'{PROGRAM_NAME} {__version__}'
VERSION_STR_LONG: str = f'{PROGRAM_NAME} {__version__}\n{__doc__.strip()}'

# https://docs.docker.com/compose/compose-file/03-compose-file/
DOCKER_COMPOSE_FILENAME_SET: set[str] = {
    'compose.yaml',
    'compose.yml',
    'docker-compose.yaml',
    'docker-compose.yml',
}

COMMAND_CLEANUP_NETWORKS: tuple[str, list[str]] = ('Remove unused networks', ['docker', 'network', 'prune', '-f'])
COMMAND_CLEANUP_IMAGES: tuple[str, list[str]] = ('Remove unused images', ['docker', 'image', 'prune', '-f'])
COMMAND_CLEANUP_BUILDER: tuple[str, list[str]] = ('Remove build cache', ['docker', 'builder', 'prune', '-f'])
COMMANDS_CLEANUP: list[tuple[str, list[str]]] = [
    COMMAND_CLEANUP_NETWORKS,
    COMMAND_CLEANUP_IMAGES,
    COMMAND_CLEANUP_BUILDER,
]

DOCKER_COMPOSE_COMMAND_PREFIX: list[str] = ['docker', 'compose']
COMMAND_SEPARATORS: tuple[str, ...] = (';', '&&', '||')

logger: logging.Logger = logging.getLogger(__name__)
shell_args: argparse.Namespace | None = None


def assert_(expr: object, msg: str = '') -> None:
    if not expr:
        raise AssertionError(msg)


def init_logging() -> None:
    logging_stream = sys.stdout
    logging_format = '\x1b[1m%(asctime)s [%(levelname)s]:\x1b[0m%(message)s'
    logging_level = logging.INFO
    logging_date_format = '%Y-%m-%d %H:%M:%S %z'

    logging.basicConfig(
        level=logging_level,
        format=logging_format,
        datefmt=logging_date_format,
        stream=logging_stream,
    )

    logging.addLevelName(logging.CRITICAL, f'\x1b[31m{logging.getLevelName(logging.CRITICAL)}\x1b[39m')
    logging.addLevelName(logging.ERROR, f'\x1b[31m{logging.getLevelName(logging.ERROR)}\x1b[39m')
    logging.addLevelName(logging.WARNING, f'\x1b[33m{logging.getLevelName(logging.WARNING)}\x1b[39m')
    logging.addLevelName(logging.INFO, f'\x1b[36m{logging.getLevelName(logging.INFO)}\x1b[39m')
    logging.addLevelName(logging.DEBUG, f'\x1b[36m{logging.getLevelName(logging.DEBUG)}\x1b[39m')


def parse_command_chain(args: list[str]) -> list[tuple[str | None, list[str]]]:
    """Split raw command line arguments into a chain of (operator, docker_compose_args) pairs"""

    if not args:
        return []

    command_chain = []
    operator = None
    docker_compose_args = []

    for arg in args:
        if arg in COMMAND_SEPARATORS:
            assert_(docker_compose_args, f'Missing command before operator {arg!r}')

            command_chain.append((operator, docker_compose_args))
            operator = arg
            docker_compose_args = []
        else:
            docker_compose_args.append(arg)

    assert_(docker_compose_args, 'Missing command after operator')

    command_chain.append((operator, docker_compose_args))
    return command_chain


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    if args is None:
        args = sys.argv[1:]

    default_scan_dir = '.'

    parser = argparse.ArgumentParser(
        prog=PROGRAM_NAME,
        description=VERSION_STR_LONG,
        epilog='''\
All arguments are passed through to "docker compose" as-is, so any "docker compose" option and command can be used.
Multiple commands can be chained with the separators ';', '&&', and '||' (quote them to protect them from the shell).
Conditions are evaluated independently for each project, using the exit status of the previous command in that project.

Examples:

  docker-compose-all up -d
  docker-compose-all --progress plain build --pull --no-cache '&&' up -d''',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
        allow_abbrev=False,
    )

    parser.add_argument('--dca-scan-dir', '--docker-compose-all-scan-dir', dest='scan_dir', metavar='dir_path', default=default_scan_dir, help='Directory to recursively scan for Docker Compose projects, default: %(default)r')
    parser.add_argument('--dca-verbose', '--docker-compose-all-verbose', dest='verbose', action='count', default=0, help='Increase verbosity level')
    parser.add_argument('--dca-cleanup', '--docker-compose-all-cleanup', dest='cleanup', action='store_true', help='Clean up unused Docker networks, images, and build cache before exit, unless an error occurred. WARNING: This may cause data loss.')

    result, unknown_args = parser.parse_known_args(args)

    if result.verbose >= 1:
        logging.root.setLevel(logging.DEBUG)

    logger.debug('Parsed arguments: %r, unknown arguments: %r', result, unknown_args)

    # Only for print_help()
    parser.add_argument('-h', '--help', action='store_true', help='Show this help message and exit')
    parser.add_argument('-V', '--version', action='store_true', help='Show version and exit')
    parser.add_argument('docker_compose_args', nargs='*', help='See below for details')

    if len(args) == 1 and args[0] in ('-h', '--help'):
        parser.print_help()
        sys.exit(0)

    if len(args) == 1 and args[0] in ('-V', '--version'):
        print(VERSION_STR_LONG)
        sys.exit(0)

    result.command_chain = parse_command_chain(unknown_args)

    result.scan_dir = os.path.abspath(os.path.expanduser(result.scan_dir))
    assert_(os.path.isdir(result.scan_dir), f'Directory not found: {result.scan_dir!r}')

    logger.debug('Command line arguments: %r', result)

    return result


def colored(s: object, foreground: str, background: str | None = None, **kwargs: bool) -> str:
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
    if background is not None:
        options.append(background_color_table.get(background, '49'))

    code = '\x1b[' + ';'.join(options) + 'm'
    code_end = '\x1b[0m'
    return code + s + code_end


def get_command_str(command: list[str]) -> str:
    return ' '.join(shlex.quote(_) for _ in command)


def get_command_chain_str(command_chain: list[tuple[str | None, list[str]]]) -> str:
    parts = []

    for operator, docker_compose_args in command_chain:
        if operator:
            parts.append(operator)

        parts.append(get_command_str(DOCKER_COMPOSE_COMMAND_PREFIX + docker_compose_args))

    return ' '.join(parts)


def check_system() -> bool:
    logger.info('Checking Docker and Docker Compose installation')
    commands = [
        ['docker', '--version'],
        ['docker', 'compose', 'version'],
    ]

    for command in commands:
        try:
            subprocess.check_call(command)
        except Exception as e:
            logger.error('Error running %s: %r %r', colored(get_command_str(command), 'red', bold=True), type(e), e)
            return False

    return True


def scan_dirs(dir_path: str) -> list[str]:
    """Scan and show Docker Compose projects"""

    docker_compose_dirs = []
    logger.info('Scanning %s', colored(dir_path, 'cyan', bold=True, repr=True))
    for top, __, files in os.walk(dir_path, followlinks=True):
        dir_path = os.path.abspath(top)

        if set(files) & DOCKER_COMPOSE_FILENAME_SET and dir_path not in docker_compose_dirs:
            logger.info('Found: %s', colored(dir_path, 'cyan', repr=True))
            docker_compose_dirs.append(dir_path)

    logger.info('Found %s Docker Compose projects', colored(len(docker_compose_dirs), 'default', bold=True))
    return docker_compose_dirs


def cleanup() -> None:
    logger.info('Cleaning up')
    for description, command in COMMANDS_CLEANUP:
        logger.info(description)
        logger.info('Running %s', colored(get_command_str(command), 'green', bold=True))
        subprocess.call(command)


def run_command_chain(command_chain: list[tuple[str | None, list[str]]]) -> int:
    """Run a command chain in the current directory, return the exit status of the last executed command"""

    prev_status = 0

    for operator, docker_compose_args in command_chain:
        if operator == '&&':
            should_run = (prev_status == 0)
        elif operator == '||':
            should_run = (prev_status != 0)
        else:
            should_run = True

        if not should_run:
            continue

        command = DOCKER_COMPOSE_COMMAND_PREFIX + docker_compose_args
        logger.info('Running %s', colored(get_command_str(command), 'green', bold=True))

        try:
            subprocess.check_call(command)
        except subprocess.CalledProcessError as e:
            prev_status = e.returncode
        else:
            prev_status = 0

    return prev_status


error_info_list: list[str] = []
def all_run_commands(docker_compose_dirs: list[str], command_chain: list[tuple[str | None, list[str]]]) -> None:
    logger.info('Running %s in all Docker Compose projects', colored(get_command_chain_str(command_chain), 'green', bold=True))

    for index, dir_path in enumerate(docker_compose_dirs, start=1):
        logger.info('Running in %s (%d/%d)', colored(dir_path, 'green', repr=True), index, len(docker_compose_dirs))

        os.chdir(dir_path)
        status = run_command_chain(command_chain)

        if status != 0:
            error_info = 'Directory: %r, command chain: %s, exit status: %d' % (dir_path, get_command_chain_str(command_chain), status)
            logger.error(colored(error_info, 'red', bold=True))
            error_info_list.append(error_info)


def main() -> None:
    global shell_args

    init_logging()
    shell_args = parse_args()

    if sys.stdout.isatty():
        atexit.register(lambda: logger.info('Exiting'))
    else:
        atexit.register(lambda: logger.info('Exiting\n'))

    start_timestamp = time.time()
    atexit.register(lambda: logger.info('Time elapsed: %s', timedelta(seconds=int(time.time() - start_timestamp))))

    logger.info(colored(VERSION_STR_SHORT, 'default', bold=True))

    if not os.getuid() == 0:
        logger.warning('Not running as root, some operations may fail')

    if not check_system():
        logger.error(colored('Docker or Docker Compose is not available', 'red', bold=True))
        sys.exit(1)

    docker_compose_dirs = scan_dirs(shell_args.scan_dir)

    if shell_args.command_chain:
        all_run_commands(docker_compose_dirs, shell_args.command_chain)
    else:
        logger.info('No Docker Compose command specified')

    command_str = get_command_str([PROGRAM_NAME] + sys.argv[1:])

    if len(error_info_list) > 0:
        logger.info('Errors while running commands:')
        for error_info in error_info_list:
            logger.error(colored(error_info, 'red', bold=True))

        if shell_args.cleanup:
            logger.warning('Skipping cleanup because errors occurred')

        logger.info('Command %s failed', colored(command_str, 'default', bold=True))
        sys.exit(1)
    else:
        if shell_args.cleanup:
            cleanup()

        logger.info('Command %s succeeded', colored(command_str, 'default', bold=True))


if __name__ == '__main__':
    main()
