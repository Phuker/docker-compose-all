# docker-compose-all

A very simple Docker cluster management tool, recursively search and control all Docker Compose projects in a directory.

![screenshots1.png](./screenshots/screenshot1.png)

## Requirements

- Python >= `3.6`, with `pip` installed
- Docker
- Docker Compose

## Install

```bash
python3 -m pip install -U docker-compose-all
```

## Usage

```console
# docker-compose-all --help
docker-compose-all version 0.1.7
usage: docker_compose_all.py [-h] [--restart | --stop | --down | --build | --up | --ps | --top] [--dokill] [--normi] [--nopull] [--doclean] [--normv] DIR

A very simple Docker cluster management tool, recursively search and control all Docker Compose projects in a directory.

positional arguments:
    DIR         A directory which contains docker-compose projects

optional arguments:
    -h, --help  show this help message and exit
    --restart   Completely rebuild and rerun all. Including the following steps: stop, down, build, up, ps.
    --stop      Stop all containers
    --down      Make all down. Stop and remove containers, networks, images
    --build     Rebuild all
    --up        Make all up
    --ps        Each ps
    --top       List all process

docker-compose options:
    --dokill    Run "docker-compose kill" instead of "docker-compose stop"
    --normi     Do NOT remove docker images when running "docker-compose down"
    --nopull    Do NOT pull images when running "docker-compose build"
    --doclean   Clean up before exit, if no error. Remove ALL unused images, networks, volumes. WARN: This may cause data loss.
    --normv     Do NOT remove ALL unused volumes when "--doclean"

https://github.com/Phuker
```

## Documentation

```shell
cat docker-compose-all.py
```

## FAQ


## License

This repo is licensed under the **GNU General Public License v3.0**

