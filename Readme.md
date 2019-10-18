# docker-compose-all

A very simple docker cluster management tool. Control all docker compose projects in a directory.

![screenshots1.png](./screenshots/screenshot1.png)

## Requirements

- python3
- docker
- docker-compose

## Usage

```
# ./docker-compose-all.py --help
docker-compose-all version 0.1.0
usage: docker-compose-all.py [-h]
                             [--restart | --stop | --down | --build | --up | --ps | --top]
                             [--normi] [--nopull] [--dokill]
                             DIR

A very simple docker cluster management tool. Control all docker compose
projects in a directory.

positional arguments:
  DIR         A directory which contains docker-compose projects

optional arguments:
  -h, --help  show this help message and exit
  --restart   Completely rebuild and rerun all. Including the following steps:
              stop, down, build, up, ps, and clean up.
  --stop      Stop all containers
  --down      Make all down. Stop and remove containers, networks
  --build     Rebuild all
  --up        Make all up
  --ps        Each ps
  --top       List all process

docker-compose options:
  --normi     Do NOT remove docker images when running "docker-compose down"
  --nopull    Do NOT pull images when running "docker-compose build"
  --dokill    Run "docker-compose kill" instead of "docker-compose stop"

https://github.com/Phuker
```

## Documentation

```shell
cat docker-compose-all.py
```

## FAQ


## License

this repo is licensed under the **GNU General Public License v3.0**

