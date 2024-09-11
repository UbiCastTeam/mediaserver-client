#!/usr/bin/env python3
import argparse
import csv
import logging
import sys

from datetime import datetime, timedelta

csv.field_size_limit(sys.maxsize)  # support huge fields


def setup_logging(verbose=False):
    logging.addLevelName(
        logging.ERROR, "\033[1;31m%s\033[1;0m" % logging.getLevelName(logging.ERROR)
    )
    logging.addLevelName(
        logging.WARNING, "\033[1;33m%s\033[1;0m" % logging.getLevelName(logging.WARNING)
    )
    level = getattr(logging, "DEBUG" if verbose else "INFO")
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(message)s",
    )


def get_percent(index, total):
    percent = 100 * (index) / total
    return percent


def get_percent_string(val, total, do_format=None):
    if do_format == "size":
        return f"{format_bytes(val)} / {format_bytes(total)} ({get_percent(val, total):.1f}%)"
    elif do_format == "time":
        return f"{format_seconds(val)} / {format_seconds(total)} ({get_percent(val, total):.1f}%)"
    else:
        return f"{val} / {total} ({get_percent(val, total):.1f}%)"


def format_seconds(seconds):
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    timecode = "%d:%02d:%02d" % (h, m, s)
    return timecode


def format_bytes(size):
    # 2**10 = 1024
    power = 2**10
    n = 0
    power_labels = {0: "", 1: "kilo", 2: "mega", 3: "giga", 4: "tera"}
    while size > power:
        size /= power
        n += 1
    return f"{round(size, 1)} {power_labels[n]}bytes"


def print_dict_stats(
    d,
    title,
    threshold_percent=0,
    do_format=None,
):
    d = dict(sorted(d.items(), key=lambda item: item[1], reverse=True))
    print(f"\n**** {title}:")
    total = sum(d.values())
    skipped = 0
    for key, val in d.items():
        if val > 0:
            percent = get_percent(val, total)
            if threshold_percent and percent <= threshold_percent:
                skipped += val
            else:
                print(f"{key}: {get_percent_string(val, total, do_format)}")
    if skipped:
        print(
            f"Various (below {threshold_percent}%: {get_percent_string(skipped, total)}"
        )


logger = logging.getLogger("csv-media-stats")


