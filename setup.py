#!/usr/bin/python3
# -*- coding: utf-8 -*-
import os
from setuptools import setup


def fullsplit(path, result=None):
    """
    Split a pathname into components (the opposite of os.path.join)
    in a platform-neutral way.
    """
    if result is None:
        result = []
    head, tail = os.path.split(path)
    if head == '':
        return [tail] + result
    if head == path:
        return result
    return fullsplit(head, [tail] + result)


# Compile the list of packages available, because distutils doesn't have an easy way to do this.
#    Copied from Django's setup.py file
packages, package_data = [], {}

root_dir = os.path.dirname(__file__)
if root_dir != '':
    os.chdir(root_dir)

for dirpath, dirnames, filenames in os.walk('ms_client', followlinks=True):
    # Ignore PEP 3147 cache dirs and those whose names start with '.'
    dirnames[:] = [d for d in dirnames if not d.startswith('.') and d != '__pycache__']
    parts = fullsplit(dirpath)
    package_name = '.'.join(parts)
    if '__init__.py' in filenames:
        packages.append(package_name)
        filenames = [f for f in filenames if not f.endswith('.py') and not f.endswith('.pyc')]
    if filenames:
        relative_path = []
        while '.'.join(parts) not in packages:
            relative_path.append(parts.pop())
        if relative_path:
            relative_path.reverse()
            path = os.path.join(*relative_path)
        else:
            path = ''
        package_files = package_data.setdefault('.'.join(parts), [])
        package_files.extend([os.path.join(path, f) for f in filenames])


# get version without importing module
version = None
with open('ms_client/__init__.py', 'r') as fo:
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
    license='cc-by-sa',
    packages=packages,
    package_data=package_data,
    scripts=[],
    install_requires=['requests'],
)
