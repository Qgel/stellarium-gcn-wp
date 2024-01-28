import subprocess
from pathlib import Path

import logging
logger = logging.getLogger(__name__)

# Wallpaper setters for KDE
def kde_set_wallpaper(image_path: Path):
    logger.info(f"Setting KDE wallpaper to {image_path}")
    subprocess.run(f"plasma-apply-wallpaperimage {image_path.absolute()}", shell=True)


def kde_set_lockscreen(image_path: Path):
    logger.info(f"Setting KDE lockscreen image to {image_path}")
    subprocess.run(f"kwriteconfig5 --file kscreenlockerrc --group Greeter --group Wallpaper"
                   f" --group org.kde.image --group General --key Image {image_path.absolute()}", shell=True)

# Wallpaper setters for Gnome
def gnome3_light_theme_set_wallpaper(image_path: Path):
    gnome3_set_wallpaper(image_path, False)

def gnome3_dark_theme_set_wallpaper(image_path: Path):
    gnome3_set_wallpaper(image_path, True)

def gnome3_set_wallpaper(image_path: Path, dark: bool):
    theme = "dark" if dark else "light"
    logger.info(f"Setting Gnome3 {theme}-theme wallpaper to {image_path}")
    config_key = "picture-uri-dark" if dark else "picture-uri"
    subprocess.run(f"gsettings set org.gnome.desktop.background {config_key} file://{image_path.absolute()}",
                   shell=True)