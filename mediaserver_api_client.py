#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2016, Florent Thiery

import os
import math
import hashlib
import requests

SERVER_URL = 'https://alpha.ubicast.net'
API_KEY = ''
VERIFY_SSL = False
PROXIES = {'http': '', 'https': ''}

MiB = 1024 * 1024
UPLOAD_CHUNK_SIZE = 5 * MiB

session = None
if not VERIFY_SSL:
    from requests.packages.urllib3.exceptions import InsecureRequestWarning
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


def request(url, method='get', data={}, params={}, files={}, headers={}, json=True, timeout=10):
    global session
    if session is None:
        session = requests.Session()

    if method == 'get':
        req_function = session.get
        params['api_key'] = API_KEY
    else:
        req_function = session.post
        data['api_key'] = API_KEY

    req_args = {
        'url': url,
        'headers': headers,
        'params': params,
        'data': data,
        'timeout': timeout,
        'proxies': PROXIES,
        'verify': VERIFY_SSL,
        'files': files,
    }
    resp = req_function(**req_args)
    if resp.status_code != 200:
        raise Exception('HTTP %s error on %s', resp.status_code, url)

    return resp.json() if json else resp.text.strip()


def api(suffix, *args, **kwargs):
    BASE_URL = requests.compat.urljoin(SERVER_URL, 'api/v2/')
    suffix.lstrip('/')
    kwargs['url'] = requests.compat.urljoin(BASE_URL, suffix)
    print(kwargs['url'])
    return request(*args, **kwargs)


def read_in_chunks(file_object, chunk_size=UPLOAD_CHUNK_SIZE):
    while True:
        data = file_object.read(chunk_size)
        if not data:
            break
        yield data


def chunked_upload(file_path, title="", category="Unsorted"):
    total_size = os.path.getsize(file_path)
    chunks_count = math.ceil(total_size / UPLOAD_CHUNK_SIZE)
    start_offset = 0
    end_offset = min(UPLOAD_CHUNK_SIZE, total_size) - 1
    completion_data = {}
    md5sum = hashlib.md5()
    with open(file_path, "rb") as file_object:
        for index, chunk in enumerate(read_in_chunks(file_object)):
            print('Uploading chunk [%s/%s]' % (index + 1, chunks_count))
            md5sum.update(chunk)
            files = {"file": (os.path.basename(file_path), chunk)}
            headers = {"Content-Range": "bytes %(start_offset)s-%(end_offset)s/%(total_size)s" % locals()}
            resp = api('medias/resource/upload/', method='post', files=files, headers=headers)
            if "upload_id" not in completion_data:
                completion_data["upload_id"] = resp["upload_id"]
            start_offset += UPLOAD_CHUNK_SIZE
            end_offset = min(end_offset + UPLOAD_CHUNK_SIZE, total_size - 1)
    completion_data["md5"] = md5sum.hexdigest()
    resp = api('medias/resource/upload/complete/', data=completion_data)
    metadata = {
        "title": title,
        "code": completion_data["upload_id"], 
        "origin": "python-api-client",
        "detect_slide": "",
        #"detect_slide": "0_0-100_100-750" min: 1, max: 1000, default: 750,
        "ocr": False,
    }
    resp = api('medias/add/', method='post', data=metadata)
    return resp


if __name__ == '__main__':
    #print(api('users/add/', method='post', data={'email': 'test@test.com'}))
    chunked_upload('/tmp/test.mp4', title='Test multichunk upload')
    #fname = sys.argv[1]
    #print(api('medias/add/', method='post', files={'file': (fname, open(fname, 'rb'))}))
