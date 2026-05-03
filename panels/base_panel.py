# -*- coding: utf-8 -*-
import logging
import os
import pathlib

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gio, GLib, Gtk, Pango, GdkPixbuf
from jinja2 import Environment
from datetime import datetime
from math import log
from ks_includes.screen_panel import ScreenPanel

BATTERY_PATH = "/sys/class/power_supply/axp288_fuel_gauge/capacity"

class BasePanel(ScreenPanel):
    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.current_panel = None
        self.has_battery = os.path.exists(BATTERY_PATH)
        self.time_min = -1
        self.time_format = self._config.get_main_config().getboolean("24htime", True)
        self.time_update = None
        self.spoolman_update = None
        self.titlebar_items = []
        self.titlebar_name_type = None
        self.buttons_showing = {
            'side_shutdown': False,
            'printer_select': len(self._config.get_printers()) > 1,
        }
        self.spoolman_low_limit = 20
        self.spoolman_current_color = None
        self.current_extruder = None
        self.last_usage_report = datetime.now() #cpu/mem high
        self.usage_report = 0
        # Action bar buttons
        abscale = 0.8 #VSYS self.bts * 1.1
        self.control['back'] = self._gtk.Button('back', scale=abscale)
        self.control['back'].connect("clicked", self.back)
        self.control['home'] = self._gtk.Button('main', scale=abscale)
        self.control['home'].connect("clicked", self._screen._menu_go_back, True)

        if len(self._config.get_printers()) > 1:
            self.control['printer_select'] = self._gtk.Button('shuffle', scale=abscale)
            self.control['printer_select'].connect("clicked", self._screen.show_printer_select)

        self.control['side_shutdown'] = self._gtk.Button('shutdown', scale=abscale)
        self.control['side_shutdown'].connect("clicked", self.menu_item_clicked, {
            "panel": "shutdown"
        })

        self.control['estop'] = self._gtk.Button('emergency', scale=abscale)
        self.control['estop'].connect("clicked", self.emergency_stop)

        # Any action bar button should close the keyboard
        for item in self.control:
            self.control[item].connect("clicked", self._screen.remove_keyboard)

        # Action bar
        self.action_bar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        if self._screen.vertical_mode:
            self.action_bar.set_hexpand(True)
            self.action_bar.set_vexpand(False)
        else:
            self.action_bar.set_hexpand(False)
            self.action_bar.set_vexpand(True)
        self.action_bar.get_style_context().add_class('action_bar')
        self.action_bar.set_size_request(self._gtk.action_bar_width, self._gtk.action_bar_height)
        self.action_bar.add(self.control['back'])
        self.action_bar.add(self.control['home'])
        self.show_back(False)
        self.show_home(False)
        if self.buttons_showing['printer_select']:
            self.action_bar.add(self.control['printer_select'])
        self.action_bar.add(self.control['estop'])
        self.show_estop(False)

        self.show_shutdown_shortcut(self._config.get_main_config().getboolean('side_shutdown_shortcut', True))

        # Titlebar

        # This box will be populated by show_heaters
        self.control['temp_box'] = Gtk.Box(spacing=10)

        self.titlelbl = Gtk.Label(hexpand=True, halign=Gtk.Align.CENTER, ellipsize=Pango.EllipsizeMode.END)

        self.control['time'] = Gtk.Label(label="00:00 AM")
        self.control['time_box'] = Gtk.Box(halign=Gtk.Align.END)
        self.control['time_box'].pack_end(self.control['time'], True, True, 10)
        if self.has_battery:
            self.control['battery'] = Gtk.Label(label="--%")
            self.control['time_box'].pack_end(self.control['battery'], True, True, 5)
        self.wifi_signal_icons = {
            'excellent': self._gtk.PixbufFromIcon('wifi_excellent', self._gtk.img_scale * 0.6),
        }
        self.control['wifi'] = Gtk.Image()
        self.control['time_box'].pack_end(self.control['wifi'], False, False, 5)

        self.labels['spoolman_icon'] = Gtk.Image()
        self.labels['spoolman_icon'].set_from_pixbuf(self.get_spoolman_icon_pixbuf())
        self.labels['spoolman_weight'] = Gtk.Label(label="?")
        self.control['spoolman_box'] = Gtk.Box()
        self.control['spoolman_box'].pack_start(self.labels['spoolman_icon'], False, False, 7)
        self.control['spoolman_box'].pack_start(self.labels['spoolman_weight'], False, False, 0)

        self.titlebar = Gtk.Box(spacing=5, valign=Gtk.Align.CENTER)
        self.titlebar.get_style_context().add_class("title_bar")
        self.titlebar.add(self.control['temp_box'])
        self.titlebar.add(self.titlelbl)
        self.titlebar.add(self.control['time_box'])
        self.set_title(title)

        # Main layout
        self.main_grid = Gtk.Grid()

        if self._screen.vertical_mode:
            self.main_grid.attach(self.titlebar, 0, 0, 1, 1)
            self.main_grid.attach(self.content, 0, 1, 1, 1)
            self.main_grid.attach(self.action_bar, 0, 2, 1, 1)
            self.action_bar.set_orientation(orientation=Gtk.Orientation.HORIZONTAL)
        else:
            self.main_grid.attach(self.action_bar, 0, 0, 1, 2)
            self.action_bar.set_orientation(orientation=Gtk.Orientation.VERTICAL)
            self.main_grid.attach(self.titlebar, 1, 0, 1, 1)
            self.main_grid.attach(self.content, 1, 1, 1, 1)

        self.update_time()

    def get_spoolman_icon_pixbuf(self, color=None):
        if not color:
            self.get_active_spoolman_color()
        klipperscreendir = pathlib.Path(__file__).parent.resolve().parent
        icon_path = os.path.join(klipperscreendir, "styles", self._screen.theme, "images", "spool.svg")
        icon_size = self._gtk.img_scale * self.bts * .9
        if not os.path.isfile(icon_path):
            icon_path = os.path.join(klipperscreendir, "styles", "spool.svg")
        try:
            svg = pathlib.Path(icon_path).read_text(encoding="utf-8")
            svg = svg.replace("var(--filament-color)", f"#{color}")
            stream = Gio.MemoryInputStream.new_from_data(svg.encode(), None)
            pixbuf = GdkPixbuf.Pixbuf.new_from_stream_at_scale(
                stream,
                -1,
                icon_size,
                True,
                None,
            )
            stream.close_async(2)
            return pixbuf
        except Exception as e:
            logging.error(f"Couldn't load spoolman icon: {e}")
            return self._gtk.PixbufFromIcon("spool", icon_size, icon_size)

    def get_active_spoolman_color(self):
        default_color = "000000"
        if (
                self._printer is None
                or not self._printer.active_spool
                or "filament" not in self._printer.active_spool
                or not self._printer.active_spool["filament"]
        ):
            return default_color
        filament = self._printer.active_spool["filament"]
        color = filament.get("color_hex")
        if isinstance(color, str):
            return color.strip().lstrip("#") or default_color
        return default_color

    def show_heaters(self, show=True):
        for child in self.control['temp_box'].get_children():
            self.control['temp_box'].remove(child)
        if self._printer is None or not show:
            return
        try:
            devices = self._printer.get_temp_devices()
            if not devices:
                return
            img_size = self._gtk.img_scale * self.bts
            for device in devices:
                self.labels[device] = Gtk.Label(ellipsize=Pango.EllipsizeMode.START)
                self.labels[f'{device}_box'] = Gtk.Box()
                icon = self.get_icon(device, img_size)
                if icon is not None:
                    self.labels[f'{device}_box'].pack_start(icon, False, False, 3)
                self.labels[f'{device}_box'].pack_start(self.labels[device], False, False, 0)

            # Limit the number of items according to resolution
            nlimit = int(round(log(self._screen.width, 10) * 5 - 10.5))
            n = 0
            if len(self._printer.get_tools()) > (nlimit - 1):
                self.current_extruder = self._printer.get_stat("toolhead", "extruder")
                if self.current_extruder and f"{self.current_extruder}_box" in self.labels:
                    self.control['temp_box'].add(self.labels[f"{self.current_extruder}_box"])
            else:
                self.current_extruder = False
            for device in devices:
                if n >= nlimit:
                    break
                if device.startswith("extruder") and self.current_extruder is False:
                    self.control['temp_box'].add(self.labels[f"{device}_box"])
                    n += 1
                elif device.startswith("heater"):
                    self.control['temp_box'].add(self.labels[f"{device}_box"])
                    n += 1
            for item in self.titlebar_items:
                # Users can fill the bar if they want
                if n >= nlimit + 1:
                    break
                if item == "spool" and self._printer.spoolman:
                    self.add_spoolman_box()
                    n += 1
                    continue
                for device in devices:
                    name = device.split()[1] if len(device.split()) > 1 else device
                    if name == item and self.labels[f"{device}_box"].get_parent() is None:
                        self.control['temp_box'].add(self.labels[f"{device}_box"])
                        n += 1
                        break
            if (
                n < nlimit
                and self._printer.spoolman
                and self.control['spoolman_box'].get_parent() != self.control['temp_box']
            ):
                self.add_spoolman_box()
                n += 1

            self.control['temp_box'].show_all()
        except Exception as e:
            logging.debug(f"Couldn't create heaters box: {e}")

    def add_spoolman_box(self):
        self.control['temp_box'].add(self.control['spoolman_box'])
        self.set_spoolman_refresh()
        self.fetch_spoolman()

    def get_icon(self, device, img_size):
        if device.startswith("extruder"):
            if self._printer.extrudercount > 1:
                if device == "extruder":
                    device = "extruder0"
                return self._gtk.Image(f"extruder-{device[8:]}", img_size, img_size)
            return self._gtk.Image("extruder", img_size, img_size)
        elif device.startswith("heater_bed"):
            return self._gtk.Image("bed", img_size, img_size)
        # Extra items
        elif self.titlebar_name_type is not None:
            # The item has a name, do not use an icon
            return None
        elif device.startswith("temperature_fan"):
            return self._gtk.Image("fan", img_size, img_size)
        elif device.startswith("heater_generic"):
            return self._gtk.Image("heater", img_size, img_size)
        else:
            return self._gtk.Image("heat-up", img_size, img_size)

    def activate(self):
        if self.time_update is None:
            self.time_update = GLib.timeout_add_seconds(1, self.update_time)

    def set_spoolman_refresh(self):
        if self.spoolman_update is None:
            self.spoolman_update = GLib.timeout_add_seconds(60, self.fetch_spoolman)

    def add_content(self, panel):
        self.current_panel = panel
        self.set_title(panel.title)
        self.content.add(panel.content)

    def update_spoolman_alert_visuals(self, alert):
        if alert:
            self.labels['spoolman_weight'].get_style_context().add_class("spoolman_low")
        else:
            self.labels['spoolman_weight'].get_style_context().remove_class("spoolman_low")

    def update_spoolman_weight_label(self):
        if self._printer is None:
            return
        if (
            not self._printer.spoolman
            or not self._printer.active_spool
            or "remaining_weight" not in self._printer.active_spool
            or self._printer.active_spool["remaining_weight"] is None
        ):
            self.update_spoolman_alert_visuals(False)
            self.labels['spoolman_weight'].set_label("?")
            return
        remaining_weight = self._printer.active_spool["remaining_weight"]
        self.labels['spoolman_weight'].set_label(f'{round(remaining_weight):.0f} g')
        self.update_spoolman_alert_visuals(remaining_weight < self.spoolman_low_limit)
        color = self.get_active_spoolman_color()
        if color != self.spoolman_current_color:
            self.labels['spoolman_icon'].set_from_pixbuf(self.get_spoolman_icon_pixbuf(color))
            self.spoolman_current_color = color

    def fetch_spoolman(self):
        if (
            not self._printer
            or 'printer_select' in self._screen._cur_panels
            or self.control['spoolman_box'].get_parent() != self.control['temp_box']
        ):
            logging.debug("Stopping Spoolman updates")
            self.spoolman_update = None
            return False
        logging.debug("Fetching Spoolman")
        self._screen.update_spool_data()
        self.update_spoolman_weight_label()
        return True

    def back(self, widget=None):
        if self.current_panel is None:
            return
        self._screen.remove_keyboard()
        if hasattr(self.current_panel, "back") \
                and not self.current_panel.back() \
                or not hasattr(self.current_panel, "back"):
            self._screen._menu_go_back()

    def process_update(self, action, data):
        if action == "notify_active_spool_set":
            self.update_spoolman_weight_label()
            return
        if action == "notify_proc_stat_update":
            cpu = data["system_cpu_usage"]["cpu"]
            memory = (data["system_memory"]["used"] / data["system_memory"]["total"]) * 100
            error = "message_cpu_warning"
            ctx = self.titlebar.get_style_context()
            msg = f"CPU: {cpu:2.0f}%    RAM: {memory:2.0f}%"
            if cpu > 80 or memory > 85:
                if self.usage_report < 3:
                    self.usage_report += 1
                    return
                self.last_usage_report = datetime.now()
                if not ctx.has_class(error):
                    ctx.add_class(error)
                self._screen.log_notification(f"{self._screen.connecting_to_printer}: {msg}", 2)
                self.titlelbl.set_label(msg)
            elif ctx.has_class(error):
                if (datetime.now() - self.last_usage_report).seconds < 5:
                    self.titlelbl.set_label(msg)
                    return
                self.usage_report = 0
                ctx.remove_class(error)
                self.titlelbl.set_label(f"{self._screen.connecting_to_printer}")
            return

        if action == "notify_update_response":
            if self.update_dialog is None:
                self.show_update_dialog()
            if 'message' in data:
                self.labels['update_progress'].set_text(
                    f"{self.labels['update_progress'].get_text().strip()}\n"
                    f"{data['message']}\n")
            if 'complete' in data and data['complete']:
                logging.info("Update complete")
                if self.update_dialog is not None:
                    try:
                        self.update_dialog.set_response_sensitive(Gtk.ResponseType.OK, True)
                        self.update_dialog.get_widget_for_response(Gtk.ResponseType.OK).show()
                    except AttributeError:
                        logging.error("error trying to show the updater button the dialog might be closed")
                        self._screen.updating = False
                        for dialog in self._screen.dialogs:
                            self._gtk.remove_dialog(dialog)
            return
        if action != "notify_status_update" or self._screen.printer is None:
            return
        devices = self._printer.get_temp_devices()
        if not devices:
            return
        for device in devices:
            temp = self._printer.get_stat(device, "temperature")
            if temp and device in self.labels:
                name = ""
                if not (device.startswith("extruder") or device.startswith("heater_bed")):
                    if self.titlebar_name_type == "full":
                        name = device.split()[1] if len(device.split()) > 1 else device
                        name = f'{self.prettify(name)}: '
                    elif self.titlebar_name_type == "short":
                        name = device.split()[1] if len(device.split()) > 1 else device
                        name = f"{name[:1].upper()}: "
                self.labels[device].set_label(f"{name}{temp:.0f}°")

        if (self.current_extruder and 'toolhead' in data and 'extruder' in data['toolhead']
                and data["toolhead"]["extruder"] != self.current_extruder):
            self.control['temp_box'].remove(self.labels[f"{self.current_extruder}_box"])
            self.current_extruder = data["toolhead"]["extruder"]
            self.control['temp_box'].pack_start(self.labels[f"{self.current_extruder}_box"], True, True, 3)
            self.control['temp_box'].reorder_child(self.labels[f"{self.current_extruder}_box"], 0)
            self.control['temp_box'].show_all()

        return False

    def remove(self, widget):
        self.content.remove(widget)

    def show_back(self, show=True):
        self.control['back'].set_sensitive(show)

    def show_home(self, show=True):
        self.control['home'].set_sensitive(show)

    def show_shutdown_shortcut(self, show=True):
        if show is True and self.buttons_showing['side_shutdown'] is False:
            self.action_bar.add(self.control['side_shutdown'])
            self.control['side_shutdown'].show()
            self.buttons_showing['side_shutdown'] = True
        elif show is False and self.buttons_showing['side_shutdown'] is True:
            self.action_bar.remove(self.control['side_shutdown'])
            self.buttons_showing['side_shutdown'] = False

    def toggle_shutdown_shorcut_sensitive(self, value=True):
        self.control['side_shutdown'].set_sensitive(value)

    def show_printer_select(self, show=True):
        if show and self.buttons_showing['printer_select'] is False:
            self.action_bar.add(self.control['printer_select'])
            self.action_bar.reorder_child(self.control['printer_select'], 2)
            self.buttons_showing['printer_select'] = True
            self.control['printer_select'].show()
        elif show is False and self.buttons_showing['printer_select']:
            self.action_bar.remove(self.control['printer_select'])
            self.buttons_showing['printer_select'] = False

    def set_title(self, title):
        self.titlebar.get_style_context().remove_class("message_cpu_warning")
        if not title:
            self.titlelbl.set_label(f"{self._screen.connecting_to_printer}")
            return
        try:
            env = Environment(extensions=["jinja2.ext.i18n"], autoescape=True)
            env.install_gettext_translations(self._config.get_lang())
            j2_temp = env.from_string(title)
            title = j2_temp.render()
        except Exception as e:
            logging.debug(f"Error parsing jinja for title: {title}\n{e}")

        self.titlelbl.set_label(f"{self._screen.connecting_to_printer} | {title}")

    def update_time(self):
        now = datetime.now()
        confopt = self._config.get_main_config().getboolean("24htime", True)
        if now.minute != self.time_min or self.time_format != confopt:
            if confopt:
                self.control['time'].set_text(f'{now:%H:%M }')
            else:
                self.control['time'].set_text(f'{now:%I:%M %p}')
            self.time_min = now.minute
            self.time_format = confopt
            self.update_wifi_icon()
        try:
            if self.has_battery:
                with open(BATTERY_PATH) as f:
                    capacity = int(f.read().strip())
                self.control['battery'].set_label(f"{capacity}%")
        except:
            pass
        return True

    def show_estop(self, show=True):
        if show:
            self.control['estop'].set_sensitive(True)
            return
        self.control['estop'].set_sensitive(False)

    def set_ks_printer_cfg(self, printer):
        ScreenPanel.ks_printer_cfg = self._config.get_printer_config(printer)
        if self.ks_printer_cfg is not None:
            self.titlebar_name_type = self.ks_printer_cfg.get("titlebar_name_type", None)
            titlebar_items = self.ks_printer_cfg.get("titlebar_items", None)
            if titlebar_items is not None:
                self.titlebar_items = [str(i.strip()) for i in titlebar_items.split(',')]
                logging.info(f"Titlebar name type: {self.titlebar_name_type} items: {self.titlebar_items}")
            else:
                self.titlebar_items = []
            self.spoolman_low_limit = self.ks_printer_cfg.getfloat("spool_low_limit", fallback=20)
        else:
            self.titlebar_items = []
            self.spoolman_low_limit = 20

    def show_update_dialog(self):
        if self.update_dialog is not None:
            return
        button = [{"name": _("Finish"), "response": Gtk.ResponseType.OK, "style": "dialog-default"}]

        self.labels['update_progress'] = Gtk.Label(halign=Gtk.Align.START, valign=Gtk.Align.START, ellipsize=Pango.EllipsizeMode.END)

        self.labels['update_scroll'] = self._gtk.ScrolledWindow(steppers=False)
        self.labels['update_scroll'].set_property("overlay-scrolling", True)
        self.labels['update_scroll'].add(self.labels['update_progress'])
        self.labels['update_scroll'].connect("size-allocate", self._autoscroll)
        dialog = self._gtk.Dialog(_("Updating"), button, self.labels['update_scroll'], self.finish_updating)
        dialog.connect("delete-event", self.close_update_dialog)
        dialog.set_response_sensitive(Gtk.ResponseType.OK, False)
        dialog.get_widget_for_response(Gtk.ResponseType.OK).hide()
        self.update_dialog = dialog
        self._screen.updating = True

    def finish_updating(self, dialog, response_id):
        if response_id != Gtk.ResponseType.OK:
            return
        logging.info("Finishing update")
        self._screen.updating = False
        self.update_dialog = None #VSYS
        self._gtk.remove_dialog(dialog)
        self._screen._menu_go_back(home=True)

    def close_update_dialog(self, *args):
        logging.info("Closing update dialog")
        if self.update_dialog in self._screen.dialogs:
            self._screen.dialogs.remove(self.update_dialog)
        self.update_dialog = None
        self._screen._menu_go_back(home=True)

    def update_wifi_icon(self):
        if 'wifi' not in self.control or not hasattr(self, 'wifi_signal_icons'):
            return
        connected = self.get_wifi_signal()
        if connected:
            self.control['wifi'].set_from_pixbuf(self.wifi_signal_icons['excellent'])
            self.control['wifi'].show()
        else:
            self.control['wifi'].hide()

    def get_wifi_signal(self):
        try:
            import subprocess
            result = subprocess.run(['nmcli', '-f', 'ACTIVE', 'dev', 'wifi'],
                                   capture_output=True, text=True)
            for line in result.stdout.split('\n'):
                if 'oui' in line or 'yes' in line:
                    return True
            return False
        except:
            return False
