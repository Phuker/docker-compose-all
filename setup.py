#!/usr/bin/env python3
# encoding: utf-8

from setuptools import setup

import docker_compose_all

with open('Readme.PyPI.md', 'r') as f:
    long_description = f.read()

setup(
    name='docker-compose-all',
    version=docker_compose_all.__version__,
    description='A very simple Docker cluster management tool, recursively search and control all Docker Compose projects in a directory.',
    long_description=long_description,
    long_description_content_type="text/markdown",
    author='Phuker',
    # author_email='',
    url='https://github.com/Phuker/docker-compose-all',
    license='GNU General Public License v3.0',
    packages=[],
    py_modules = ['docker_compose_all'],
    install_requires=[],
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'docker-compose-all=docker_compose_all:main'
        ]
    },
    classifiers=[
        'Environment :: Console',
        'Operating System :: POSIX',
        'Operating System :: POSIX :: Linux',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Programming Language :: Python :: 3',
    ],
    python_requires = '>=3.6'
)
