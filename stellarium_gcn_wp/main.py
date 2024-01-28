import argparse
import dataclasses
import datetime
import random
import sys
import time
from pathlib import Path

from stellarium_gcn_wp.gcn_consumer import GCNConsumer
from stellarium_gcn_wp.gcn_parser import GCNParser, GCNNotice
from stellarium_gcn_wp.renderer import RenderParams, Renderer
from stellarium_gcn_wp.settings import Settings

from queue import Queue, Empty

import logging

logger = logging.getLogger(__name__)


def tjd_sod_to_datetime_utc(tjd: int, sod: int) -> datetime.datetime:
    return datetime.datetime.utcfromtimestamp((tjd - 587) * 86400 + sod)


def make_render_params(notice: GCNNotice) -> RenderParams:
    ts = tjd_sod_to_datetime_utc(notice.tjd, notice.sod)

    color = "#ffbf00"  # gold
    if "Bronze" in notice.notice_type:
        color = "#CD7F32"  # bronze

    return RenderParams(
        image_width=Settings.image_width,
        image_height=Settings.image_height,
        fov=Settings.fov,
        projection=Settings.projection,
        ra_view_offset=Settings.ra_view_offset,
        dec_view_offset=Settings.dec_view_offset,
        observer_lon=Settings.observer_location[0],
        observer_lat=Settings.observer_location[1],
        ra=notice.ra,
        dec=notice.dec,
        tjd=notice.tjd,
        sod=notice.sod,
        marker_color=color,
        evt_str=notice.notice_type,
        date_str=f"{ts.isoformat()} UTC",
        pos_str=f"{notice.gal_lon:.2f}° lon, {notice.gal_lat:.2f}° lat galactic",
        en_str=f"{notice.energy:.4e} TeV"
    )


def run(queue: Queue, once: bool):
    while True:
        logger.info("Waiting for GCN Notice")
        while True:
            try:
                gcn_text = queue.get(block=True, timeout=0.5)
                break
            except Empty:
                continue

        notice = GCNParser.parse(gcn_text)
        logger.info(f"Parsed GCN notice: {notice}")

        logger.info("Rendering")
        rp = make_render_params(notice)
        renderer = Renderer(render_params=rp, cpu_limit=Settings.render_cpu_limit)
        out_filename = Path(Settings.out_file_name.format(**dataclasses.asdict(notice)))
        out_filename = out_filename.expanduser().resolve()
        out_filename.parent.mkdir(parents=True, exist_ok=True)

        renderer.render(out_filename, Settings.render_timeout)
        logger.info(f"Render for event {notice.evt_num} saved to {out_filename}")

        for cb in Settings.post_render_callbacks:
            cb(out_filename)

        queue.task_done()

        if once:
            return


def main():
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format="[%(asctime)s] %(levelname)s %(name)s: %(message)s")
    random.seed(time.time())

    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--start",
                        type=str, choices=["first", "last", "next", "track"], default="last")
    parser.add_argument("-t", "--type",
                        type=str, default="gold,bronze")
    parser.add_argument("-1", "--once", action="store_true", default=False)
    parser.add_argument("-o", "--output", type=str)
    parser.add_argument("-i", "--init-tracking", action="store_true", default=False)

    args = parser.parse_args()

    if args.output is not None:
        Settings.out_file_name = args.output

    types = args.type.split(",")
    types = [t.strip() for t in types]
    topics = []
    for t in types:
        if t == "gold":
            t = 'gcn.classic.text.ICECUBE_ASTROTRACK_GOLD'
        if t == "bronze":
            t = 'gcn.classic.text.ICECUBE_ASTROTRACK_BRONZE'
        topics.append(t)

    queue = Queue()
    consumer = GCNConsumer(queue, start_on=args.start, topics=topics)
    consumer.start()

    # If we are initializing tracking, we want to consume every event and commit it,
    # so we start at the end of the stream in the future
    if args.init_tracking:
        if not args.start == "track":
            logger.warning(f"Can only initialize tracking when --start is 'track'. Is currently '{args.start}'")

        logger.info("Initializing tracking by moving to end of stream")
        while True:
            try:
                _ = queue.get(True, 10.0)
                queue.task_done()
            except Empty:
                logger.info("Done initializing tracking.")
                exit(0)

    try:
        logger.info("Starting main loop")
        run(queue, args.once)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        consumer.stop()


if __name__ == "__main__":
    main()
