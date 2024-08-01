import logging
import re
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango
from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel
from ks_includes.widgets.autogrid import AutoGrid


class Panel(ScreenPanel):

    def __init__(self, screen, title):
        title = title or _("Extrude")
        super().__init__(screen, title)
        self.current_extruder = self._printer.get_stat("toolhead", "extruder")
        macros = self._printer.get_gcode_macros()
        self.load_filament = any("LOAD_FILAMENT" in macro.upper() for macro in macros)
        self.unload_filament = any("UNLOAD_FILAMENT" in macro.upper() for macro in macros)
        self.extrude_filament = any("_EXTRUDE" in macro.upper() for macro in macros) #VSYS
        self.wait_temp = any("_WAIT_TEMP" in macro.upper() for macro in macros) #VSYS

        self.speeds = ['1', '2', '5', '25']
        self.distances = ['5', '10', '15', '25']

        if self.ks_printer_cfg is not None:
            dis = self.ks_printer_cfg.get("extrude_distances", 'None')
            if re.match(r'^[0-9,\s]+$', dis):
                dis = [str(i.strip()) for i in dis.split(',')]
                if 1 < len(dis) < 5:
                    self.distances = dis
            vel = self.ks_printer_cfg.get("extrude_speeds", 'None')
            if re.match(r'^[0-9,\s]+$', vel):
                vel = [str(i.strip()) for i in vel.split(',')]
                if 1 < len(vel) < 5:
                    self.speeds = vel

        self.distance = int(self.distances[1])
        self.speed = int(self.speeds[2])
        self.buttons = {
            'extrude': self._gtk.Button("extrude", _("Extrude"), "color4"),
            'load': self._gtk.Button("arrow-down", _("Load"), "color3"),
            'unload': self._gtk.Button("arrow-up", _("Unload"), "color2"),
            'retract': self._gtk.Button("retract", _("Retract"), "color1"),
            'temperature': self._gtk.Button("heat-up", _("Temperature"), "color4"),
            'spoolman': self._gtk.Button("spoolman", "Spoolman", "color3"),
            'pressure': self._gtk.Button("pressure_advance", _("Pressure Advance"), "color2"),
            'retraction': self._gtk.Button("settings", _("Retraction"), "color1")
        }
        self.buttons['extrude'].connect("clicked", self.check_min_temp, "extrude", "+")
        self.buttons['load'].connect("clicked", self.check_min_temp, "load_unload", "+")
        self.buttons['unload'].connect("clicked", self.check_min_temp, "load_unload", "-")
        self.buttons['retract'].connect("clicked", self.check_min_temp, "extrude", "-")
        self.buttons['temperature'].connect("clicked", self.menu_item_clicked, {
            "panel": "temperature"
        })

        self.buttons['spoolman'].connect("clicked", self.menu_item_clicked, {
            "panel": "spoolman"
        })
        self.buttons['pressure'].connect("clicked", self.menu_item_clicked, {
            "panel": "pressure_advance"
        })
        self.buttons['retraction'].connect("clicked", self.menu_item_clicked, {
            "panel": "retraction"
        })

        xbox = Gtk.Box(homogeneous=True)
        limit = 4
        i = 0
        extruder_buttons = []
        for extruder in self._printer.get_tools():
            if self._printer.extrudercount == 1:
                self.labels[extruder] = self._gtk.Button("extruder", "")
            else:
                n = self._printer.get_tool_number(extruder)
                self.labels[extruder] = self._gtk.Button(f"extruder-{n}", f"T{n}")
                self.labels[extruder].connect("clicked", self.change_extruder, extruder)
            if extruder == self.current_extruder:
                self.labels[extruder].get_style_context().add_class("button_active")
            if self._printer.extrudercount < limit:
                xbox.add(self.labels[extruder])
                i += 1
            else:
                extruder_buttons.append(self.labels[extruder])
        if extruder_buttons:
            self.labels['extruders'] = AutoGrid(extruder_buttons, vertical=self._screen.vertical_mode)
            self.labels['extruders_menu'] = self._gtk.ScrolledWindow()
            self.labels['extruders_menu'].add(self.labels['extruders'])
        if self._printer.extrudercount >= limit:
            changer = self._gtk.Button("toolchanger")
            changer.connect("clicked", self.load_menu, 'extruders', _('Extruders'))
            xbox.add(changer)
            self.labels["current_extruder"] = self._gtk.Button("extruder", "")
            xbox.add(self.labels["current_extruder"])
            self.labels["current_extruder"].connect("clicked", self.load_menu, 'extruders', _('Extruders'))
