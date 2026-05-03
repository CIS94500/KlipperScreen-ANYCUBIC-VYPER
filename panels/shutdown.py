import logging
import os

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from ks_includes.screen_panel import ScreenPanel

BACKLIGHT_PATH = "/sys/class/backlight/intel_backlight/brightness"
MAX_BACKLIGHT_PATH = "/sys/class/backlight/intel_backlight/max_brightness"

class Panel(ScreenPanel):
    def __init__(self, screen, title):
        title = title or _("Halt")
        super().__init__(screen, title)
        self.has_backlight = os.path.exists(BACKLIGHT_PATH)
        self.has_power_devices = len(self._printer.get_power_devices()) > 0

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, vexpand=True)

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
            slider.set_draw_value(False) # desactive l'affichage du chiffre

            slider_box = Gtk.Box(valign=Gtk.Align.CENTER)
            # slider_box.set_margin_top(5)
            slider_box.add(slider)
            main_box.pack_start(slider_box, False, False, 5)

        poweroff = self._gtk.Button("shutdown", _("Shutdown"), "color1")
        poweroff.connect("clicked", self.reboot_poweroff, "shutdown")

        restart = self._gtk.Button("refresh", _("Restart"), "color2")
        restart.connect("clicked", self.reboot_poweroff, "reboot")

        restart_ks = self._gtk.Button("refresh", _("Restart") + " " + _("Screen"), "color3")
        restart_ks.connect("clicked", self._screen.restart_ks)

        power_btn = self._gtk.Button("fine-tune", _("Power"), "color4")
        power_btn.connect("clicked", self.open_power_panel)

        # boutons
        self.main = Gtk.Grid(row_homogeneous=True, column_homogeneous=True)
        self.main.set_vexpand(True)
        restart_ks.set_vexpand(True)
        restart_ks.set_hexpand(True)
        poweroff.set_vexpand(True)
        poweroff.set_hexpand(True)
        restart.set_vexpand(True)
        restart.set_hexpand(True)
        power_btn.set_vexpand(True)
        power_btn.set_hexpand(True)
        self.main.attach(restart_ks, 0, 0, 1, 1)
        self.main.attach(power_btn,  1, 0, 1, 1)
        self.main.attach(poweroff,   0, 1, 1, 1)
        self.main.attach(restart,    1, 1, 1, 1)
        main_box.pack_end(self.main, True, True, 0)
        self.content.add(main_box)

    def reboot_poweroff(self, widget, method):
        label = Gtk.Label(wrap=True, hexpand=True, vexpand=True)
        if method == "reboot":
            label.set_label(_("Are you sure you wish to reboot the system?"))
            title = _("Restart")
        else:
            label.set_label(_("Are you sure you wish to shutdown the system?"))
            title = _("Shutdown")
        buttons = []
        if (
            self._screen.apiclient is None
            or "127.0.0.1" in self._screen.apiclient.endpoint
            or "localhost" in self._screen.apiclient.endpoint
        ):
            buttons.append({"name": _("Accept"), "response": Gtk.ResponseType.ACCEPT, "style": 'dialog-primary'})
        else:
            logging.info(self._screen.apiclient.endpoint)
            buttons.extend([
                {"name": _("Host"), "response": Gtk.ResponseType.OK, "style": 'dialog-info'},
                {"name": _("Printer"), "response": Gtk.ResponseType.APPLY, "style": 'dialog-warning'},
                {"name": _("Both"), "response": Gtk.ResponseType.ACCEPT, "style": 'dialog-primary'},
            ])
        buttons.append({"name": _("Cancel"), "response": Gtk.ResponseType.CANCEL, "style": 'dialog-error'})
        self._gtk.Dialog(title, buttons, label, self.reboot_poweroff_confirm, method)

    def reboot_poweroff_confirm(self, dialog, response_id, method):
        self._gtk.remove_dialog(dialog)
        if response_id == Gtk.ResponseType.ACCEPT:
            if method == "reboot":
                self._screen._ws.send_method("machine.reboot")
                os.system("systemctl reboot -i")
            else:
                self._screen._ws.send_method("machine.shutdown")
                os.system("systemctl poweroff -i")
        elif response_id == Gtk.ResponseType.OK:
            if method == "reboot":
                os.system("systemctl reboot -i")
            else:
                os.system("systemctl poweroff -i")
        elif response_id == Gtk.ResponseType.APPLY:
            if method == "reboot":
                self._screen._ws.send_method("machine.reboot")
            else:
                self.turn_off_power_devices()
                self._screen._ws.send_method("machine.shutdown")

    def turn_off_power_devices(self):
        if self.ks_printer_cfg is not None and self._screen._ws.connected:
            power_devices = self.ks_printer_cfg.get("power_devices", "")
            if power_devices and self._printer.get_power_devices():
                logging.info(f"Turning off associated power devices: {power_devices}")
                self._screen.power_devices(widget=None, devices=power_devices, on=False)

    def set_brightness(self, scale):
        value = int(scale.get_value())
        with open(BACKLIGHT_PATH, "w") as f:
            f.write(str(value))

    def open_power_panel(self, widget):
        if not self.has_power_devices:
            self._screen.show_popup_message(_("No power devices configured"), 2)
        else:
            self._screen.show_panel("power", _("Power"))

    def back(self):
        # Si le panneau précédent est updater, on saute
        if len(self._screen._cur_panels) > 1:
            prev = self._screen._cur_panels[-2]
            if 'updater' in prev:
                self._screen._menu_go_back(home=True)
                return True

    def activate(self):
        self._screen.base_panel.toggle_shutdown_shorcut_sensitive(False)

    def deactivate(self):
        self._screen.base_panel.toggle_shutdown_shorcut_sensitive(True)

