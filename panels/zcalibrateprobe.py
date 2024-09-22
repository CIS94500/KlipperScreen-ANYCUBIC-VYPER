import logging
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from ks_includes.screen_panel import ScreenPanel

class Panel(ScreenPanel):
    widgets = {}
    distances = ['0.01', '0.05', '0.10', '0.50', '1.00', '5.00']
    distance = distances[-2]
    mem_zoffset = 0

    def __init__(self, screen, title):
        title = title or _("Z Calibrate")
        super().__init__(screen, title)
        macros = self._printer.get_gcode_macros()
        self.macro_calibrate = any("_START_CALIBRATE_PROBE" in macro.upper() for macro in macros)

        self.mesh_min = []
        self.mesh_max = []
        self.zero_ref = []
        self.z_hop_speed = 15.0
        self.z_hop = 5.0
        self.z_offset = None
        self.probe = self._printer.get_probe()
        if self.probe:
            self.x_offset = float(self.probe['x_offset']) if "x_offset" in self.probe else 0.0
            self.y_offset = float(self.probe['y_offset']) if "y_offset" in self.probe else 0.0
            self.z_offset = float(self.probe['z_offset'])
            if "sample_retract_dist" in self.probe:
                self.z_hop = float(self.probe['sample_retract_dist'])
            if "speed" in self.probe:
                self.z_hop_speed = float(self.probe['speed'])
        else:
            self.x_offset = 0.0
            self.y_offset = 0.0
            self.z_offset = 0.0
        logging.info(f"Offset X:{self.x_offset} Y:{self.y_offset} Z:{self.z_offset}")

        grid = Gtk.Grid(row_homogeneous=False, column_homogeneous=True)
        self.buttons = {
            'start': self._gtk.Button('arrow-down', _("Calibrate"), 'color3'),
            'z+': self._gtk.Button('z-farther', _("Raise Nozzle"), 'color4'),
            'z-': self._gtk.Button('z-closer', _("Lower Nozzle"), 'color1'),
            'accept': self._gtk.Button('complete', _("Accept"), 'color3'),
            'cancel': self._gtk.Button('cancel', _("Abort"), 'color2'),
        }
        self.buttons['start'].connect("clicked", self.start_calibration)
        self.buttons['z+'].connect("clicked", self.move, "+")
        self.buttons['z-'].connect("clicked", self.move, "-")
        self.buttons['accept'].connect("clicked", self.accept_calibrate)
        self.buttons['cancel'].connect("clicked", self.abort)
        self.labels['zoffset'] = Gtk.Label("Z: ?")
        # self.labels['distance'] = Gtk.Label(f'Z Offset : {float(self._printer.data["gcode_move"]["homing_origin"][2]):.3f}mm')
        self.labels['distance'] = Gtk.Label("Distance (mm) :")

        distgrid = Gtk.Grid()
        for j, i in enumerate(self.distances):
            self.widgets[i] = self._gtk.Button(label=i)
            self.widgets[i].set_direction(Gtk.TextDirection.LTR)
            self.widgets[i].connect("clicked", self.change_distance, i)
            ctx = self.widgets[i].get_style_context()
            if (self._screen.lang_ltr and j == 0) or (not self._screen.lang_ltr and j == len(self.distances) - 1):
                ctx.add_class("distbutton_top")
            elif (not self._screen.lang_ltr and j == 0) or (self._screen.lang_ltr and j == len(self.distances) - 1):
                ctx.add_class("distbutton_bottom")
            else:
                ctx.add_class("distbutton")
            if i == self.distance:
                ctx.add_class("distbutton_active")
            distgrid.attach(self.widgets[i], j, 0, 1, 1)

        grid.attach(self.buttons['start'], 0, 0, 1, 1)
        grid.attach(self.labels['zoffset'], 0, 1, 1, 1)
        grid.attach(self.buttons['z+'], 1, 0, 1, 1)
        grid.attach(self.buttons['z-'],  1, 1, 1, 1)
        grid.attach(self.buttons['accept'], 2, 0, 1, 1)
        grid.attach(self.buttons['cancel'], 2, 1, 1, 1)

        grid.attach(self.labels['distance'], 0, 2, 1, 1)
        grid.attach(distgrid, 1, 2, 2, 1)
        # nb bloc de decalage a partir de la gauche, nb bloc de decalage a partir du haut, longueur du nombre de bloc, ?? visible
        self.content.add(grid)

        self.set_functions()

    @staticmethod
    def _csv_to_array(string):
        return [float(i.strip()) for i in string.split(',')]

    def set_functions(self):
        functions = []

        if "BED_MESH_CALIBRATE" in self._printer.available_commands:
            self.mesh_min = self._csv_to_array(self._printer.get_config_section("bed_mesh")['mesh_min'])
            self.mesh_max = self._csv_to_array(self._printer.get_config_section("bed_mesh")['mesh_max'])
            if 'zero_reference_position' in self._printer.get_config_section("bed_mesh"):
                self.zero_ref = self._csv_to_array(
                    self._printer.get_config_section("bed_mesh")['zero_reference_position'])
        logging.info(f"Available functions for calibration: {functions}")

    def process_busy(self, busy):
        if busy:
            for button in self.buttons:
                self.buttons[button].set_sensitive(False)
        elif self._printer.get_stat("manual_probe", "is_active"):
            self.buttons_calibrating()
        else:
            self.buttons_not_calibrating()

    def process_update(self, action, data):
        if action == "notify_busy":
            self.process_busy(data)
            return
        if action == "notify_status_update":
            if self._printer.get_stat("toolhead", "homed_axes") != "xyz":
                self.labels['zoffset'].set_label(f'Z: {float(self._printer.get_config_section("stepper_z")["position_max"]):.3f}')
                # self.labels['distance'].set_label(f'Z Offset : {float(self._printer.data["gcode_move"]["homing_origin"][2]):.3f}mm')
            elif "gcode_move" in data and "gcode_position" in data['gcode_move']:
                self.update_position(data['gcode_move']['gcode_position'])
        elif action == "notify_gcode_response":
            if "out of range" in data.lower():
                self._screen.show_popup_message(data)
                logging.info(data)
            elif "fail" in data.lower() and "use testz" in data.lower():
                self._screen.show_popup_message(_("Failed, adjust position first"))
                logging.info(data)
        return

    def update_position(self, position):
        if self.z_offset is not None:
            self.labels['zoffset'].set_label(f"Z: {position[2] - self.z_offset:.3f}")
        else:
            self.labels['zoffset'].set_label(f"Z: {position[2]:.3f}")

    def change_distance(self, widget, distance):
        self.widgets[f"{self.distance}"].get_style_context().remove_class("distbutton_active")
        self.widgets[f"{distance}"].get_style_context().add_class("distbutton_active")
        self.distance = distance

    def move(self, widget, direction):
        self._screen._ws.klippy.gcode_script(f"TESTZ Z={direction}{self.distance}")

    def accept_calibrate(self, widget):
        self.mem_zoffset = 0
        self._screen._ws.klippy.gcode_script(f"ACCEPT\nG90\nG1 Z10 F3600\nSAVE_CONFIG")

    def abort(self, widget):
        logging.info("Aborting calibration")
        self._screen._ws.klippy.gcode_script(f"G0 Z10 F3600\nSET_GCODE_OFFSET Z={self.mem_zoffset}\nABORT")
        self.buttons_not_calibrating()
        self._screen._menu_go_back()

    def home(self, widget):
        self._screen._ws.klippy.gcode_script("G28")

    def start_calibration(self, widget):
        self.mem_zoffset = self._printer.data["gcode_move"]["homing_origin"][2]
        self._screen._ws.klippy.gcode_script(f"SET_GCODE_OFFSET Z=0")
        if self._printer.config_section_exists("bed_mesh"):
            self._screen._ws.klippy.gcode_script("BED_MESH_CLEAR")

        if not self.macro_calibrate:
            self._screen.show_popup_message(_("Please wait while the elements heat up..."), 1)
            self._screen._ws.klippy.gcode_script(f"M104 S210\nM140 S60\nM109 S210\nM190 S60")
            if self._printer.get_stat("toolhead", "homed_axes") != "xyz":
                self._screen._ws.klippy.gcode_script("G28")
            self._move_to_position(*self._get_probe_location())
            self._screen._ws.klippy.gcode_script(f"PROBE_CALIBRATE")
        else:
            self._screen._ws.klippy.gcode_script(f"_START_CALIBRATE_PROBE")

    def _move_to_position(self, x, y):
        if not x or not y:
            self._screen.show_popup_message(_("Error: Couldn't get a position to probe"))
            return
        logging.info(f"Lifting Z: {self.z_hop}mm {self.z_hop_speed}mm/s")
        self._screen._ws.klippy.gcode_script(f"G91\nG0 Z{self.z_hop} F{self.z_hop_speed * 60}")
        logging.info(f"Moving to X:{x} Y:{y}")
        self._screen._ws.klippy.gcode_script(f'G90\nG0 X{x} Y{y} F3000')

    def _get_probe_location(self):
        if self.ks_printer_cfg is not None:
            x = self.ks_printer_cfg.getfloat("calibrate_x_position", None)
            y = self.ks_printer_cfg.getfloat("calibrate_y_position", None)
            if x and y:
                logging.debug(f"Using KS configured position: {x}, {y}")
                return x, y

        if self.zero_ref:
            logging.debug(f"Using zero reference position: {self.zero_ref}")
            return self.zero_ref[0] - self.x_offset, self.zero_ref[1] - self.y_offset

        if ("safe_z_home" in self._printer.get_config_section_list() and
                "Z_ENDSTOP_CALIBRATE" not in self._printer.available_commands):
            return self._get_safe_z()

        x, y = self._calculate_position()
        return x, y

    def _get_safe_z(self):
        safe_z = self._printer.get_config_section("safe_z_home")
        safe_z_xy = self._csv_to_array(safe_z['home_xy_position'])
        logging.debug(f"Using safe_z {safe_z_xy[0]}, {safe_z_xy[1]}")
        if 'z_hop' in safe_z:
            self.z_hop = float(safe_z['z_hop'])
        if 'z_hop_speed' in safe_z:
            self.z_hop_speed = float(safe_z['z_hop_speed'])
        return safe_z_xy[0], safe_z_xy[1]

    def _calculate_position(self):
        if self.mesh_max and self.mesh_min:
            mesh_mid_x = (self.mesh_min[0] + self.mesh_max[0]) / 2
            mesh_mid_y = (self.mesh_min[1] + self.mesh_max[1]) / 2
            logging.debug(f"Probe in the mesh center X:{mesh_mid_x} Y:{mesh_mid_y}")
            return mesh_mid_x - self.x_offset, mesh_mid_y - self.y_offset
        try:
            mid_x = float(self._printer.get_config_section("stepper_x")['position_max']) / 2
            mid_y = float(self._printer.get_config_section("stepper_y")['position_max']) / 2
        except KeyError:
            logging.error("Couldn't get max position from stepper_x and stepper_y")
            return None, None
        logging.debug(f"Probe in the center X:{mid_x} Y:{mid_y}")
        return mid_x - self.x_offset, mid_y - self.y_offset

    def buttons_calibrating(self):
        self.buttons['start'].get_style_context().remove_class('color3')
        self.buttons['start'].set_sensitive(False)

        self.buttons['z+'].set_sensitive(True)
        self.buttons['z+'].get_style_context().add_class('color4')
        self.buttons['z-'].set_sensitive(True)
        self.buttons['z-'].get_style_context().add_class('color1')
        self.buttons['accept'].set_sensitive(True)
        self.buttons['accept'].get_style_context().add_class('color3')
        self.buttons['cancel'].set_sensitive(True)
        self.buttons['cancel'].get_style_context().add_class('color2')

    def buttons_not_calibrating(self):
        self.buttons['start'].get_style_context().add_class('color3')
        if self.probe:
            self.buttons['start'].set_sensitive(True)
        else:
            self.buttons['start'].set_sensitive(False)

        self.buttons['z+'].set_sensitive(False)
        self.buttons['z+'].get_style_context().remove_class('color4')
        self.buttons['z-'].set_sensitive(False)
        self.buttons['z-'].get_style_context().remove_class('color1')
        self.buttons['accept'].set_sensitive(False)
        self.buttons['accept'].get_style_context().remove_class('color3')
        self.buttons['cancel'].set_sensitive(False)
        self.buttons['cancel'].get_style_context().remove_class('color2')
