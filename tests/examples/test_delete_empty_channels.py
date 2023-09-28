from datetime import date
from itertools import count

import pytest

counter = count()


@pytest.fixture()
def api_client(channel_tree):
    def mock_api_call(url, **kwargs):
        if url == 'catalog/bulk_delete/':
            return {
                'statuses': {
                    oid: {'status': 403 if oid == 'c0001stlevelempty' else 200}
                    for oid in kwargs['data']['oids']
                }
            }
        if url == 'catalog/get-all/':
            return channel_tree

    from ms_client.client import MediaServerClient
    client = MediaServerClient()
    client.api = mock_api_call
    return client


@pytest.fixture()
def channel_tree():
    return {
        "channels": [
            {
                "oid": "c0001stlevelempty",
                "dbid": next(counter),
                "title": "First level empty Last Year",
                "add_date": "2023-07-03 16:24:00",
            },
            {
                "oid": "c0001stlevelfull",
                "dbid": next(counter),
                "title": "First level empty Last Year",
                "add_date": "2022-07-03 16:24:00",
                "videos": [{}, {}, {}],
                "lives": [{}],
                "photos": [{}],
            },
            {
                "oid": "c0001stlevelfull3sub",
                "dbid": next(counter),
                "title": "First level full with 3 subchannels",
                "add_date": "2022-07-03 16:24:00",
                "channels": [
                    {
                        "oid": "c0002ndlevelempty",
                        "dbid": next(counter),
                        "title": "Second level empty",
                        "add_date": "2022-07-03 16:24:00",
                    },
                    {
                        "oid": "c0002ndlevelfull",
                        "dbid": next(counter),
                        "title": "Second level full",
                        "add_date": "2022-07-03 16:24:00",
                        "videos": [{}, {}, {}],
                    },
                    {
                        "oid": "c0002ndlevelfull3sub",
                        "dbid": next(counter),
                        "title": "Second level full with 3 subchannels",
                        "add_date": "2022-07-03 16:24:00",
                        "videos": [{}, {}, {}],
                        "channels": [
                            {
                                "oid": "c0003rdlevelempty",
                                "dbid": next(counter),
                                "title": "Third level empty",
                                "add_date": "2022-07-03 16:24:00",
                            },
                            {
                                "oid": "c0003rdlevelempty2",
                                "dbid": next(counter),
                                "title": "Third level second empty",
                                "add_date": "2022-07-03 16:24:00",
                            },
                            {
                                "oid": "c0003rdlevelfull2sub",
                                "dbid": next(counter),
                                "title": "Third level full with 2 subchannels",
                                "add_date": "2022-07-03 16:24:00",
                                "channels": [
                                    {
                                        "oid": "c0004thlevelempty",
                                        "dbid": next(counter),
                                        "title": "Fourth level empty",
                                        "add_date": "2023-07-03 16:24:00",
                                    },
                                    {
                                        "oid": "c0004thlevelfull3sub",
                                        "dbid": next(counter),
                                        "title": "Fourth level full with 3 subchannels",
                                        "add_date": "2023-07-03 16:24:00",
                                        "channels": [
                                            {
                                                "oid": "c0005thlevelempty",
                                                "dbid": next(counter),
                                                "title": "Fifth level empty",
                                                "add_date": "2023-07-03 16:24:00",
                                            },
                                            {
                                                "oid": "c0005thlevelemptysubchannel",
                                                "dbid": next(counter),
                                                "title": "Fifth level with empty subchannel",
                                                "add_date": "2023-07-03 16:24:00",
                                                "channels": [
                                                    {
                                                        "oid": "c0006thlevelempty",
                                                        "dbid": next(counter),
                                                        "title": "Sixth level empty",
                                                        "add_date": "2023-07-03 16:24:00",
                                                    },
                                                ],
                                            },
                                        ],
                                    },
                                ],
                            },
                        ],
                    },
                ],
            },
        ],
    }