class Stats:
    def __init__(self, options):
        self.options = options
        self.recordings_per_day = dict()
        self.parse_options()
        self.skipped = 0
        self.read_csv()
        self.display_stats()
        if self.options["compute_max_parallel_recordings"]:
            self.compute_max_parallel_recordings()

    def compute_max_parallel_recordings(self):
        max_parallel = 0
        max_date = max_machines = None
        processed = 0
        total_media = sum([len(t) for t in self.recordings_per_day.values()])
        days_sorted = sorted(self.recordings_per_day.keys())
        for day in days_sorted:
            recordings_per_day = self.recordings_per_day[day]
            sorted_recordings = sorted(recordings_per_day)
            while len(sorted_recordings):
                cursor, cursor_end, origin = sorted_recordings.pop(0)
                machines = [self.get_recorder_serial(origin)]
                processed += 1
                parallel = 1
                print(
                    f"[{processed}/{total_media}] {cursor} ({len(recordings_per_day)} media the same day)"
                )
                while cursor <= cursor_end:
                    for start, end, origin in sorted_recordings:
                        machine = self.get_recorder_serial(origin)
                        if cursor >= start and cursor <= end:
                            if (
                                machine not in machines
                            ):  # we do not want to count trimmings from the same machine
                                parallel += 1
                                machines.append(machine)
                    cursor += timedelta(seconds=1)
                    if parallel > max_parallel:
                        max_parallel = parallel
                        max_date = cursor
                        max_machines = machines
        print(
            f"Reached {max_parallel} parallel recordings on {max_date}: {max_machines}"
        )

    def get_recorder_serial(self, origin):
        return origin.split("_")[0]

    def parse_options(self):
        for key in ["start_date", "end_date"]:
            date = self.options.get(key)
            if date:
                self.options[key] = datetime.strptime(date, "%Y-%m-%d")

    def read_csv(self):
        self.media_list = list()
        with open(self.options["input"]) as f:
            reader = csv.DictReader(f, delimiter=",")
            for row in reader:
                if row["type"] == "video":
                    try:
                        media = self.filter_by_date(row)
                        if media:
                            self.media_list.append(media)
                    except Exception as e:
                        logger.warning(f"Failed to parse row {row}: {e}")
        logging.info(f"Found {len(self.media_list)} media, skipped {self.skipped}")

    def filter_by_date(self, row):
        creation = row["creation"] = datetime.strptime(
            row["creation"], "%Y-%m-%d %H:%M:%S"
        )
        if self.options["start_date"] and creation < self.options["start_date"]:
            logging.debug(
                f"Skipping {row} because it was created before the start date"
            )
            self.skipped += 1
            return
        if self.options["end_date"] and creation > self.options["end_date"]:
            self.skipped += 1
            logging.debug(f"Skipping {row} because it was created after the end date")
            return

        end_time = creation + timedelta(seconds=int(float(row["duration_s"])))
        origin = row["origin"]
        if origin.startswith("miris-box") or origin.startswith("easycast-"):
            day_code = f"{creation.year}-{creation.month}-{creation.day}"
            self.recordings_per_day.setdefault(day_code, [])
            self.recordings_per_day[day_code].append([creation, end_time, origin])
        return row

    def display_stats(self):
        upload_types_count = {
            "hardware": 0,
            "webstudio": 0,
            "obs": 0,
            "upload": 0,
            "embed": 0,
            "external-resource": 0,
            "youtube": 0,
            "videoconferencing": 0,
            "mediaimport": 0,
            "mediasite-migration": 0,
            "mediaserver-client": 0,
            "unspecified": 0,
            "empty": 0,
        }

        upload_types_duration = dict(upload_types_count)

        upload_types_size = dict(upload_types_count)

        media_type = {
            "original": 0,
            "trimming": 0,
        }

        hardware_count = {}
        hardware_duration = {}

        speakers_count = {}
        speakers_duration = {}

        for media in self.media_list:
            origin = media["origin"]
            speaker_email = media["speaker_email"]
            duration_seconds = int(float(media["duration_s"])) if media["duration_s"] else 0
            size_bytes = int(media["storage_used"])

            try:
                if "trimming-" in origin:
                    media_type["trimming"] += 1
                    origin = origin.split(" trimming")[0]
                else:
                    media_type["original"] += 1

                if origin.startswith("miris-box-") or origin.startswith("easycast-"):
                    mtype = "hardware"
                    serial, version = origin.split("_")

                    hardware_count.setdefault(serial, 0)
                    hardware_count[serial] += 1

                    hardware_duration.setdefault(serial, 0)
                    hardware_duration[serial] += duration_seconds
                elif origin in [
                    "Manual (form: AddMediaWithFileForm)",
                    "Manual (form: AddVODByUploadForm)",
                    "Manual (form: AddVODWithMetadataZipForm)",
                ]:
                    mtype = "upload"
                elif origin == "Manual (form: AddVODWithEmbedForm)":
                    mtype = "embed"
                elif origin == "Manual (form: AddVODWithResourcesForm)":
                    mtype = "external-resource"
                elif origin == "Manual (form: AddVODWithYouTubeForm)":
                    mtype = "youtube"
                elif origin == "Manual (form: AddVODEmptyForm)":
                    mtype = "empty"
                elif origin.startswith("webstudio_"):
                    # webstudio_linux_chromium_102
                    mtype = "webstudio"
                    # ws, os, browser, browser_ver = origin.split('_')
                elif (
                    origin.startswith("zoom")
                    or origin.startswith("msteams-")
                    or origin in ["teams", "microsoft_teams"]
                    or origin == "big_blue_button"
                ):
                    mtype = "videoconferencing"
                elif origin == "nudgis-obs-plugin":
                    mtype = "obs"
                elif origin.startswith("mediaimport-"):
                    mtype = "mediaimport"
                elif origin in ["mediatransfer", "mediasite-migration-client"]:
                    mtype = "mediasite-migration"
                elif origin == "python-api-client":
                    mtype = "mediaserver-client"
                elif origin in ["API", ""]:
                    mtype = "unspecified"
                else:
                    logging.warning(f'Unsupported origin "{origin}" for {media}')

                upload_types_count[mtype] += 1
                upload_types_duration[mtype] += duration_seconds
                upload_types_size[mtype] += size_bytes

            except Exception as e:
                logging.warning(f"Failed to analyze origin for {media}: {e}")

            if speaker_email:
                speakers_count.setdefault(speaker_email, 0)
                speakers_count[speaker_email] += 1
                speakers_duration.setdefault(speaker_email, 0)
                speakers_duration[speaker_email] += duration_seconds

        print_dict_stats(upload_types_count, "Count by type")
        print_dict_stats(upload_types_duration, "Duration by type", do_format="time")
        print_dict_stats(upload_types_size, "Size by type", do_format="size")
        print_dict_stats(media_type, "Media type")
        print_dict_stats(hardware_count, "Count by system")
        print_dict_stats(hardware_duration, "Duration by system", do_format="time")
        print_dict_stats(speakers_count, "Count by speaker")
        print_dict_stats(speakers_duration, "Duration by speaker", do_format="time")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "-v", "--verbose", help="set verbosity to DEBUG", action="store_true"
    )

    parser.add_argument("--input", type=str, required=True, help="Path to CSV file")

    parser.add_argument(
        "--start-date",
        type=str,
        help='Only keep media created after this date, e.g. "2022-01-31"',
    )

    parser.add_argument(
        "--end-date",
        type=str,
        help='Only keep media created before this date, e.g. "2022-01-31"',
    )

    parser.add_argument(
        "--compute-max-parallel-recordings",
        help="Compute how many recorders have recorded in parallel",
        action="store_true",
    )

    args = parser.parse_args()

    setup_logging(args.verbose)

    stats = Stats(vars(args))
