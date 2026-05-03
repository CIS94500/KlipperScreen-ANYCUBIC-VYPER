import logging
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Pango
from ks_includes.screen_panel import ScreenPanel

class Panel(ScreenPanel):
    def __init__(self, screen, title, spool=None):
        title = title or "Edit Spool"
        super().__init__(screen, title)
        self.spool = spool
        self.fields = {}

        # Construction UI
        self.scroll = self._gtk.ScrolledWindow()
        grid = Gtk.Grid(column_spacing=10, row_spacing=10, margin=15)

        save_btn = self._gtk.Button("complete", "Save", None, self.bts, Gtk.PositionType.RIGHT, 1)
        save_btn.get_style_context().add_class("button_active")
        save_btn.get_style_context().add_class("buttons_slim")
        save_btn.connect("clicked", self.confirm_save)
        save_btn.set_hexpand(False)
        save_btn.set_halign(Gtk.Align.END)

        topbar = Gtk.Box(hexpand=True, vexpand=False)
        topbar.pack_end(save_btn, False, False, 5)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main_box.pack_start(topbar, False, False, 0)
        main_box.pack_start(self.scroll, True, True, 0)
        self.content.add(main_box)

        # Infos lecture seule
        infos = {
            _("Name"): spool.name if spool else "",
            _("Material"): spool.filament.material if spool else "",
            _("Last used"): str(spool.last_used) if spool and spool.last_used else "",
            _("Remaining length"): f"{round(spool.remaining_length / 1000, 2)} m" if spool and hasattr(spool, 'remaining_length') else "",
        }

        row = 0
        for lbl, val in infos.items():
            if not val:
                continue
            label = Gtk.Label(label=lbl, halign=Gtk.Align.START)
            value = Gtk.Label(label=val, halign=Gtk.Align.START)
            value.get_style_context().add_class("title_20")
            grid.attach(label, 0, row, 1, 1)
            grid.attach(value, 1, row, 1, 1)
            row += 1

        # Champ poids éditable
        weight_label = Gtk.Label(label=_("Remaining weight (g)"), halign=Gtk.Align.START)
        weight_entry = Gtk.Entry()
        weight_entry.set_text(str(round(spool.remaining_weight, 2)) if spool and hasattr(spool, 'remaining_weight') else "0")
        weight_entry.set_hexpand(True)
        weight_entry.set_input_purpose(Gtk.InputPurpose.NUMBER)
        weight_entry.get_style_context().add_class("active")
        weight_entry.connect("focus-in-event", self.show_keyboard)
        weight_entry.connect("focus-out-event", self._screen.remove_keyboard)
        self.fields["remaining_weight"] = weight_entry
        grid.attach(weight_label, 0, row, 1, 1)
        grid.attach(weight_entry, 1, row, 1, 1)

        self.scroll.add(grid)
        
        GLib.timeout_add(300, self._focus_weight)

    def _focus_weight(self):
        self.fields["remaining_weight"].grab_focus()
        return False

    def show_keyboard(self, entry, event):
        self._screen.show_keyboard(entry, event)
        GLib.timeout_add(100, self.scroll_to_entry, entry)

    def scroll_to_entry(self, entry):
        self.scroll.get_vadjustment().set_value(entry.get_allocation().y - 50)

    def confirm_save(self, widget):
        new_weight = self.fields["remaining_weight"].get_text().strip()
        if not new_weight:
            self._screen.show_popup_message(_("Weight is required"))
            return
        try:
            float(new_weight)
        except ValueError:
            self._screen.show_popup_message(_("Weight: numbers only"))
            return
        label = Gtk.Label(wrap=True, hexpand=True, vexpand=True)
        label.set_label(_("Save spool weight?"))
        buttons = [
            {"name": _("Continue"), "response": Gtk.ResponseType.OK, "style": "dialog-info"},
            {"name": _("Cancel"), "response": Gtk.ResponseType.CANCEL, "style": "dialog-error"}
        ]
        self._gtk.Dialog(_("Confirm"), buttons, label, self.save_spool)

    def save_spool(self, dialog, response_id):
        self._gtk.remove_dialog(dialog)
        if response_id == Gtk.ResponseType.CANCEL:
            return
        new_weight = float(self.fields["remaining_weight"].get_text().strip())
        result = self._screen.spoolman_api.update_spool_weight(self.spool.id, new_weight)
        if result:
            self._screen.show_popup_message(_("Weight updated"), 1)
        else:
            self._screen.show_popup_message(_("Error updating weight"), 3)
        self._screen._menu_go_back()
        # Refresh le panneau spoolman
        if "spoolman" in self._screen.panels:
            self._screen.panels["spoolman"].refresh()
        GLib.timeout_add(500, self._refresh_topbar)

    def _refresh_topbar(self):
        self._screen.update_spool_data()
        GLib.timeout_add(500, self._screen.base_panel.update_spoolman_weight_label)
        return False
