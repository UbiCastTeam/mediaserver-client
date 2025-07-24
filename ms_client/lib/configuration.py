"""
MediaServer client configuration library
This module is not intended to be used directly, only the client class should be used.
"""
import json
import logging
import re
import socket
from pathlib import Path
from typing import Any

from ..conf import BASE_CONF

logger = logging.getLogger(__name__)


class ConfigurationError(ValueError):
    pass


def load_conf(default_conf: Path | str | dict | None = None, local_conf: Path | str | dict | None = None) -> dict:
    # Copy default configuration
    conf = BASE_CONF.copy()
    # Update with default and local configuration
    for index, conf_override in enumerate((default_conf, local_conf)):
        if not conf_override:
            continue

        if isinstance(conf_override, str) and not conf_override.startswith('unix:'):
            conf_override = Path(conf_override)

        if isinstance(conf_override, str):
            # Use an unix user to get configuration
            user = conf_override[len('unix:'):]
            try:
                conf_mod = get_conf_for_unix_user(user)
            except Exception as err:
                raise ConfigurationError(f'Failed to get configuration from unix user: {err}') from err
            else:
                conf.update(conf_mod)
        elif isinstance(conf_override, Path):
            # Configuration file
            if conf_override.exists():
                content = conf_override.read_text()
                content = re.sub(r'\n\s*//.*', '\n', content)  # Remove comments
                conf_mod = json.loads(content) if content else None
                if not conf_mod:
                    logger.debug(f'Config file "{conf_override}" is empty.')
                else:
                    logger.debug(f'Config file "{conf_override}" loaded.')
                    if not isinstance(conf_mod, dict):
                        raise ConfigurationError(f'The configuration in "{conf_override}" is not a dict.')
                    conf.update(conf_mod)
            else:
                logger.debug(f'Config file {conf_override} does not exist.')
        elif isinstance(conf_override, dict):
            # Configuration dict
            for key, val in conf_override.items():
                if not key.startswith('_'):
                    conf[key] = val
        else:
            raise ConfigurationError('Unsupported type for configuration.')
    if conf['SERVER_URL'].endswith('/'):
        conf['SERVER_URL'] = conf['SERVER_URL'].rstrip('/')
    conf['CLIENT_ID'] = conf['CLIENT_ID'].replace('<host>', socket.gethostname())
    return conf


def update_conf(local_conf: Path | str | dict | None, key: str, value: Any) -> None:
    if isinstance(local_conf, str):
        local_conf = Path(local_conf)
    if not local_conf or not isinstance(local_conf, Path):
        logger.debug('Cannot update configuration, "local_conf" is not a path.')
        return
    content = ''
    if local_conf.is_file():
        content = local_conf.read_text()
        content = re.sub(r'\n\s*//.*', '\n', content)  # Remove comments
    data = json.loads(content) if content else {}
    data[key] = value
    new_content = json.dumps(data, sort_keys=True, indent=4)
    local_conf.write_text(new_content)
    logger.info(f'Configuration file "{local_conf}" updated: "{key}" set to "{value}".')


def check_conf(conf: dict) -> None:
    # Check that mandatory configuration values are set
    if not conf.get('SERVER_URL') or conf['SERVER_URL'] == 'https://mediaserver':
        raise ConfigurationError('The value of "SERVER_URL" is not set. Please configure it.')
    conf['SERVER_URL'] = conf['SERVER_URL'].strip('/')


def get_conf_for_unix_user(user: str) -> dict:
    user = user.strip()
    if not user:
        raise ConfigurationError('Invalid unix user provided.')

    settings_path = Path(f'/home/{user}/msinstance/conf/mssettings.py')
    if not settings_path.exists():
        raise ConfigurationError(f'Instance settings file "{settings_path}" does not exists.')
    logger.info(f'Retrieving configuration from user "{user}" instance.')

    # Get settings, do not load module to avoid import errors
    content = settings_path.read_text().replace('\r', '')

    # Get site url
    SITE_URL = None
    res = re.search(r'SITE_URL\s*=\s*[\'|"]{1}(.*)[\'|"]{1}\n', content)
    if res:
        SITE_URL = res.groups()[0]
    if SITE_URL is None:
        raise ConfigurationError('Failed to get site URL from instance settings.')
    logger.info(f'Site URL from settings: "{SITE_URL}".')

    # Get master API key
    MASTER_API_KEY = None
    res = re.search(r'MASTER_API_KEY\s*=\s*[\'|"]{1}(.*)[\'|"]{1}\n', content)
    if res:
        MASTER_API_KEY = res.groups()[0]
    if MASTER_API_KEY is None:
        raise ConfigurationError('Failed to get master API key from instance settings.')

    return {
        'SERVER_URL': SITE_URL,
        'API_KEY': MASTER_API_KEY,
    }
