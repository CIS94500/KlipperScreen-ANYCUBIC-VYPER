import os
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from ks_includes.screen_panel import ScreenPanel

# Ajouter dans /home/pi/KlipperScreen/config/main_menu.conf
# [menu __main brightness]
# name: Brightness
# icon: light
# panel: brightness

BACKLIGHT_PATH = "/sys/class/backlight/intel_backlight/brightness"
MAX_BACKLIGHT_PATH = "/sys/class/backlight/intel_backlight/max_brightness"

class Panel(ScreenPanel):
    def __init__(self, screen, title):
        title = title or "Brightness"
        super().__init__(screen, title)
        self.has_backlight = os.path.exists(BACKLIGHT_PATH)

        if self.has_backlight:
            with open(MAX_BACKLIGHT_PATH) as f:
                max_brightness = int(f.read().strip())
            with open(BACKLIGHT_PATH) as f:
                current = int(f.read().strip())

            slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1, max_brightness, 1)
            slider.set_value(current)
            slider.set_hexpand(True)
            slider.set_vexpand(False)
            slider.set_margin_start(20)
            slider.set_margin_end(20)
            slider.connect("value-changed", self.set_brightness)

            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER, vexpand=True)
            box.add(slider)
            self.content.add(box)

    def set_brightness(self, scale):
        value = int(scale.get_value())
        with open(BACKLIGHT_PATH, "w") as f:
            f.write(str(value))
