import os
import random
from dataclasses import dataclass
from http.client import HTTPSConnection
from pathlib import Path
from typing import Callable, Tuple

from stellarium_gcn_wp import hooks


@dataclass
class _Settings:
    # GCN Kafka ID and secret
    # If these are set to none, they are read from the STELLARIUM_GCN_KAFKA_ID
    # and STELLARIUM_GCN_KAFKA_SECRET environment varibales
    _gcn_kafka_id: str | None = None
    _gcn_kafka_secret: str | None = None

    # Group ID used in the kafka subscriber when in 'track' mode, where we subscribe
    # to, and commit, to all gcn's we have seen. Useful if this script isn't always
    # running, and you want to start of from where you left off last time.
    gcn_kafka_group_id: str = "stellarium-gcn-wp"

    # Image output settings
    image_width: int = 1920
    image_height: int = 1200
    fov: float = 180.0
    projection: str = "ProjectionCylinder"

    # Limits cpu usage of rendering. Between (0, 1], where 1 allows 100% of cpu to be
    # used. Setting this to a negative value disables cpu limiting completely
    render_cpu_limit: float = 0.2

    # Timeout for the renderer, in seconds. Note that rendering will take a long time,
    # in general, since we are running stellarium in Xvfb (so it runs in the background),
    # which means we are doing software-rendering
    render_timeout: float = 25 * 60

    # Output filename for each generated render. You can use any property of
    # the GCNNotice dataclass in this format string. See gcn_parser.py
    out_file_name = "~/Pictures/stellarium-gcn/wallpaper_{evt_num}_{revision}.png"

    # Functions called with the path of the path of the rendered image.
    # Can be set to one of the functions in hooks.py to automatically set the
    # desktop wallpaper
    post_render_callbacks: Tuple[Callable[[Path], None]] = (hooks.kde_set_wallpaper,
                                                            hooks.kde_set_lockscreen)

    # Observer location can be a tuple of (lat, lon) or None, in which case
    # the location will be set based on the host machines (ip-based) location
    _oberserver_location: tuple[float, float] | None = (-89.99, -63.453056)

    # The offset of the viewpoint from the direction of the rendered event.
    # If this is 0,0 the event will be exactly in the center of the image
    _ra_view_offset: float | Callable[[], float] = lambda: random.uniform(-50, 50)
    _dec_view_offset: float | Callable[[], float] = lambda: random.uniform(-20, 20)

    @property
    def gcn_kafka_id(self):
        if self._gcn_kafka_id is None:
            id = os.environ.get("STELLARIUM_GCN_KAFKA_ID", None)
            if id is None:
                raise RuntimeError("No gcn kafka id defined,"
                                   " and STELLARIUM_GCN_KAFKA_ID environment variable is unset.")
            return id
        return self._gcn_kafka_id

    @property
    def gcn_kafka_secret(self):
        if self._gcn_kafka_secret is None:
            secret = os.environ.get("STELLARIUM_GCN_KAFKA_SECRET", None)
            if secret is None:
                raise RuntimeError("No gcn kafka secret defined,"
                                   " and STELLARIUM_GCN_KAFKA_SECRET environment variable is unset.")
            return secret
        return self._gcn_kafka_secret

    @property
    def observer_location(self):
        if self._oberserver_location is None:
            conn = HTTPSConnection("ipinfo.io")
            conn.request("GET", "/loc")
            resp = conn.getresponse()
            lat, lon = resp.readline().decode().strip().split(",")
            return float(lat), float(lon)
        return self._oberserver_location

    @property
    def ra_view_offset(self):
        if isinstance(self._ra_view_offset, Callable):
            return self._ra_view_offset()
        return self._ra_view_offset

    @property
    def dec_view_offset(self):
        if isinstance(self._dec_view_offset, Callable):
            return self._dec_view_offset()
        return self._dec_view_offset


Settings = _Settings()