@pytest.mark.parametrize('blacklist, max_date, min_depth, expected_result', [
    pytest.param(
        (),
        date.today(),
        0,
        {
            'c0001stlevelempty', 'c0002ndlevelempty', 'c0003rdlevelempty', 'c0003rdlevelempty2',
            'c0004thlevelempty', 'c0005thlevelempty', 'c0006thlevelempty'
        }, id='Default no param'),
    pytest.param(
        ['c0003rdlevelempty', 'c0003rdlevelempty2', 'c0005thlevelempty'],
        date.today(),
        0,
        {
            'c0001stlevelempty', 'c0002ndlevelempty', 'c0004thlevelempty', 'c0006thlevelempty'
        }, id='Empty but excluded'),
    pytest.param(
        (),
        date(2023, 1, 1),
        0,
        {
            'c0002ndlevelempty', 'c0003rdlevelempty', 'c0003rdlevelempty2'
        }, id='Empty but channel date is after max_date'),
    pytest.param(
        (),
        date.today(),
        3,
        {
            'c0003rdlevelempty', 'c0003rdlevelempty2', 'c0004thlevelempty',
            'c0005thlevelempty', 'c0006thlevelempty'
        }, id='Empty but channel depth < min_depth'),
    pytest.param(
        (),
        date(2023, 1, 1),
        3,
        {
            'c0003rdlevelempty', 'c0003rdlevelempty2',
        }, id='Channel depth >= min_depth but channel date is after max_date'),
    pytest.param(
        ['c0003rdlevelempty', 'c0003rdlevelempty2', 'c0005thlevelempty'],
        date.today(),
        3,
        {
            'c0004thlevelempty', 'c0006thlevelempty'
        }, id='Channel depth >= min_depth but channel is excluded'),
    pytest.param(
        ['c0003rdlevelempty', 'c0003rdlevelempty2', 'c0005thlevelempty'],
        date(2023, 1, 1),
        0,
        {
            'c0002ndlevelempty'
        }, id='Empty but channel date is after max_date but some are excluded'),
    pytest.param(
        ['c0003rdlevelempty', 'c0003rdlevelempty2', 'c0005thlevelempty'],
        date(2023, 1, 1),
        3,
        set(),
        id='Empty but channel date is after max_date'
        'and some are excluded and channel depth < min_depth'),
])
def test_empty_channels_iterator(channel_tree, blacklist, max_date, min_depth, expected_result):
    from examples.delete_empty_channels import empty_channels_iterator
    oids = {channel['oid'] for channel in empty_channels_iterator(
        channel_tree,
        channel_oid_blacklist=blacklist,
        min_depth=min_depth,
        max_date=max_date
    )}
    assert oids == expected_result


def _get_oids(tree):
    for channel in tree.get('channels', ()):
        yield channel['oid']
        yield from _get_oids(channel)


@pytest.mark.parametrize('blacklist, max_date, min_depth, dry_run, expected_deleted', [
    pytest.param(
        (),
        date.today(),
        0,
        False,
        {
            # c0001stlevelempty is 403 on delete
            'c0002ndlevelempty', 'c0003rdlevelempty', 'c0003rdlevelempty2',
            'c0004thlevelempty', 'c0005thlevelempty', 'c0006thlevelempty',
            'c0003rdlevelfull2sub', 'c0004thlevelfull3sub',
            'c0005thlevelemptysubchannel',  # Recursively
        },
        id='Default no param'),
    pytest.param(
        ['c0003rdlevelempty', 'c0003rdlevelempty2', 'c0005thlevelemptysubchannel'],
        date.today(),
        0,
        False,
        {
            'c0002ndlevelempty', 'c0004thlevelempty', 'c0005thlevelempty',
        },
        id='Empty but excluded'),
    pytest.param(
        (),
        date(2023, 1, 1),
        0,
        False,
        {
            'c0002ndlevelempty', 'c0003rdlevelempty', 'c0003rdlevelempty2',
        },
        id='Empty but channel date is after max_date'),
    pytest.param(
        (),
        date.today(),
        3,
        False,
        {
            'c0003rdlevelempty', 'c0003rdlevelempty2', 'c0003rdlevelfull2sub',
            'c0004thlevelempty', 'c0004thlevelfull3sub',
            'c0005thlevelempty', 'c0005thlevelemptysubchannel', 'c0006thlevelempty',
        }, id='Empty but channel depth < min_depth'),
    pytest.param(
        (),
        date(2023, 1, 1),
        3,
        False,
        {
            'c0003rdlevelempty', 'c0003rdlevelempty2',
        }, id='Channel depth >= min_depth but channel date is after max_date'),
])
def test_delete_empty_channels(
    api_client,
    channel_tree,
    blacklist,
    max_date,
    min_depth,
    dry_run,
    expected_deleted
):
    from examples.delete_empty_channels import delete_empty_channels
    initial_oids = set(_get_oids(channel_tree))
    delete_empty_channels(
        api_client,
        channel_oid_blacklist=blacklist,
        max_date=max_date,
        min_depth=min_depth,
        dry_run=dry_run
    )
    assert initial_oids - set(_get_oids(channel_tree)) == expected_deleted
