#!/usr/bin/env python3
"""
Script to extract one layer of a Dynamic RichMedia file into a single file.
By default, will target the first camera it finds. Requires ffmpeg to be present in the PATH

./examples/extract_layer.py --url https://nudgis.tv/videos/myvideo/ --config myconfig.json --stop-after 100
"""

import argparse
import json
import logging
import os
import subprocess
import sys
from urllib.parse import urlparse

logger = logging.getLogger("extract_layer")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description=__doc__.strip(),
    )

    parser.add_argument(
        "--url",
        type=str,
        required=True,
        help="URL of source media (can be the slug or permalink URL)",
    )

    parser.add_argument(
        "--config", type=str, required=True, help="Path to config file."
    )

    parser.add_argument(
        "--layer-label",
        type=str,
        default="camera",
        help="String to look for in the layer labels; the first matching layer will be selected",
    )

    parser.add_argument(
        "--stop-after",
        type=int,
        default=0,
        help="Stop after this amount of seconds (useful for testing purposes)",
    )

    args = parser.parse_args()

    # get ms client
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ms_client.client import MediaServerClient

    msc = MediaServerClient(args.config)
    path = urlparse(args.url).path
    name = path.strip("/").split("/")[-1]
    if name.startswith("v") and len(name) == 20:
        key = "oid"
    else:
        key = "slug"

    params = {"full": "yes"}
    params[key] = name
    m = msc.api("/medias/get/", params=params)
    if not m.get("info"):
        print(f"No media found at {args.url}")
        sys.exit(1)

    info = m["info"]
    layout_preset = info.get("layout_preset")
    if not layout_preset:
        print("Media does not have any layout info")
        sys.exit(1)

    layout = json.loads(layout_preset)
    original_size = layout.get("composition_area", {"w": 1920, "h": 1080})

    initial_preset = layout["composition_data"][0]
    target_layer = None
    available_layers = list()
    for layer in initial_preset["layers"]:
        available_layers.append(layer["label"])
        if target_layer is None and args.layer_label in layer["label"]:
            target_layer = layer["source"]["roi"]

    if not target_layer:
        print(
            f"\nFound no layer with label containing {args.layer_label} in {initial_preset['layers']}"
        )
        print(f"\nPossible --layer-label arguments are: {available_layers}")
        sys.exit(1)

    oid = info["oid"]
    resources = msc.api("/medias/resources-list/", params={"oid": oid})["resources"]

    resource = None
    # we expect the only mp4 resource to be the high quality file
    for r in resources:
        if r["format"] == "mp4":
            resource = r
            if r["width"] != original_size["w"] or r["height"] != original_size["h"]:
                print("Warning, downloaded file is smaller than original")
            break
    url = resource["file"]

    filter_params = "{w}:{h}:{x}:{y}".format(**target_layer)
    cmd = f'ffmpeg -y -i "{url}" -filter:v "crop={filter_params}" -c:a copy'
    if args.stop_after:
        cmd += f" -t {args.stop_after}"
    cmd += f" {oid}_{args.layer_label}.mp4"
    print("Starting command, hit Q key to abort")
    print(cmd)
    status, output = subprocess.getstatusoutput(cmd)
    if status != 0:
        print(output)
