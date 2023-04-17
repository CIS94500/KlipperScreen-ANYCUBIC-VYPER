import gi
import logging
import re

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel

def create_panel(*args):
    return ZCalibrateDeltaPanel(*args)

class ZCalibrateDeltaPanel(ScreenPanel):
    dist = 0
    distance = "0.1"
    distances = ["0.01", "0.05", "0.1", "0.5", "1"]

    def __init__(self, screen, title):
        super().__init__(screen, title)

        grid = self._gtk.HomogeneousGrid()
        grid.set_row_homogeneous(False)    
        self.buttons = {      
            'home': self._gtk.Button('arrow-down', _("Homing"), 'color3'),
            'start': self._gtk.Button('arrow-down', _("Move Z0"), 'color4'),
            'z+': self._gtk.Button('z-farther', _("Raise Nozzle"), 'color1'),
            'z-': self._gtk.Button('z-closer', _("Lower Nozzle"), 'color3'),
        }
        
        self.buttons['home'].connect("clicked", self.home)
        script = {"script": "_MOVE_TO_Z0"}
        self.buttons['start'].connect("clicked", self._screen._confirm_send_action,
                                          _("Please remove leveling switch before move Z0."),
                                          "printer.gcode.script", script)
        self.buttons['z+'].connect("clicked", self.change_babystepping, "+")
        self.buttons['z-'].connect("clicked", self.change_babystepping, "-")           
        self.labels['zoffset'] = Gtk.Label(f'Z Offset : {float(self._printer.data["gcode_move"]["homing_origin"][2]):.3f}mm')         
        self.labels['blank'] = Gtk.Label()
        
        grid.attach(self.buttons['home'], 0, 0, 1, 1)
        grid.attach(self.buttons['z+'], 1, 0, 2, 1)
        grid.attach(self.buttons['z-'],  1, 1, 2, 1)
        grid.attach(self.buttons['start'], 0, 1, 1, 1)
        grid.attach(self.labels['zoffset'], 0, 4, 1, 1)
        grid.attach(self.labels['blank'], 0, 3, 1, 1)
        
        distgrid = Gtk.Grid()
        j = 0
        for i in self.distances:
            self.labels[i] = self._gtk.ToggleButton(i)
            self.labels[i].connect("clicked", self.change_distance, i)
            ctx = self.labels[i].get_style_context()
            if j == 0:
                ctx.add_class("distbutton_top")
            elif j == len(self.distances)-1:
                ctx.add_class("distbutton_bottom")
            else:
                ctx.add_class("distbutton")
            if i == self.distance:
                ctx.add_class("distbutton_active")
            distgrid.attach(self.labels[i], j, 0, 1, 1)
            j += 1
        grid.attach(distgrid, 1, 4, 2, 1)

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

    def change_distance(self, widget, dist):
        if self.distance == dist:
            return
        logging.info("### BabyStepping " + str(dist))

        ctx = self.labels[str(self.distance)].get_style_context()
        ctx.remove_class("distbutton_active")

        self.distance = dist
        ctx = self.labels[self.distance].get_style_context()
        ctx.add_class("distbutton_active")
        for i in self.distances:
            if i == self.distance:
                continue
            self.labels[i].set_active(False)
            
    def home(self, widget):
        self._screen._ws.klippy.gcode_script(KlippyGcodes.HOME)
