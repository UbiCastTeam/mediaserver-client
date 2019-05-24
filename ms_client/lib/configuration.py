#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
MediaServer client library
This module is not intended to be used directly, only the client class should be used.
'''
import imp
import json
import logging
import os
import re
import subprocess

logger = logging.getLogger('ms_client.lib.configuration')

BASE_CONF_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'conf.json')


def load_conf(default_conf=None, local_conf=None):
    # copy default configuration
    with open(BASE_CONF_PATH, 'r') as fo:
        content = fo.read()
    content = re.sub(r'\n\s*//.*', '\n', content)  # remove comments
    conf = json.loads(content)
    # update with default and local configuration
    for index, conf_override in enumerate((default_conf, local_conf)):
        if not conf_override:
            continue
        if isinstance(conf_override, dict):
            for key, val in conf_override.items():
                if not key.startswith('_'):
                    conf[key] = val
        elif isinstance(conf_override, str):
            if conf_override.startswith('unix:'):
                # use an unix user to get configuration
                user = conf_override[len('unix:'):]
                try:
                    conf_mod = get_conf_for_unix_user(user)
                except Exception as e:
                    raise ValueError('Failed to get configuration from unix user: %s' % e)
                else:
                    conf.update(conf_mod)
            elif os.path.exists(conf_override):
                with open(conf_override, 'r') as fo:
                    content = fo.read()
                content = re.sub(r'\n\s*//.*', '\n', content)  # remove comments
                conf_mod = json.loads(content) if content else None
                if not conf_mod:
                    logger.debug('Config file "%s" is empty.', conf_override)
                else:
                    logger.debug('Config file "%s" loaded.', conf_override)
                    if not isinstance(conf_mod, dict):
                        raise ValueError('The configuration in "%s" is not a dict.' % conf_override)
                    conf.update(conf_mod)
            else:
                logger.debug('Config file does not exists, using default config.')
        else:
            raise ValueError('Unsupported type for configuration.')
    if conf['SERVER_URL'].endswith('/'):
        conf['SERVER_URL'] = conf['SERVER_URL'].rstrip('/')
    return conf


def update_conf(local_conf, key, value):
    if not local_conf or not isinstance(local_conf, str):
        logger.debug('Cannot update configuration, "local_conf" is not a path.')
        return
    content = ''
    if os.path.isfile(local_conf):
        with open(local_conf, 'r') as fo:
            content = fo.read()
        content = content.strip()
    data = json.loads(content) if content else dict()
    data[key] = value
    new_content = json.dumps(data, sort_keys=True, indent=4)
    with open(local_conf, 'w') as fo:
        fo.write(new_content)
    logger.debug('Configuration file "%s" updated: "%s" set to "%s".', local_conf, key, value)


def check_conf(conf):
    # check that mandatory configuration values are set
    if not conf.get('SERVER_URL') or conf['SERVER_URL'] == 'https://mediaserver':
        raise ValueError('The value of "SERVER_URL" is not set. Please configure it.')
    conf['SERVER_URL'] = conf['SERVER_URL'].strip('/')
    if not conf.get('API_KEY'):
        raise ValueError('The value of "API_KEY" is not set. Please configure it.')


def get_conf_for_unix_user(user):
    user = user.strip()
    if not user:
        raise ValueError('Invalid unix user provided.')
    # override config with data from user db
    instance_dir = '/home/%s/msinstance' % user
    if not os.path.exists(instance_dir):
        raise Exception('Instance dir "%s" does not exists.' % instance_dir)
    logger.info('Retrieving configuration from MS user "%s".', user)

    # get MS db settings
    # do not load entire module to avoid errors
    mssettings_path = os.path.join(instance_dir, 'conf', 'mssettings.py')
    with open(mssettings_path, 'r') as fo:
        content = fo.read().replace('\r', '')
    if 'DATABASES' not in content:
        raise Exception('Failed to get instance db settings, no configuration found in mssettings.')
    content = content[content.index('\nDATABASES'):]
    content = content[:content.index('\n}') + 2]
    dbs_module = imp.new_module('dbs_module')
    exec(content, dbs_module.__dict__)

    # get MS site settings
    cmd = 'python3 %s shell -i python' % os.path.join(instance_dir, 'manage.py')
    if os.environ.get('USER') == user:
        cmd = ['bash', '-c', cmd]
    else:
        cmd = ['su', user, '-c', cmd]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate(input=('from mediaserver.main.models import SiteSettings; ms_ss=SiteSettings.get_singleton(); print("site_url:%s" % ms_ss.site_url); print("master_api_key:%s" % ms_ss.master_api_key); print("resources_secret:%s" % ms_ss.resources_secret);').encode('utf-8'))
    out = out.decode('utf-8') if out else ''
    if err:
        out += '\n' + err.decode('utf-8')
    m = re.match(r'site_url:(.*)\nmaster_api_key:(.*)\nresources_secret:(.*)', out)
    if not m:
        raise Exception('Failed to get instance settings:\n%s' % out)
    site_url, master_api_key, resources_secret = m.groups()

    # prepare client configuration
    conf = dict(
        SECURE_LINK=True if resources_secret else False,  # just for information, not used in the client
        SERVER_URL=site_url,
        API_KEY=master_api_key,
    )
    return conf
