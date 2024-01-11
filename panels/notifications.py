import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from ks_includes.screen_panel import ScreenPanel


COLORS = {
    "time": "DarkGrey",
    "info": "Silver",
    "warning": "DarkOrange",
    "error": "FireBrick",
}


def remove_newlines(msg: str) -> str:
    return msg.replace('\n', ' ')


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.empty = _("Notification log empty")
        self.tb = Gtk.TextBuffer(text=self.empty)

        clean_button = self._gtk.Button("refresh", _('Clear') + " ", None, self.bts, Gtk.PositionType.RIGHT, 1)
        clean_button.get_style_context().add_class("buttons_slim")
        clean_button.connect("clicked", self.clean)
        clean_button.set_hexpand(True)

        topbar = Gtk.Box()
        topbar.set_hexpand(False)
        topbar.set_vexpand(False)
        topbar.add(clean_button)

        tv = Gtk.TextView(editable=False, cursor_visible=False, wrap_mode=Gtk.WrapMode.WORD)
        tv.set_buffer(self.tb)
        tv.connect("button-press-event", self.tvClicked)
        tv.connect("size-allocate", self._autoscroll)

        scroll = Gtk.ScrolledWindow()
        scroll.set_hexpand(True)
        scroll.set_vexpand(True)
        scroll.add(tv)

        grid = self._gtk.HomogeneousGrid()
        grid.set_row_homogeneous(False)
        grid.attach(topbar, 3, 0, 1, 1)
        grid.attach(scroll, 0, 1, 4, 1)
        self.content.add(grid)

    def activate(self):
        self.clear()
        for log in self._screen.notification_log:
            self.add_notification(log)

    def add_notification(self, log):
        if log["level"] == 0:
            if "error" in log["message"].lower() or "cannot" in log["message"].lower():
                color = COLORS["error"]
            else:
                color = COLORS["info"]
        elif log["level"] == 1:
            color = COLORS["info"]
        elif log["level"] == 2:
            color = COLORS["warning"]
        else:
            color = COLORS["error"]
        self.tb.insert_markup(
            self.tb.get_end_iter(),
            f'\n<span color="{COLORS["time"]}">{log["time"]}</span> '
            f'<span color="{color}"><b>{remove_newlines(log["message"])}</b></span>',
            -1
        )

    def clear(self):
        self.tb.set_text("")

    def clean(self, widget):
        self._screen.notification_log.clear()
        self._screen.log_notification("Clear notifications", 1)
        self.activate()

    def process_update(self, action, data):
        if action != "notify_log":
            return
        self.add_notification(data)

    def tvClicked(self, widget, event):
        return True
