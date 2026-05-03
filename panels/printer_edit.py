import configparser
import io
import gi
import logging
import re
import threading
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib
from ks_includes.screen_panel import ScreenPanel

class Panel(ScreenPanel):
    def __init__(self, screen, title, printer_name=None):
        title = title or _("Edit Printer")
        super().__init__(screen, title)
        self.printer_name = printer_name
        self.fields = {}

        self.defaults = {
            "name": "",
            "moonraker_host": "127.0.0.1",
            "moonraker_port": "7125",
            "extrude_distances": "5, 10, 15, 25",
            "extrude_speeds": "1, 2, 5, 25",
            "z_babystep_values": "0.01, 0.05",
        }

        # Charger les valeurs existantes si edition
        current = self.defaults.copy()
        if printer_name:
            current["name"] = printer_name
            user_def, _saved = self._config.separate_saved_config(self._config.config_path)
            config = configparser.ConfigParser()
            config.read_string(user_def)
            section = f"printer {printer_name}"
            if section in config.sections():
                for key in ["moonraker_host", "moonraker_port", "extrude_distances", "extrude_speeds", "z_babystep_values"]:
                    if config.has_option(section, key):
                        current[key] = config.get(section, key)

        # Construction UI
        self.scroll = self._gtk.ScrolledWindow()
        grid = Gtk.Grid(column_spacing=10, row_spacing=10, margin=15)
        save_btn = self._gtk.Button("complete", _("Save") + " ", None, self.bts, Gtk.PositionType.RIGHT, 1)
        save_btn.get_style_context().add_class("button_active")
        save_btn.get_style_context().add_class("buttons_slim")
        save_btn.connect("clicked", self.confirm_save)
        save_btn.set_hexpand(False)  # pas tout le long
        save_btn.set_halign(Gtk.Align.END)  # à droite
        save_btn.set_size_request(-1, 60)  # plus haut

        test_btn = self._gtk.Button("refresh", _("Test") + " ", None, self.bts, Gtk.PositionType.RIGHT, 1)
        test_btn.get_style_context().add_class("button_active")
        test_btn.get_style_context().add_class("buttons_slim")
        test_btn.connect("clicked", self.test_connection)
        test_btn.set_hexpand(False)
        test_btn.set_halign(Gtk.Align.END)

        topbar = Gtk.Box(hexpand=True, vexpand=False)
        topbar.pack_end(save_btn, False, False, 5)
        topbar.pack_end(test_btn, False, False, 5)  # collé à droite

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main_box.pack_start(topbar, False, False, 0)
        main_box.pack_start(self.scroll, True, True, 0)
        self.content.add(main_box)

        labels = {
            "name": _("Name"),
            "moonraker_host": _("Host"),
            "moonraker_port": _("Port"),
            "extrude_distances": _("Extrude distances"),
            "extrude_speeds": _("Extrude speeds"),
            "z_babystep_values": _("Z babystep values"),
        }

        for i, (key, lbl) in enumerate(labels.items()):
            label = Gtk.Label(label=lbl, halign=Gtk.Align.START)
            entry = Gtk.Entry()
            entry.set_text(current[key])
            entry.set_hexpand(True)
            self.fields[key] = entry
            if key in ("moonraker_port", "extrude_distances", "extrude_speeds", "z_babystep_values"):
                entry.set_input_purpose(Gtk.InputPurpose.NUMBER)
                entry.get_style_context().add_class("active")
            else:
                entry.set_input_purpose(Gtk.InputPurpose.ALPHA)
            entry.connect("focus-in-event", self.show_keyboard)
            entry.connect("focus-out-event", self._screen.remove_keyboard)
            icon = self._gtk.PixbufFromIcon("hashtag")
            entry.set_icon_from_pixbuf(Gtk.EntryIconPosition.SECONDARY, icon)
            entry.connect("icon-press", self.on_icon_pressed)
            self.fields[key] = entry
            grid.attach(label, 0, i, 1, 1)
            grid.attach(entry, 1, i, 1, 1)


        self.scroll.add(grid)

    def show_keyboard(self, entry, event):
        self._screen.show_keyboard(entry, event)
        GLib.timeout_add(100, self.scroll_to_entry, entry)

    def scroll_to_entry(self, entry):
        self.scroll.get_vadjustment().set_value(
            entry.get_allocation().y - 50
        )

    def on_icon_pressed(self, entry, icon_pos, event):
        entry.grab_focus()
        self._screen.remove_keyboard()
        if entry.get_input_purpose() == Gtk.InputPurpose.ALPHA:
            if entry.get_input_hints() in (Gtk.InputHints.NONE, Gtk.InputHints.EMOJI):
                entry.set_input_purpose(Gtk.InputPurpose.NUMBER)
            else:
                entry.set_input_purpose(Gtk.InputPurpose.DIGITS)
            entry.get_style_context().add_class("active")
        else:
            entry.set_input_purpose(Gtk.InputPurpose.ALPHA)
            entry.get_style_context().remove_class("active")
        self.show_keyboard(entry, event)

    def confirm_save(self, widget):

        new_name = self.fields["name"].get_text().strip()
        host = self.fields["moonraker_host"].get_text().strip()
        port = self.fields["moonraker_port"].get_text().strip()
        extrude_distances = self.fields["extrude_distances"].get_text().strip()
        extrude_speeds = self.fields["extrude_speeds"].get_text().strip()
        z_babystep_values = self.fields["z_babystep_values"].get_text().strip()

        if not self.validate_csv_numbers(extrude_distances, 4):
            self._screen.show_popup_message(_("Extrude distances: 4 numbers required"))
            return
        if not self.validate_csv_numbers(extrude_speeds, 4):
            self._screen.show_popup_message(_("Extrude speeds: 4 numbers required"))
            return
        if not self.validate_csv_numbers(z_babystep_values, 2):
            self._screen.show_popup_message(_("Z babystep: 2 numbers required"))
            return
        if not port.isdigit():
            self._screen.show_popup_message(_("Port: numbers only"))
            return
        if not new_name or not host or not port:
            self._screen.show_popup_message(_("Name, host and port are required"))
            return

        label = Gtk.Label(wrap=True, hexpand=True, vexpand=True)
        label.set_label(_("Save printer configuration ?"))
        buttons = [
            {"name": _("Continue"), "response": Gtk.ResponseType.OK, "style": "dialog-info"},
            {"name": _("Cancel"), "response": Gtk.ResponseType.CANCEL, "style": "dialog-error"}
        ]
        self._gtk.Dialog(_("Confirm"), buttons, label, self.save_printer)

    def save_printer(self, dialog, response_id):
        self._gtk.remove_dialog(dialog)
        if response_id == Gtk.ResponseType.CANCEL:
            return
        new_name = self.fields["name"].get_text().strip()
        host = self.fields["moonraker_host"].get_text().strip()
        port = self.fields["moonraker_port"].get_text().strip()
        extrude_distances = self.normalize_csv(self.fields["extrude_distances"].get_text().strip())
        extrude_speeds = self.normalize_csv(self.fields["extrude_speeds"].get_text().strip())
        z_babystep_values = self.normalize_csv(self.fields["z_babystep_values"].get_text().strip())

        user_def, saved_def = self._config.separate_saved_config(self._config.config_path)
        config = configparser.ConfigParser()
        config.read_string(user_def)

        # Récupérer la position avant suppression
        import re
        with open(self._config.config_path) as f:
            content = f.read()
        ordered = re.findall(r'^\[printer (.+)\]', content, re.MULTILINE)
        position = ordered.index(self.printer_name) if self.printer_name and self.printer_name in ordered else len(ordered)

        # Supprimer l'ancienne section
        if self.printer_name and f"printer {self.printer_name}" in config.sections():
            config.remove_section(f"printer {self.printer_name}")

        # Créer la nouvelle section
        section = f"printer {new_name}"
        config.add_section(section)
        config.set(section, "moonraker_host", host)
        config.set(section, "moonraker_port", port)
        config.set(section, "extrude_distances", extrude_distances)
        config.set(section, "extrude_speeds", extrude_speeds)
        config.set(section, "z_babystep_values", z_babystep_values)

        # Reconstruire dans le bon ordre
        new_config = configparser.ConfigParser()
        printer_sections = [s for s in config.sections() if s.startswith("printer ")]
        other_sections = [s for s in config.sections() if not s.startswith("printer ")]

        # Insérer à la bonne position
        printer_sections.remove(section)
        printer_sections.insert(position, section)

        for s in other_sections:
            new_config.add_section(s)
            for k, v in config[s].items():
                new_config.set(s, k, v)
        for s in printer_sections:
            new_config.add_section(s)
            for k, v in config[s].items():
                new_config.set(s, k, v)

        output = io.StringIO()
        new_config.write(output)
        new_user_def = output.getvalue()

        with open(self._config.config_path, 'w') as f:
            f.write(new_user_def)
            if saved_def:
                f.write(f"{self._config.do_not_edit_line}\n")
                for line in saved_def.split("\n"):
                    if line.strip():
                        f.write(f"{self._config.do_not_edit_prefix} {line}\n")
                    else:
                        f.write(f"{self._config.do_not_edit_prefix}\n")

        self._screen.restart_ks()

    def validate_csv_numbers(self, value, count):
        parts = [p.strip() for p in value.split(",")]
        if len(parts) != count:
            return False
        for part in parts:
            if not part:
                return False
            try:
                float(part)
            except ValueError:
                return False
        return True

    def normalize_csv(self, value):
        parts = [p.strip() for p in value.split(",")]
        return ", ".join(parts)

    def test_connection(self, widget):
        host = self.fields["moonraker_host"].get_text().strip()
        port = self.fields["moonraker_port"].get_text().strip()
        threading.Thread(target=self._do_test, args=(host, port), daemon=True).start()

    def _do_test(self, host, port):
        try:
            import urllib.request
            urllib.request.urlopen(f"http://{host}:{port}/printer/info", timeout=3)
            GLib.idle_add(self._screen.show_popup_message, _("Connection OK"), 1)
        except:
            GLib.idle_add(self._screen.show_popup_message, _("Connection failed"), 3)
