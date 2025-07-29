![PyPI - Python Version](https://img.shields.io/pypi/pyversions/mediaserver-api-client.svg)
![PyPI](https://img.shields.io/pypi/v/mediaserver-api-client.svg)

# Nudgis API client

A python3 reference implementation of an UbiCast Nudgis API client.
Nudgis was called MediaServer in the past but the internal name of Nudgis is still MediaServer.

## Requirements

* git
* python >= 3.11 (download the latest stable release from https://www.python.org/downloads/)

Optional:
* python3-venv

Note:
If you are using Python3.9, use the branch of the same name.

## Installation

### Linux & OSX

For development, the package can be installed in editable mode to allow changes on it :

```sh
git clone https://github.com/UbiCastTeam/mediaserver-client.git
cd mediaserver-client/
python3 -m venv .venv
source .venv/bin/activate  # remember to run this every time you enter the folder and need to restore the environment
python3 -m pip install --editable .
```

If you want to install it system-wide as dependency, the releases are available on pypi:
```sh
pip install mediaserver-api-client
```

### Windows

* Open cmd.exe and check python is available with `py --version` which should display the Python version

```
>py --version
Python 3.11.1
```

* From this project root path, run:

```
> py -m venv .venv
> ".venv/Scripts/activate.bat"
> pip install .
``` 
 
* Check it works with:

```
>py -m examples.ping_server
Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "C:\Users\User\src\mediaserver-client\examples\ping_server.py", line 17, in <module>
    print(msc.api('/'))
          ^^^^^^^^^^^^
  File "C:\Users\User\src\mediaserver-client\ms_client\client.py", line 221, in api
    result = self.request(*args, **kwargs)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\User\src\mediaserver-client\ms_client\client.py", line 98, in request
    self.check_conf()
  File "C:\Users\User\src\mediaserver-client\ms_client\client.py", line 71, in check_conf
    configuration_lib.check_conf(self.conf)
  File "C:\Users\User\src\mediaserver-client\ms_client\lib\configuration.py", line 87, in check_conf
    raise ConfigurationError('The value of "SERVER_URL" is not set. Please configure it.')
ms_client.lib.configuration.ConfigurationError: The value of "SERVER_URL" is not set. Please configure it.
```

Despite the error above, it shows that the installation is complete.

## Configuration

Copy the provided `config.json.example` file into e.g. `myconfig.json`, edit it with a text editor and fill the URL and API KEY.

* Check it works with:

Linux:
```
$ python3 ./examples/ping.py myconfig.json
{'success': True, 'mediaserver': '13.1.1'}
```
Windows:
```
$ py ./examples/ping.py myconfig.json
{'success': True, 'mediaserver': '13.1.1'}
```

## Client class instantiation

The client class (`ms_client`.`client`.`MediaServerClient`) takes two arguments:
* `local_conf`: This argument can be either a dict, a path (`str` object) or a unix user (`unix:msuser` for example) -- only aplicable from running scripts from within the server running mediaserver (Nudgis). The default value is `None`, which means no configuration.
* `setup_logging`: This argument must be a boolean. If set to `True`, the logging to console will be configured. The default value is `True`.

## Configuration

You can see available parameters in the default configuration file :
[Default configuration](/ms_client/conf.py)

The local configuration must be a json file.

## Examples

### Start/Stop a live

``` python
from ms_client.client import MediaServerClient
msc = MediaServerClient(local_conf='your-conf.json')

response = msc.api('/lives/prepare', method='post')
if response['success']:
    oid = response['oid']
    rtmp_uri = response['publish_uri']

    print(oid, rtmp_uri)

    print(msc.api('/lives/start', method='post', data={'oid': oid}))

    print(msc.api('/lives/stop', method='post', data={'oid': oid}))
```

### Remove all users function

``` python
from ms_client.client import MediaServerClient
msc = MediaServerClient(local_conf='your-conf.json')


def remove_all_users():
    print('Remove all users')
    users = msc.api('/users')['users']

    for user in users:
        msc.api('/users/delete', method='get', params={'id': user['id']})
```

### Add media with a video, make it published at once

``` python
from ms_client.client import MediaServerClient
msc = MediaServerClient(local_conf='your-conf.json')

print(msc.add_media('Test multichunk upload mp4', file_path='test.mp4', validated='yes', speaker_email='user@domain.com'))
```

### Create user personal channel and upload into it

``` python
from ms_client.client import MediaServerClient
msc = MediaServerClient(local_conf='your-conf.json')

personal_channel_oid = msc.api('/channels/personal/', method='get', params={'email': 'test@test.com'}).get('oid')

respone_like = {
    'slug': 'testtestcom_05881',
    'oid': 'c125855df7d36iudslp3',
    'dbid': 113,
    'title': 'test@test.com',
    'success': True
}
if personal_channel_oid:
    print('Uploading to personal channel %s' % personal_channel_oid)

    print(msc.add_media('Test multichunk upload mp4', file_path='test.mp4', validated='yes', speaker_email='user@domain.com', channel=personal_channel_oid))
```

### Add media with a zip

``` python
from ms_client.client import MediaServerClient
msc = MediaServerClient(local_conf='your-conf.json')

print(msc.add_media('Test multichunk upload zip', file_path='/tmp/test.zip'))
print(msc.add_media(file_path='test.mp4'))
```

### Add a user

``` python
from ms_client.client import MediaServerClient
msc = MediaServerClient(local_conf='your-conf.json')

print(msc.api('users/add/', method='post', data={'email': 'test@test.com'}))
```

### Add users with csv file; example file (header should be included):

users.csv :

``` csv
Firstname;Lastname;Email;Company
Albert;Einstein;albert.einstein@test.com;Humanity
```

``` python
from ms_client.client import MediaServerClient
msc = MediaServerClient(local_conf='your-conf.json')

msc.import_users_csv('users.csv')
```

### Add an annotation

``` python
from ms_client.client import MediaServerClient
msc = MediaServerClient(local_conf='your-conf.json')

print(msc.api('annotations/post', params={'oid': 'v125849d470d7v92kvtc', 'time': 1000}))
```

### Get Chapters

``` python
from ms_client.client import MediaServerClient
msc = MediaServerClient(local_conf='your-conf.json')

print(msc.api('annotations/chapters/list', params={'oid': 'v125849d470d7v92kvtc'}))
```

### Get annotations types list and print chapters id

``` python
from ms_client.client import MediaServerClient
msc = MediaServerClient(local_conf='your-conf.json')

response = msc.api('annotations/types/list', params={'oid': 'v125849d470d7v92kvtc'})
for a in response['types']:
    if a['slug'] == 'chapter':
        print(a['id'])
```