#Begin VSYS
        if self._printer.spoolman:
            xbox.add(self.buttons['spoolman'])
            i += 1        
        else:
            if not self._screen.vertical_mode:  
                xbox.add(self.buttons['pressure'])
                i += 1
            if self._printer.get_config_section("firmware_retraction") and not self._screen.vertical_mode:
                xbox.add(self.buttons['retraction'])
                i += 1
        if i < limit:
            xbox.add(self.buttons['temperature'])
#End VSYS
        distgrid = Gtk.Grid()
        for j, i in enumerate(self.distances):
            x = int(i)
            self.labels[f"dist{x}"] = self._gtk.Button(label=i)
            self.labels[f"dist{x}"].connect("clicked", self.change_distance, int(x))
            ctx = self.labels[f"dist{x}"].get_style_context()
            if ((self._screen.lang_ltr is True and j == 0) or
                    (self._screen.lang_ltr is False and j == len(self.distances) - 1)):
                ctx.add_class("distbutton_top")
            elif ((self._screen.lang_ltr is False and j == 0) or
                  (self._screen.lang_ltr is True and j == len(self.distances) - 1)):
                ctx.add_class("distbutton_bottom")
            else:
                ctx.add_class("distbutton")
            if x == int(self.distance):
                ctx.add_class("distbutton_active")
            distgrid.attach(self.labels[f"dist{x}"], j, 0, 1, 1)

        speedgrid = Gtk.Grid()
        for j, i in enumerate(self.speeds):
            x = int(i)
            self.labels[f"speed{x}"] = self._gtk.Button(label=i)
            self.labels[f"speed{x}"].connect("clicked", self.change_speed, int(x))
            ctx = self.labels[f"speed{x}"].get_style_context()
            if ((self._screen.lang_ltr is True and j == 0) or
                    (self._screen.lang_ltr is False and j == len(self.speeds) - 1)):
                ctx.add_class("distbutton_top")
            elif ((self._screen.lang_ltr is False and j == 0) or
                  (self._screen.lang_ltr is True and j == len(self.speeds) - 1)):
                ctx.add_class("distbutton_bottom")
            else:
                ctx.add_class("distbutton")
            if x == int(self.speed):
                ctx.add_class("distbutton_active")
            speedgrid.attach(self.labels[f"speed{x}"], j, 0, 1, 1)

        distbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.labels['extrude_dist'] = Gtk.Label(_("Distance (mm)"))
        distbox.pack_start(self.labels['extrude_dist'], True, True, 0)
        distbox.add(distgrid)
        speedbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.labels['extrude_speed'] = Gtk.Label(_("Speed (mm/s)"))
        speedbox.pack_start(self.labels['extrude_speed'], True, True, 0)
        speedbox.add(speedgrid)

        filament_sensors = self._printer.get_filament_sensors()
        sensors = Gtk.Grid()
#Begin VSYS
        #sensors.set_size_request(self._gtk.content_width, -1) #VSYS
        if len(filament_sensors) > 0:
            sensors.set_column_spacing(5)
            sensors.set_row_spacing(5)
            sensors.set_halign(Gtk.Align.CENTER)
            sensors.set_valign(Gtk.Align.CENTER)
            for s, x in enumerate(filament_sensors):
                if s > limit:
                    break
                name = x[23:].strip()
                self.labels[x] = {
                    'label': Gtk.Label(self.prettify(name)),
                    'switch': Gtk.Switch(),
                    'box': Gtk.Box()
                }
                self.labels[x]['label'].set_halign(Gtk.Align.CENTER)
                self.labels[x]['label'].set_hexpand(True)
                self.labels[x]['label'].set_ellipsize(Pango.EllipsizeMode.END)
                self.labels[x]['switch'].set_property("width-request", round(self._gtk.font_size * 2))
                self.labels[x]['switch'].set_property("height-request", round(self._gtk.font_size))
                self.labels[x]['switch'].connect("notify::active", self.enable_disable_fs, name, x)
                self.labels[x]['box'].pack_start(self.labels[x]['label'], True, True, 5) #VSYS
                self.labels[x]['box'].pack_start(self.labels[x]['switch'], False, False, 0) #VSYS
                self.labels[x]['box'].get_style_context().add_class("filament_sensor")
                self.labels[x]['box'].set_hexpand(True) #VSYS
                sensors.attach(self.labels[x]['box'], s, 0, 1, 1)
