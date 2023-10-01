import gi
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from ks_includes.screen_panel import ScreenPanel

class Panel(ScreenPanel):
    widgets = {}
    distances = ["0.01", "0.05", "0.10", "0.50", "1.00"]
    distance = distances[-3]

    def __init__(self, screen, title):
        super().__init__(screen, title)
        macros = self._printer.get_gcode_macros()
        self.macro_move_z = any("_MOVE_TO_Z0" in macro.upper() for macro in macros)

        grid = self._gtk.HomogeneousGrid()
        grid.set_row_homogeneous(False)
        self.buttons = {
            'home': self._gtk.Button('home', _("Homing"), 'color3'),
            'start': self._gtk.Button('arrow-down', _("Move Z0"), 'color4'),
            'z+': self._gtk.Button('z-farther', _("Raise Nozzle"), 'color1'),
            'z-': self._gtk.Button('z-closer', _("Lower Nozzle"), 'color3'),
        }

        self.buttons['home'].connect("clicked", self.home)
        if not self.macro_move_z:
            script = {"script": "G28\nG0 Z0 F1000\n"}
        else:
            script = {"script": "_MOVE_TO_Z0"}
        self.buttons['start'].connect("clicked", self._screen._confirm_send_action,
                                          _("Please remove leveling switch before move Z0."),
                                          "printer.gcode.script", script)
        self.buttons['z+'].connect("clicked", self.change_babystepping, "+")
        self.buttons['z-'].connect("clicked", self.change_babystepping, "-")
        self.labels['zoffset'] = Gtk.Label(f'Z Offset : {float(self._printer.data["gcode_move"]["homing_origin"][2]):.3f}mm')

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

        grid.attach(self.buttons['home'], 0, 0, 1, 1)
        grid.attach(self.buttons['z+'], 1, 0, 2, 1)
        grid.attach(self.buttons['z-'],  1, 1, 2, 1)
        grid.attach(self.buttons['start'], 0, 1, 1, 1)
        grid.attach(self.labels['zoffset'], 0, 2, 1, 1)
        grid.attach(distgrid, 1, 2, 2, 1)
        # nb bloc de decalage a partir de la gauche, nb bloc de decalage a partir du haut, longueur du nombre de bloc, ?? visible
        self.content.add(grid)

    def process_update(self, action, data):
        if action != "notify_status_update":
            return
        if "gcode_move" in data:
            if "homing_origin" in data["gcode_move"]:
                self.labels['zoffset'].set_label(f'Z Offset : {data["gcode_move"]["homing_origin"][2]:.3f}mm')

    def change_babystepping(self, widget, dir):
        if dir == "+":
            gcode = "SET_GCODE_OFFSET Z_ADJUST=%s MOVE=1" % self.distance
        else:
            gcode = "SET_GCODE_OFFSET Z_ADJUST=-%s MOVE=1" % self.distance

        self._screen._ws.klippy.gcode_script(gcode)

    def change_distance(self, widget, distance):
        #logging.info(f"### Distance {distance}")
        self.widgets[f"{self.distance}"].get_style_context().remove_class("distbutton_active")
        self.widgets[f"{distance}"].get_style_context().add_class("distbutton_active")
        self.distance = distance

    def home(self, widget):
        self._screen._ws.klippy.gcode_script(f"G28")
