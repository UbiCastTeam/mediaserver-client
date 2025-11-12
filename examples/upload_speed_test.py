#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2022, Stéphane Diemer
'''
Script to test upload speed of multiple files.
'''
from dataclasses import dataclass
import argparse
import logging
import multiprocessing
import os
import shutil
import string
import sys
import time
import traceback

logger = logging.getLogger('upload_speed_test')


def upload_hls_files(msc, uid, tmp_path):
    logger.info(f'Starting HLS upload (#{uid}).')
    msc.hls_upload(tmp_path + '.m3u8', f'speed-test-{uid}')


def upload_chunked_files(msc, uid, files_list):
    logger.info(f'Starting chunked upload (#{uid}).')
    for i, path in enumerate(files_list):
        logger.info(f'Process #{uid}, file {i + 1}/{len(files_list)}')
        msc.chunked_upload(file_path=path, remote_path=f'speed-test-{uid}/' + os.path.basename(path))


def strict_positive_int_type(value):
    val = int(value)
    if val <= 0:
        raise ValueError('A positive integer is required.')
    return val


def run_test(args):
    # Get ms client
    start = time.time()
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ms_client.client import MediaServerClient

    msc = MediaServerClient(args.conf, setup_logging=False)
    if args.chunk:
        msc.conf['UPLOAD_CHUNK_SIZE'] = args.chunk * 1000
    msc.check_server()

    # Generate test files
    tmp_path = '/tmp/ms-test-upload-file'
    logger.info(f'Generating {args.size} kB of test content in "{tmp_path}".')
    # Get text pattern of 1000 bytes
    text = 10 * (
        string.ascii_letters
        + string.digits
        + ' '
        + ''.join([c for c in reversed(string.digits)])
        + ''.join([c for c in reversed(string.ascii_lowercase)])
        + '\n')
    assert len(text) == 1000  # Check that the text size is exactly of 1000 bytes
    with open(tmp_path + '.m3u8', 'w') as fo:
        for i in range(args.size):
            fo.write(text)
    if os.path.isdir(tmp_path):
        shutil.rmtree(tmp_path)
    os.makedirs(tmp_path)
    files_list = []
    if args.count > 1:
        logger.info(f'Copying file {args.count - 1} times in "{tmp_path}".')
        for i in range(1, args.count):
            shutil.copy(tmp_path + '.m3u8', tmp_path + '/files-' + str(i) + '.ts')
            files_list.append(tmp_path + '/files-' + str(i) + '.ts')
    files_list.append(tmp_path + '.m3u8')

    # Prepare arguments
    if args.m3u8:
        up_fct = upload_hls_files
    else:
        up_fct = upload_chunked_files
    args_list = []
    for i in range(1, args.processes + 1):
        if args.m3u8:
            args_list.append((msc, i, tmp_path))
        else:
            args_list.append((msc, i, files_list))
    end = time.time()
    duration = end - start
    duration = round(duration, 2)
    logger.info(f'Initialisation done in {duration} s.')

    # Upload files
    start = time.time()
    try:
        if args.processes > 1:
            pool = multiprocessing.Pool(processes=args.processes)
            pool.starmap(up_fct, args_list)
            pool.close()
            pool.join()
        else:
            up_fct(*args_list[0])
    except Exception:
        logger.info(f'Test:\033[91m failed \033[0m\n{traceback.format_exc()}')
        return
    except KeyboardInterrupt:
        logger.info('Test:\033[93m canceled \033[0m')
        return
    else:
        end = time.time()
        duration = end - start
        logger.info('Test:\033[92m done \033[0m')
    finally:
        os.remove(tmp_path + '.m3u8')
        shutil.rmtree(tmp_path)

    total_files = args.count * args.processes
    total_size = round(args.count * args.processes * args.size / 1000, 2)
    avg_speed = round(args.count * args.processes * args.size / duration, 2)
    duration = round(duration, 2)
    logger.info(f'Number of files uploaded: {total_files}.')
    logger.info(f'Total size: {total_size} MB.')
    logger.info(f'Average speed: {avg_speed} kB/s.')
    logger.info(f'Upload duration: {duration} s.')
    return total_files, total_size, avg_speed, duration