#End VSYS

        grid = Gtk.Grid(column_homogeneous=True)
        grid.attach(xbox, 0, 0, 4, 1)

        if self._screen.vertical_mode:
            grid.attach(self.buttons['extrude'], 0, 1, 2, 1)
            grid.attach(self.buttons['retract'], 2, 1, 2, 1)
            grid.attach(self.buttons['load'], 0, 2, 2, 1)
            grid.attach(self.buttons['unload'], 2, 2, 2, 1)
            settings_box = Gtk.Box(homogeneous=True)
            settings_box.add(self.buttons['pressure'])
            if self._printer.get_config_section("firmware_retraction"):
                settings_box.add(self.buttons['retraction'])
            grid.attach(settings_box, 0, 3, 4, 1)
            grid.attach(distbox, 0, 4, 4, 1)
            grid.attach(speedbox, 0, 5, 4, 1)
            grid.attach(sensors, 0, 6, 4, 1)
        else:
            grid.attach(self.buttons['extrude'], 0, 2, 1, 1)
            grid.attach(self.buttons['load'], 1, 2, 1, 1)
            grid.attach(self.buttons['unload'], 2, 2, 1, 1)
            grid.attach(self.buttons['retract'], 3, 2, 1, 1)
            grid.attach(distbox, 0, 3, 2, 1)
            grid.attach(speedbox, 2, 3, 2, 1)
            grid.attach(sensors, 0, 4, 4, 1)

        self.menu = ['extrude_menu']
        self.labels['extrude_menu'] = grid
        self.content.add(self.labels['extrude_menu'])

    def process_busy(self, busy):
        for button in self.buttons:
            if button in ("pressure", "retraction", "spoolman", "temperature"):
                continue
            self.buttons[button].set_sensitive((not busy))

    def process_update(self, action, data):
        if action == "notify_busy":
            self.process_busy(data)
            return
        if action != "notify_status_update":
            return
        for x in self._printer.get_tools():
            if x in data:
                self.update_temp(
                    x,
                    self._printer.get_stat(x, "temperature"),
                    self._printer.get_stat(x, "target"),
                    self._printer.get_stat(x, "power"),
                    lines=2,
                )
        if "current_extruder" in self.labels:
            self.labels["current_extruder"].set_label(self.labels[self.current_extruder].get_label())

        if ("toolhead" in data and "extruder" in data["toolhead"] and
                data["toolhead"]["extruder"] != self.current_extruder):
            for extruder in self._printer.get_tools():
                self.labels[extruder].get_style_context().remove_class("button_active")
            self.current_extruder = data["toolhead"]["extruder"]
            self.labels[self.current_extruder].get_style_context().add_class("button_active")
            if "current_extruder" in self.labels:
                n = self._printer.get_tool_number(self.current_extruder)
                self.labels["current_extruder"].set_image(self._gtk.Image(f"extruder-{n}"))

        for x in self._printer.get_filament_sensors():
            if x in data and x in self.labels:
                if 'enabled' in data[x]:
                    self.labels[x]['switch'].set_active(data[x]['enabled'])
                if 'filament_detected' in data[x]:
                    if self._printer.get_stat(x, "enabled"):
                        if data[x]['filament_detected']:
                            self.labels[x]['box'].get_style_context().remove_class("filament_sensor_empty")
                            self.labels[x]['box'].get_style_context().add_class("filament_sensor_detected")
                        else:
                            self.labels[x]['box'].get_style_context().remove_class("filament_sensor_detected")
                            self.labels[x]['box'].get_style_context().add_class("filament_sensor_empty")
                logging.info(f"{x}: {self._printer.get_stat(x)}")

    def change_distance(self, widget, distance):
        logging.info(f"### Distance {distance}")
        self.labels[f"dist{self.distance}"].get_style_context().remove_class("distbutton_active")
        self.labels[f"dist{distance}"].get_style_context().add_class("distbutton_active")
        self.distance = distance

    def change_extruder(self, widget, extruder):
        logging.info(f"Changing extruder to {extruder}")
        for tool in self._printer.get_tools():
            self.labels[tool].get_style_context().remove_class("button_active")
        self.labels[extruder].get_style_context().add_class("button_active")

        self._screen._ws.klippy.gcode_script(f"T{self._printer.get_tool_number(extruder)}")

    def change_speed(self, widget, speed):
        logging.info(f"### Speed {speed}")
        self.labels[f"speed{self.speed}"].get_style_context().remove_class("distbutton_active")
        self.labels[f"speed{speed}"].get_style_context().add_class("distbutton_active")
        self.speed = speed

    def check_min_temp(self, widget, method, direction):
        if not self.wait_temp: #VSYS
            temp = int(self._printer.get_stat(self.current_extruder, 'temperature'))
            target = int(self._printer.get_stat(self.current_extruder, 'target'))
            min_extrude_temp = int(self._printer.config[self.current_extruder].get('min_extrude_temp', 170))
            if temp < min_extrude_temp:
                if target > min_extrude_temp:
                    self._screen.show_popup_message(_("Please wait for the nozzle to heat up to" ) + f" {target}°C...", level=1)
                    self._screen._ws.klippy.gcode_script(f"M109 S{target}")
                else:
                    self._screen.show_popup_message(_("Temperature too low to extrude"))
                    self.menu_item_clicked(
                        widget,
                        {"panel": "temperature", 'extra': self.current_extruder}
                    )
                    return
        if method == "extrude":
            self.extrude(widget, direction)
        elif method == "load_unload":
            self.load_unload(widget, direction)

