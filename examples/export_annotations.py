#!/usr/bin/env python3
'''
Script to ping a MediaServer.
'''
import os
import sys

if __name__ == '__main__':
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ms_client.client import MediaServerClient

    local_conf = sys.argv[1] if len(sys.argv) > 1 else None
    msc = MediaServerClient(local_conf)
    # ping
    annotations = msc.api('/annotations/list/', params={'oid': 'v125f52117974vspq8g1'})

    type_id = None
    annotation_type_name = 'comment'
    for key, val in annotations['types'].items():
        if val['slug'] == annotation_type_name:
            type_id = val['id']
    if type_id is None:
        print(f'Annotation type {annotation_type_name} not found')
        exit(1)

    for annotation in annotations['annotations']:
        # comment
        if annotation['type_id'] == type_id:
            s = '{poster} ({popularity} votes): {content}\n'.format(**annotation)
            print(s)
