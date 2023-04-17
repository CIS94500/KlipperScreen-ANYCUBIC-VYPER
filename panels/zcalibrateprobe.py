import gi
import logging
import re

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel

def create_panel(*args):
    return ZCalibrateProbePanel(*args)

class ZCalibrateProbePanel(ScreenPanel):
    distances = ['0.01', '0.05', '0.1', '0.5', '1', '5']
    distance = distances[-2]

    def __init__(self, screen, title):
        super().__init__(screen, title)
        
        grid = self._gtk.HomogeneousGrid()
        grid.set_row_homogeneous(False)        
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
        
        self.labels['blank'] = Gtk.Label()        
        self.labels['distance'] = Gtk.Label("Distance (mm) :")    
        
        grid.attach(self.buttons['start'], 0, 0, 1, 1)
        grid.attach(self.labels['zoffset'], 0, 1, 1, 1)
        grid.attach(self.buttons['z+'], 1, 0, 1, 1)
        grid.attach(self.buttons['z-'],  1, 1, 1, 1)        
        grid.attach(self.buttons['accept'], 2, 0, 1, 1)
        grid.attach(self.buttons['cancel'], 2, 1, 1, 1)
        
        grid.attach(self.labels['blank'], 0, 3, 1, 1)
        grid.attach(self.labels['distance'], 0, 4, 1, 1)
        
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
                
    def process_busy(self, busy):
        for button in self.buttons:
            if button != "start":
                self.buttons[button].set_sensitive(not busy)
            else:
                self.buttons[button].set_sensitive(False)
                
    def process_update(self, action, data):
        if action == "notify_busy":
            self.process_busy(data)
            return
        if action == "notify_status_update":
            if self._printer.get_stat("toolhead", "homed_axes") != "xyz":
                self.labels['zoffset'].set_label("Z: ?")
            elif "gcode_move" in data and "gcode_position" in data['gcode_move']:
                self.update_position(data['gcode_move']['gcode_position'])
        elif action == "notify_gcode_response":
            data = data.lower()
            if "unknown" in data:
                self.buttons_not_calibrating()
                logging.info(data)
            elif "save_config" in data:
                self.buttons_not_calibrating()
            elif "out of range" in data:
                self._screen.show_popup_message(data)
                self.buttons_not_calibrating()
                logging.info(data)
            elif "fail" in data and "use testz" in data:
                self._screen.show_popup_message(_("Failed, adjust position first"))
                self.buttons_not_calibrating()
                logging.info(data)
            elif "use testz" in data or "use abort" in data or "z position" in data:
                self.buttons_calibrating()
        return
        
    def update_position(self, position):
        self.labels['zoffset'].set_label(f"Z: {position[2]:.3f}")
            
    def change_distance(self, widget, dist):
        if self.distance == dist:
            return
        logging.info("### TestZ " + str(dist))

        ctx = self.labels[str(self.distance)].get_style_context()
        ctx.remove_class("distbutton_active")

        self.distance = dist
        ctx = self.labels[self.distance].get_style_context()
        ctx.add_class("distbutton_active")
        for i in self.distances:
            if i == self.distance:
                continue
            self.labels[i].set_active(False)
            
    def move(self, widget, direction):
        self._screen._ws.klippy.gcode_script(KlippyGcodes.testz_move(f"{direction}{self.distance}"))
        
    def abort(self, widget):
        logging.info("Aborting calibration")
        self._screen._ws.klippy.gcode_script("G1 Z10 F3600\nM84")        
        self._screen._ws.klippy.gcode_script(KlippyGcodes.ABORT)
        self.buttons_not_calibrating()
        self._screen._menu_go_back()
       
    def home(self, widget):
        self._screen._ws.klippy.gcode_script(KlippyGcodes.HOME)
        
    def start_calibration(self, widget):
        self._screen._ws.klippy.gcode_script("_START_CALIBRATE_PROBE")
        
    def accept_calibrate(self, widget):
        self._screen._ws.klippy.gcode_script("ACCEPT\nG90\nG1 Z10 F3600\nSAVE_CONFIG")
        
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
        self.buttons['start'].set_sensitive(True)
        
        self.buttons['z+'].set_sensitive(False)
        self.buttons['z+'].get_style_context().remove_class('color4')
        self.buttons['z-'].set_sensitive(False)
        self.buttons['z-'].get_style_context().remove_class('color1')
        self.buttons['accept'].set_sensitive(False)
        self.buttons['accept'].get_style_context().remove_class('color3')
        self.buttons['cancel'].set_sensitive(False)
        self.buttons['cancel'].get_style_context().remove_class('color2')
        
    def activate(self):
        # This is only here because klipper doesn't provide a method to detect if it's calibrating
        self._screen._ws.klippy.gcode_script(KlippyGcodes.testz_move("+0.001"))
