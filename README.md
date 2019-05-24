![PyPI - Python Version](https://img.shields.io/pypi/pyversions/mediaserver-api-client.svg)
![PyPI](https://img.shields.io/pypi/v/mediaserver-api-client.svg)

# mediaserver-client

A python3 reference implementation of an UbiCast MediaServer API client.


## Important

For production use, it is recommended to use the branch named "stable". The "master" branch is used for development.


## Client class instantiation

The client class (`ms_client`.`client`.`MediaServerClient`) takes two arguments:
* `local_conf`: This argument can be either a dict, a path (`str` object) or a unix user (`unix:msuser` for example). The default value is `None`, which means no configuration.
* `setup_logging`: This argument must be a boolean. If set to `True`, the logging to console will be configured. The default value is `True`.


## Notes about older client

If you are using the first version of this client (a single file named mediaserver_api_client.py), here are the steps to update your client:

* Remove the old client file (mediaserver_api_client.py).
* Install the new client using the setup.py.
* Replace the import path of `MediaServerClient` (see examples).
* Replace the arguments named `config_dict` and `config_path` by `local_conf` in the `MediaServerClient` init.
* Replace all occurences of `MediaServerClient`.`config` by `MediaServerClient`.`conf`.


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
