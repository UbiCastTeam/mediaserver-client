#!/usr/bin/python3
# -*- coding: utf-8 -*-
import os
from setuptools import setup


# get version without importing module
version = None
with open(os.path.join(os.path.dirname(__file__), 'ms_client', '__init__.py'), 'r') as fo:
    for line in fo:
        if line.startswith('__version__'):
            version = line[len('__version__'):].strip(' =\'"\n\t')
            break


setup(
    name='ms_client',
    version=version,
    description='A Python3 client to interact with an UbiCast MediaServer site.',
    author='UbiCast',
    url='https://github.com/UbiCastTeam/mediaserver-client',
    license='LGPL v3',
    packages=['ms_client'],
    package_data={'ms_client': ['conf.json']},
    scripts=[],
    setup_requires=['setuptools'],
    install_requires=['requests'],
)
