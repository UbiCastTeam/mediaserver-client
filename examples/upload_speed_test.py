#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2017, Stéphane Diemer
'''
Script to test upload speed of multiple files.
'''
import argparse
import logging
import os
import shutil
import string
import sys
import time

logger = logging.getLogger('upload_speed_test')


if __name__ == '__main__':
    # parse args
    parser = argparse.ArgumentParser(description=__doc__.strip())
    parser.add_argument('conf', nargs='?', action='store', default=None, help='Configuration file path or instance unix user. Use local configuration file by default.')
    parser.add_argument('count', nargs='?', action='store', default=10, type=int, help='The number of files to send. Default is 10.')
    parser.add_argument('size', nargs='?', action='store', default=1000, type=int, help='The size in kB of the files to send. default is 1 MB.')
    parser.add_argument('chunk', nargs='?', action='store', default=None, type=int, help='The size in kB of the chunks to send. default is 5 MB.')
    parser.add_argument('-m', '--m3u8', dest='m3u8', action='store_true', help='Use HLS upload API instead of chunked upload API.')
    parser.add_argument('-d', '--debug', dest='debug', action='store_true', help='Set log level to debug.')
    parser.add_argument('-5', '--md5', dest='md5', action='store_true', help='Check md5 or not when using chunked upload.')
    args = parser.parse_args()

    # get ms client
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ms_client.client import MediaServerClient

    msc = MediaServerClient(args.conf)
    if args.chunk:
        msc.conf['UPLOAD_CHUNK_SIZE'] = args.chunk * 1000
    msc.check_server()

    # generate test file
    tmp_path = '/tmp/ms-test-upload-file'
    logger.info('Generating %s kB of test content in "%s".', args.size, tmp_path)
    # possible characters
    chars = string.ascii_letters + '_' + string.digits + '-' + '\n'
    with open(tmp_path + '.m3u8', 'w') as fo:
        for i in range(args.size * 1000):
            fo.write(chars[i % len(chars)])
    if os.path.isdir(tmp_path):
        shutil.rmtree(tmp_path)
    os.makedirs(tmp_path)
    files_list = list()
    if args.count > 1:
        for i in range(1, args.count):
            shutil.copy(tmp_path + '.m3u8', tmp_path + '/files-' + str(i))
            files_list.append(tmp_path + '/files-' + str(i))
    files_list.append(tmp_path + '.m3u8')

    # upload file
    start = time.time()
    try:
        if args.m3u8:
            logger.info('Starting HLS upload.')
            msc.hls_upload(tmp_path + '.m3u8', 'rtest')
        else:
            logger.info('Starting chunked upload (check_md5=%s).', args.md5)
            for i, path in enumerate(files_list):
                logger.info('File %s/%s', i + 1, args.count)
                msc.chunked_upload(file_path=path, remote_path='rtest/%s' % (path[len(os.path.dirname(tmp_path)) + 1:]), check_md5=args.md5)
    except Exception as e:
        logger.info('Test:\033[91m failed \033[0m\n%s', e)
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info('Test:\033[93m canceled \033[0m')
        sys.exit(1)
    else:
        end = time.time()
        duration = end - start
        logger.info('Test:\033[92m done \033[0m')
    finally:
        os.remove(tmp_path + '.m3u8')
        shutil.rmtree(tmp_path)

    logger.info('Number of files uploaded: %s.', args.count)
    logger.info('Total size: %.2f MB.', args.count * args.size / 1000)
    logger.info('Average speed: %.2f kB/s.', args.count * args.size / duration)
    logger.info('Upload duration: %.2f s.', duration)

    sys.exit(0)
