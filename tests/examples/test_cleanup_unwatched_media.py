#!/usr/bin/env python3
import pytest
import os

import examples.cleanup_unwatched_media as e


@pytest.fixture()
def api_client(unwatched_tree, all_resources):
    def mock_api_call(url, **kwargs):
        if url == "/catalog/bulk_delete/":
            return {
                "statuses": {oid: {"status": 200} for oid in kwargs["vods"]["oids"]}
            }
        elif url == "/stats/unwatched/":
            return unwatched_tree
        elif url == "/medias/resources-list/":
            oid = kwargs["params"]["oid"]
            return {"resources": all_resources.get(oid, {})}
        elif url == "/medias/resources-delete/":
            oid = kwargs["data"]["oid"]
            if oid in all_resources.keys():
                return {
                    "success": True,
                }
            else:
                return {"success": False}

    from ms_client.client import MediaServerClient

    client = MediaServerClient()
    client.api = mock_api_call
    return client


@pytest.fixture()
def all_resources():
    return {
        "v1234local": [
            {
                "manager": {"service": "local"},
                "format": "m3u8",
                "path": "media_1080_RB4YjJhKks.m3u8",
                "file_size": 1000,
            },
            {
                "manager": {"service": "local"},
                "format": "m3u8",
                "path": "media_720_yKViKrE37V.m3u8",
                "file_size": 500,
            },
            {
                "manager": {"service": "local"},
                "format": "mp4",
                "path": "media_1080_Gqi7RHDWdv.mp4",
                "file_size": 1000,
            },
        ],
        "v1234object": [
            {
                "manager": {"service": "object"},
                "format": "m3u8",
                "path": "media_1080_RB4YjJhKks.m3u8",
                "file_size": 1000,
            }
        ],
        "v1234youtube": [
            {
                "manager": {"service": "youtube"},
            }
        ],
    }


@pytest.fixture()
def unwatched_tree():
    return {
        "success": True,
        "start_date": "2023-09-10",
        "end_date": "2023-09-11",
        "unwatched": [
            {
                "object_id": "v1234local",
                "storage_used": 2000000,
            },
            {
                "object_id": "v1234object",
                "storage_used": 1000000,
            },
            {
                "object_id": "v1234youtube",
                "storage_used": 1000000,
            },
            {
                "object_id": "l12665a308e2b1mfwdke",
                "storage_used": 9970,
            },
        ],
    }


def test_get_human_readable_size():
    assert e.get_human_readable_size(1) == "1.0B"
    assert e.get_human_readable_size(1000) == "1.0KB"
    assert e.get_human_readable_size(1000000) == "1.0MB"
    assert e.get_human_readable_size(1000000000) == "1.0GB"
    assert e.get_human_readable_size(1000000000000) == "1.0TB"


def test_filter_vod(unwatched_tree):
    assert set(
        vod["object_id"] for vod in e.filter_vod(unwatched_tree["unwatched"])
    ) == {"v1234local", "v1234object", "v1234youtube"}


def test_query_deletable_unwatched_vods(api_client):
    vods = e.query_deletable_unwatched_vods(api_client, {})
    assert set(vod["object_id"] for vod in vods) == {"v1234local", "v1234object"}


def test_cleanup_hls_resources(api_client):
    vods = e.query_deletable_unwatched_vods(api_client, {})

    hls_resources, hls_size = e.get_hls_resources(vods)
    assert set(hls_resources.keys()) == {"v1234local", "v1234object"}
    assert hls_size == 2500
    total_resources = 0
    for h in hls_resources.values():
        total_resources += len(h)
        for path in h:
            assert path.endswith(".m3u8")
    assert total_resources == 3

    assert e.delete_hls_resources(api_client, vods, apply=False) == 0
    assert e.delete_hls_resources(api_client, vods, apply=True) == 3


def test_cleanup_to_trash(api_client):
    vods = e.query_deletable_unwatched_vods(api_client, {})

    total_size = e.get_total_size(vods)
    assert total_size == 3000000

    oids = e.get_oids(vods)
    assert set(oids) == {"v1234local", "v1234object"}

    trashed_media_count, trashed_files_log_path = e.delete_unwatched_vods(
        api_client, vods, apply=False
    )
    assert trashed_media_count == 0
    assert trashed_files_log_path is None

    trashed_media_count, trashed_files_log_path = e.delete_unwatched_vods(
        api_client, vods, apply=True
    )
    assert trashed_media_count == 2
    with open(trashed_files_log_path, "r") as f:
        d = f.read().strip()
        lines = d.split("\n")
        assert len(lines) == 2
        for oid in lines:
            assert oid.startswith("v")
    os.unlink(trashed_files_log_path)
