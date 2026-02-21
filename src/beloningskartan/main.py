"""Belöningskartan - Visual reward and goal tracking."""
import sys, os, json, gettext, locale
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gio, GLib, Gdk
from beloningskartan import __version__
from beloningskartan.accessibility import apply_large_text

TEXTDOMAIN = "beloningskartan"
for p in [os.path.join(os.path.dirname(__file__), "locale"), "/usr/share/locale"]:
    if os.path.isdir(p):
        gettext.bindtextdomain(TEXTDOMAIN, p)
        locale.bindtextdomain(TEXTDOMAIN, p)
        break
gettext.textdomain(TEXTDOMAIN)
_ = gettext.gettext

CONFIG_DIR = os.path.join(GLib.get_user_config_dir(), "beloningskartan")
DATA_FILE = os.path.join(CONFIG_DIR, "goals.json")

def _default_goals():
    return [
        {"name": _("Brush teeth"), "emoji": "\U0001f9f7", "target": 5, "progress": 0},
        {"name": _("Get dressed"), "emoji": "\U0001f455", "target": 5, "progress": 0},
        {"name": _("Tidy room"), "emoji": "\U0001f9f9", "target": 3, "progress": 0},
        {"name": _("Read a book"), "emoji": "\U0001f4d6", "target": 5, "progress": 0},
    ]

def _load_goals():
    try:
        with open(DATA_FILE) as f: return json.load(f)
    except: return _default_goals()

def _save_goals(goals):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(DATA_FILE, "w") as f: json.dump(goals, f, ensure_ascii=False, indent=2)


class RewardApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="se.danielnylander.beloningskartan",
                         flags=Gio.ApplicationFlags.DEFAULT_FLAGS)

    def do_activate(self):
        apply_large_text()
        win = self.props.active_window or RewardWindow(application=self)
        win.present()

    def do_startup(self):
        Adw.Application.do_startup(self)
        for name, cb, accel in [
            ("quit", lambda *_: self.quit(), "<Control>q"),
            ("about", self._on_about, None),
            ("export", self._on_export, "<Control>e"),
        ]:
            a = Gio.SimpleAction.new(name, None)
            a.connect("activate", cb)
            self.add_action(a)
            if accel: self.set_accels_for_action(f"app.{name}", [accel])

    def _on_about(self, *_):
        d = Adw.AboutDialog(application_name=_("Reward Chart"), application_icon="beloningskartan",
            version=__version__, developer_name="Daniel Nylander", website="https://www.autismappar.se",
            license_type=Gtk.License.GPL_3_0, developers=["Daniel Nylander"],
            copyright="\u00a9 2026 Daniel Nylander")
        d.present(self.props.active_window)

    def _on_export(self, *_):
        w = self.props.active_window
        if w: w.do_export()


class RewardWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs, default_width=500, default_height=650, title=_("Reward Chart"))
        self.goals = _load_goals()
        self._build_ui()

    def _build_ui(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(box)
        header = Adw.HeaderBar()
        box.append(header)

        menu = Gio.Menu()
        menu.append(_("Export"), "app.export")
        menu.append(_("About Reward Chart"), "app.about")
        menu.append(_("Quit"), "app.quit")
        header.pack_end(Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu))

        theme_btn = Gtk.Button(icon_name="weather-clear-night-symbolic",
                               tooltip_text=_("Toggle dark/light theme"))
        theme_btn.connect("clicked", self._toggle_theme)
        header.pack_end(theme_btn)

        title = Gtk.Label(label=_("My Goals"))
        title.add_css_class("title-1")
        title.set_margin_top(16)
        box.append(title)

        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_margin_start(16)
        scroll.set_margin_end(16)
        scroll.set_margin_top(12)
        self.goal_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        scroll.set_child(self.goal_box)
        box.append(scroll)

        add_btn = Gtk.Button(label=_("Add Goal"))
        add_btn.add_css_class("suggested-action")
        add_btn.add_css_class("pill")
        add_btn.set_halign(Gtk.Align.CENTER)
        add_btn.set_margin_top(8)
        add_btn.connect("clicked", self._on_add_goal)
        box.append(add_btn)

        reset_btn = Gtk.Button(label=_("Reset All"))
        reset_btn.add_css_class("destructive-action")
        reset_btn.add_css_class("pill")
        reset_btn.set_halign(Gtk.Align.CENTER)
        reset_btn.set_margin_top(4)
        reset_btn.set_margin_bottom(8)
        reset_btn.connect("clicked", self._on_reset)
        box.append(reset_btn)

        self.status_label = Gtk.Label(label="", xalign=0)
        self.status_label.add_css_class("dim-label")
        self.status_label.set_margin_start(12)
        self.status_label.set_margin_bottom(4)
        box.append(self.status_label)
        GLib.timeout_add_seconds(1, self._update_clock)
        self._refresh_goals()

    def _refresh_goals(self):
        while (child := self.goal_box.get_first_child()):
            self.goal_box.remove(child)
        for i, goal in enumerate(self.goals):
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            card.add_css_class("card")

            hbox = Gtk.Box(spacing=8)
            hbox.set_margin_start(12)
            hbox.set_margin_top(8)
            emoji = Gtk.Label()
            emoji.set_markup(f'<span size="48000">{goal["emoji"]}</span>')
            hbox.append(emoji)
            name_l = Gtk.Label(label=goal["name"])
            name_l.add_css_class("title-3")
            name_l.set_hexpand(True)
            name_l.set_xalign(0)
            hbox.append(name_l)
            del_btn = Gtk.Button(icon_name="edit-delete-symbolic")
            del_btn.add_css_class("flat")
            del_btn.connect("clicked", self._on_delete, i)
            hbox.append(del_btn)
            card.append(hbox)

            stars = Gtk.Box(spacing=4, halign=Gtk.Align.CENTER)
            stars.set_margin_bottom(8)
            for j in range(goal["target"]):
                s = Gtk.Button(label="\u2b50" if j < goal["progress"] else "\u2606")
                s.add_css_class("flat")
                s.connect("clicked", self._on_star, i, j)
                stars.append(s)
            card.append(stars)

            prog = Gtk.Label(label=_("%d of %d") % (goal["progress"], goal["target"]))
            prog.add_css_class("dim-label")
            prog.set_margin_bottom(8)
            card.append(prog)

            if goal["progress"] >= goal["target"]:
                done = Gtk.Label(label=_("Goal reached!"))
                done.add_css_class("title-4")
                done.set_margin_bottom(8)
                card.append(done)

            self.goal_box.append(card)

    def _on_star(self, btn, gi, si):
        self.goals[gi]["progress"] = si + 1
        _save_goals(self.goals)
        self._refresh_goals()

    def _on_add_goal(self, *_):
        d = Adw.MessageDialog(transient_for=self, heading=_("New Goal"), body=_("Enter goal name:"))
        entry = Gtk.Entry(placeholder_text=_("e.g. Brush teeth"))
        d.set_extra_child(entry)
        d.add_response("cancel", _("Cancel"))
        d.add_response("add", _("Add"))
        d.set_response_appearance("add", Adw.ResponseAppearance.SUGGESTED)
        def on_resp(dlg, resp):
            if resp == "add" and entry.get_text().strip():
                self.goals.append({"name": entry.get_text().strip(), "emoji": "\U0001f31f", "target": 5, "progress": 0})
                _save_goals(self.goals)
                self._refresh_goals()
        d.connect("response", on_resp)
        d.present()

    def _on_delete(self, btn, idx):
        del self.goals[idx]
        _save_goals(self.goals)
        self._refresh_goals()

    def _on_reset(self, *_):
        for g in self.goals: g["progress"] = 0
        _save_goals(self.goals)
        self._refresh_goals()

    def do_export(self):
        from beloningskartan.export import export_csv, export_json
        os.makedirs(CONFIG_DIR, exist_ok=True)
        ts = GLib.DateTime.new_now_local().format("%Y%m%d_%H%M%S")
        data = [{"date": "", "details": g["name"], "result": f'{g["progress"]}/{g["target"]}'} for g in self.goals]
        export_csv(data, os.path.join(CONFIG_DIR, f"export_{ts}.csv"))
        export_json(data, os.path.join(CONFIG_DIR, f"export_{ts}.json"))

    def _toggle_theme(self, *_):
        mgr = Adw.StyleManager.get_default()
        mgr.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT if mgr.get_dark() else Adw.ColorScheme.FORCE_DARK)

    def _update_clock(self):
        self.status_label.set_label(GLib.DateTime.new_now_local().format("%Y-%m-%d %H:%M:%S"))
        return True


def main():
    app = RewardApp()
    app.run(sys.argv)

if __name__ == "__main__":
    main()