#Begin VSYS
    def extrude(self, widget, direction):
        if not self.extrude_filament:
            self._screen._ws.klippy.gcode_script(KlippyGcodes.EXTRUDE_REL)
            self._screen._ws.klippy.gcode_script(KlippyGcodes.extrude(f"{direction}{self.distance}", f"{self.speed * 60}"))
        else:
            self._screen._ws.klippy.gcode_script(f"_EXTRUDE DIR={direction} DIST={self.distance} SPEED={self.speed * 60}")
#End VSYS

    def load_unload(self, widget, direction):
        if direction == "-":
            if not self.unload_filament:
                self._screen.show_popup_message("Macro UNLOAD_FILAMENT not found")
            else:
                self._screen._ws.klippy.gcode_script(f"UNLOAD_FILAMENT") #SPEED={self.speed * 60}") VSYS
        if direction == "+":
            if not self.load_filament:
                self._screen.show_popup_message("Macro LOAD_FILAMENT not found")
            else:
                self._screen._ws.klippy.gcode_script(f"LOAD_FILAMENT") #SPEED={self.speed * 60}") VSYS

    def enable_disable_fs(self, switch, gparams, name, x):
        if switch.get_active():
            self._screen._ws.klippy.gcode_script(f"SET_FILAMENT_SENSOR SENSOR={name} ENABLE=1")
            if self._printer.get_stat(x, "filament_detected"):
                self.labels[x]['box'].get_style_context().add_class("filament_sensor_detected")
            else:
                self.labels[x]['box'].get_style_context().add_class("filament_sensor_empty")
        else:
            self._screen._ws.klippy.gcode_script(f"SET_FILAMENT_SENSOR SENSOR={name} ENABLE=0")
            self.labels[x]['box'].get_style_context().remove_class("filament_sensor_empty")
            self.labels[x]['box'].get_style_context().remove_class("filament_sensor_detected")
