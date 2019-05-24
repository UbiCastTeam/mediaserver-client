#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
MediaServer client csv library
This module is not intended to be used directly, only the client class should be used.
'''
import logging
import time

logger = logging.getLogger('ms_client.lib.csv')


def import_users_csv(client, csv_path):
    groupname = 'Users imported from csv on %s' % time.ctime()
    groupid = client.api('groups/add/', method='post', data={'name': groupname}).get('id')
    logger.info('Created group %s with id %s' % (groupname, groupid))
    with open(csv_path, 'r') as f:
        d = f.read()
        for index, l in enumerate(d.split('\n')):
            # Skip first line (contains header)
            if l and index > 0:
                fields = [field.strip() for field in l.split(';')]
                email = fields[2]
                user = {
                    'email': email,
                    'first_name': fields[0],
                    'last_name': fields[1],
                    'company': fields[3],
                    'username': email,
                    'is_active': 'true',
                }
                logger.info('Adding %s' % email)
                try:
                    logger.info(client.api('users/add/', method='post', data=user))
                except Exception as e:
                    logger.error('Error: %s' % e)
                logger.info('Adding user %s to group %s' % (email, groupname))
                try:
                    logger.info(client.api('groups/members/add/', method='post', data={'id': groupid, 'user_email': email}))
                except Exception as e:
                    logger.error('Error: %s' % e)
