import configparser
import io
import gi
import re

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        title = title or _("Settings")
        super().__init__(screen, title)
        self.printers = self.settings = self.langs = {}
        self.menu = ['settings_menu']
        options = self._config.get_configurable_options().copy()
        options.append({"printers": {
            "name": _("Printer Connections"),
            "type": "menu",
            "menu": "printers"
        }})
        options.append({"lang": {
            "name": _("Language"),
            "type": "menu",
            "menu": "lang"
        }})

        self.labels['settings_menu'] = self._gtk.ScrolledWindow()
        self.labels['settings'] = Gtk.Grid()
        self.labels['settings_menu'].add(self.labels['settings'])
        for option in options:
            name = list(option)[0]
            self.add_option('settings', self.settings, name, option[name])

        self.labels['lang_menu'] = self._gtk.ScrolledWindow()
        self.labels['lang'] = Gtk.Grid()
        self.labels['lang_menu'].add(self.labels['lang'])
        for lang in self._config.lang_list:
            self.langs[lang] = {
                "name": lang,
                "type": "lang",
            }
            self.add_option("lang", self.langs, lang, self.langs[lang])

        self.labels['printers_menu'] = self._gtk.ScrolledWindow()
        self.labels['printers'] = Gtk.Grid()
        self.labels['printers_menu'].add(self.labels['printers'])
        self._build_printers_list()

        add_btn = self._gtk.Button("increase", _("Add") + " ", None, self.bts, Gtk.PositionType.RIGHT, 1)
        add_btn.get_style_context().add_class("button_active")
        add_btn.get_style_context().add_class("buttons_slim")
        add_btn.connect("clicked", self.add_printer)
        add_btn.set_hexpand(False)  # pas tout le long
        add_btn.set_halign(Gtk.Align.END)  # à droite
        add_btn.set_size_request(-1, 60)  # plus haut

        topbar = Gtk.Box(hexpand=True, vexpand=False)
        topbar.pack_end(add_btn, False, False, 5)

        printers_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        printers_box.pack_start(topbar, False, False, 0)
        printers_box.pack_start(self.labels['printers_menu'], True, True, 0)
        self.labels['printers_menu'] = printers_box  # remplace la référence
        self.content.add(self.labels['settings_menu'])  # seulement celui-là

    def add_printer(self, widget):
        self._screen.show_panel("printer_edit", "Add Printer")

    def activate(self):
        while len(self.menu) > 1:
            self.unload_menu()

    def back(self):
        if len(self.menu) > 1:
            self.unload_menu()
            return True
        return False

    def confirm_delete(self, widget, printer_name):
        label = Gtk.Label(wrap=True, hexpand=True, vexpand=True)
        label.set_label(_("Delete printer configuration ?"))
        buttons = [
            {"name": _("Continue"), "response": Gtk.ResponseType.OK, "style": "dialog-info"},
            {"name": _("Cancel"), "response": Gtk.ResponseType.CANCEL, "style": "dialog-error"}
        ]
        self._gtk.Dialog(_("Confirm"), buttons, label, self.delete_printer, printer_name)

    def delete_printer(self, dialog, response_id, printer_name):
        self._gtk.remove_dialog(dialog)
        if response_id == Gtk.ResponseType.CANCEL:
            return
        user_def, saved_def = self._config.separate_saved_config(self._config.config_path)
        config = configparser.ConfigParser()
        config.read_string(user_def)
        if f"printer {printer_name}" in config.sections():
            config.remove_section(f"printer {printer_name}")
            output = io.StringIO()
            config.write(output)
            new_user_def = output.getvalue()

            # Nettoyer le saved_def des sections orphelines
            if saved_def:
                saved_config = configparser.ConfigParser()
                saved_config.read_string(saved_def)
                for section in list(saved_config.sections()):
                    if printer_name in section:
                        saved_config.remove_section(section)
                saved_output = io.StringIO()
                saved_config.write(saved_output)
                saved_def = saved_output.getvalue()

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

    def edit_printer(self, widget, printer_name):
        self._screen.show_panel("printer_edit", _("Edit Printer"), printer_name=printer_name)

    def move_printer_up(self, widget, printer_name):
        self._move_printer(printer_name, -1)

    def move_printer_down(self, widget, printer_name):
        self._move_printer(printer_name, 1)

    def _move_printer(self, printer_name, direction):
        user_def, saved_def = self._config.separate_saved_config(self._config.config_path)
        config = configparser.ConfigParser()
        config.read_string(user_def)

        # Récupérer uniquement les sections printer dans l'ordre
        printer_sections = [s for s in config.sections() if s.startswith("printer ")]
        other_sections = [s for s in config.sections() if not s.startswith("printer ")]

        section = f"printer {printer_name}"
        if section not in printer_sections:
            return

        idx = printer_sections.index(section)
        new_idx = idx + direction

        if new_idx < 0 or new_idx >= len(printer_sections):
            return

        # Swap
        printer_sections[idx], printer_sections[new_idx] = printer_sections[new_idx], printer_sections[idx]

        # Reconstruire le config dans le bon ordre
        new_config = configparser.ConfigParser()
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

        # Recharger uniquement les printers
        self._config.config.read(self._config.config_path)

        # Reconstruire les printers dans config
        with open(self._config.config_path) as f:
            content = f.read()
        ordered = re.findall(r'^\[printer (.+)\]', content, re.MULTILINE)
        self._config.printers = [
            {p: {
                "moonraker_host": self._config.config.get(f"printer {p}", "moonraker_host", fallback="127.0.0.1"),
                "moonraker_port": self._config.config.get(f"printer {p}", "moonraker_port", fallback="7125"),
                "moonraker_api_key": self._config.config.get(f"printer {p}", "moonraker_api_key", fallback=""),
            }} for p in ordered if f"printer {p}" in self._config.config.sections()
        ]

        # Vider et reconstruire la liste
        for child in self.labels['printers'].get_children():
            self.labels['printers'].remove(child)
        self._build_printers_list()

    def _build_printers_list(self):
        self.printers = {}
        for printer in self._config.get_printers():
            pname = list(printer)[0]
            self.printers[pname] = {
                "name": pname,
                "section": f"printer {pname}",
                "type": "printer",
                "moonraker_host": printer[pname]['moonraker_host'],
                "moonraker_port": printer[pname]['moonraker_port'],
                "edit_callback": self.edit_printer,
                "delete_callback": self.confirm_delete,
                "move_up_callback": self.move_printer_up,
                "move_down_callback": self.move_printer_down,
            }
            self.add_option("printers", self.printers, pname, self.printers[pname])

        self.labels['printers'].show_all()