@dataclass
class Params:
    conf: str
    count: int
    size: int
    chunk: int
    processes: int
    m3u8: bool
    debug: bool


def main():
    # Parse args
    parser = argparse.ArgumentParser(description=__doc__.strip())
    parser.add_argument(
        '-c', '--conf', action='store', default=None,
        help='Configuration file path or instance unix user. Use local configuration file by default.')
    parser.add_argument(
        '-n', '--count', action='store', default=10, type=strict_positive_int_type,
        help='The number of files to send. Default is 10.')
    parser.add_argument(
        '-s', '--size', action='store', default=1000, type=strict_positive_int_type,
        help='The size in kB of the files to send. default is 1 MB.')
    parser.add_argument(
        '-k', '--chunk', action='store', default=None, type=strict_positive_int_type,
        help='The size in kB of the chunks to send. default is 5 MB.')
    parser.add_argument(
        '-p', '--processes', action='store', default=1, type=strict_positive_int_type,
        help='Number of processes to use to upload (parallel upload). Each process will upload all files.')
    parser.add_argument(
        '-m', '--m3u8', action='store_true',
        help='Use HLS upload API instead of chunked upload API.')
    parser.add_argument(
        '-d', '--debug', action='store_true',
        help='Set log level to debug.')
    parser.add_argument(
        '-b', '--bench', action='store_true',
        help='Run script in benchmark mode. '
             'Other arguments will be ignored in this mode except "conf", "chunk" and "debug".')
    args = parser.parse_args()

    logging.basicConfig(
        format='%(asctime)s.%(msecs)03d pid:%(process)d %(name)s %(levelname)s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        level=logging.DEBUG if args.debug else logging.INFO,
    )

    if not args.bench:
        result = run_test(args)
        if not result:
            return 1
    else:
        logger.info('Running in benchmark mode.')
        results = []
        test_types = [
            {'m3u8': True},
            {'m3u8': False},
        ]
        test_data = [
            {'processes': 1, 'count': 5, 'size': 10},
            {'processes': 1, 'count': 5, 'size': 1000},
            {'processes': 1, 'count': 5, 'size': 1000000},
            {'processes': 3, 'count': 2, 'size': 10},
            {'processes': 3, 'count': 2, 'size': 1000},
            {'processes': 3, 'count': 2, 'size': 1000000},
            {'processes': 8, 'count': 2, 'size': 10},
            {'processes': 8, 'count': 2, 'size': 1000},
            {'processes': 8, 'count': 2, 'size': 1000000},
        ]
        steps = len(test_types) * len(test_data)
        for test_type in test_types:
            m3u8 = test_type.get('m3u8', False)
            for entry in test_data:
                # Number of steps: 3 * 3 * 5 * 5 * 4 = 400
                params = Params(
                    conf=args.conf,
                    count=entry['count'],
                    size=entry['size'],
                    chunk=args.chunk,
                    processes=entry['processes'],
                    m3u8=m3u8,
                    debug=args.debug,
                )
                logger.info(f'\033[94m-- Step {len(results) + 1}/{steps} Running with {params}...\033[0m')
                if params.m3u8 and params.size > 100000:
                    logger.info('Test skipped because of size limit in m3u8 upload.')
                    continue
                result = run_test(params)
                if not result:
                    return 1
                result = (params.m3u8, params.processes) + result
                results.append(','.join([str(v) for v in result]))

        csv = '/tmp/ms-test-upload-bench.csv'
        logger.info(f'CSV report will be written in "{csv}".')
        with open(csv, 'w') as fo:
            fo.write('hls upload,processes,total files,total size,average speed,duration\n')
            for result in results:
                fo.write(result + '\n')
        logger.info('Done.')

    return 0


if __name__ == '__main__':
    sys.exit(main())
