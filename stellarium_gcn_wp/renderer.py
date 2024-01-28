import asyncio
import logging
import shutil
import tempfile
import time
import multiprocessing
from dataclasses import dataclass, asdict
from pathlib import Path
from string import Template
from typing import Union, Optional

logger = logging.getLogger(__name__)


@dataclass
class RenderParams:
    # rendering parameters
    image_width: int
    image_height: int
    fov: float
    projection: str

    # Offset of the viewpoint (center of image) from the event
    # coordinates
    ra_view_offset: float
    dec_view_offset: float

    # Observer position lat/lon.
    observer_lat: float
    observer_lon: float

    # event time and position. J2000 frame
    ra: float
    dec: float
    tjd: int
    sod: int

    # styling / description for the event
    marker_color: str  # hex/html color string
    evt_str: str
    date_str: str
    pos_str: str
    en_str: str


class Renderer:
    TEMPLATE_PATH = Path(__file__).parent / "screenshot.ssc"

    def __init__(self, render_params: RenderParams, cpu_limit: float = -1):
        self._render_script = self.TEMPLATE_PATH.read_text()
        self._render_params = render_params
        self._cpu_limit = cpu_limit

    def _stellarium_cmd(self, script_path: Path, output_dir: Path):
        cmd = (f"stellarium --full-screen no "
               f"--startup-script {script_path.absolute()} "
               f"--screenshot-dir {output_dir.absolute()}")

        if self._cpu_limit > 0:
            limit = int(self._cpu_limit * multiprocessing.cpu_count() * 100)
            cmd = f"cpulimit -l {limit} -i {cmd}"

        return f"WAYLAND_DISPLAY= DISPLAY=:99 {cmd}"

    def _xvfb_cmd(self):
        return f"Xvfb :99 -screen 0 {self._render_params.image_width}x{self._render_params.image_height}x24"

    @staticmethod
    async def _wait_stdout(process, key: str):
        while key not in (l := (await process.stdout.readline()).decode().rstrip()):
            logger.debug("[stdout] %s", l)
            pass

    @staticmethod
    async def _get_window_id():
        proc = await asyncio.create_subprocess_shell("DISPLAY=:99 xdotool search --onlyvisible stellarium",
                                                     shell=True,
                                                     stdout=asyncio.subprocess.PIPE,
                                                     stderr=asyncio.subprocess.DEVNULL)
        stdout, _ = await proc.communicate()
        return int(stdout.decode().strip())

    async def _render(self, out_path: Path):
        with tempfile.TemporaryDirectory() as tmp_dir:
            # write render script with actual render parameters set
            script_file = Path(tmp_dir) / 'screenshot.ssc'
            template = Template(self._render_script)
            script_file.write_text(template.safe_substitute(asdict(self._render_params)))

            p_xvfb = None
            p_stellarium = None

            try:
                # Run Xvfb
                logger.info(f"Running Xvfb server: {self._xvfb_cmd()}")
                p_xvfb = await asyncio.create_subprocess_shell(self._xvfb_cmd(),
                                                               stderr=asyncio.subprocess.DEVNULL)
                await asyncio.sleep(3.0)

                # Run stellarium
                cmd = self._stellarium_cmd(script_file, Path(tmp_dir))
                logger.info(f"Running stellarium: {cmd}")
                p_stellarium = await asyncio.create_subprocess_shell(cmd, shell=True,
                                                                     stdout=asyncio.subprocess.PIPE,
                                                                     stderr=asyncio.subprocess.STDOUT)

                # Wait until we are rendering
                logger.info("Waiting for rendering loop to start")
                await self._wait_stdout(p_stellarium, "[SGW] render_loop")

                # Resize the window to the correct size
                logger.info("Resizing stellarium window")
                window_id = await self._get_window_id()
                await asyncio.create_subprocess_shell(f"DISPLAY=:99 xdotool windowmove {window_id} 0 0", shell=True)
                await asyncio.create_subprocess_shell(f"DISPLAY=:99 xdotool windowsize "
                                                      f"{window_id} {self._render_params.image_width} "
                                                      f"{self._render_params.image_height}", shell=True)

                logger.info("Waiting for resize")
                await self._wait_stdout(p_stellarium, "[SGW] screen_sized")

                logger.info("Waiting for screenshot")
                await self._wait_stdout(p_stellarium, "[SGW] done")

                logger.info(f"Saving screenshot to '{out_path}'")
                screenshot = Path(tmp_dir) / "screenshot.png"
                shutil.move(screenshot, out_path)

                logger.info("Done")
            finally:
                async with asyncio.timeout(5):
                    if p_xvfb:
                        p_xvfb.terminate()
                        await p_xvfb.wait()
                    if p_stellarium:
                        p_stellarium.terminate()
                        await p_stellarium.wait()

            return True

    def render(self, out_path: Union[str, Path], timeout: Optional[float] = None):
        out_path = str(out_path)

        async def _render_task():
            try:
                async with asyncio.timeout(timeout):
                    return await self._render(out_path)
            except TimeoutError:
                logger.warning("Rendering timed out, terminating")
            return False

        timeout_str = "without a timeout"
        if timeout is not None:
            timeout_str = f"with {timeout} second timeout"
        logger.info(f"Starting render {timeout_str}")

        t_start = time.time()
        result = asyncio.run(_render_task())

        logger.info(f"Rendering finished. result={result}, dt={time.time() - t_start:.2f} s")
        return result
