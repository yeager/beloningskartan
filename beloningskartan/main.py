"""Belöningskartan — Visual reward system."""

import gettext
import json
import locale
from datetime import datetime
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from beloningskartan import __version__
from beloningskartan.export import show_export_dialog

try:
    locale.setlocale(locale.LC_ALL, "")
except locale.Error:
    pass
for d in [Path(__file__).parent.parent / "po", Path("/usr/share/locale")]:
    if d.is_dir():
        locale.bindtextdomain("beloningskartan", str(d))
        gettext.bindtextdomain("beloningskartan", str(d))
        break
gettext.textdomain("beloningskartan")
_ = gettext.gettext

APP_ID = "se.danielnylander.beloningskartan"


def _config_dir():
    p = Path(GLib.get_user_config_dir()) / "beloningskartan"
    p.mkdir(parents=True, exist_ok=True)
    return p

def _load_data():
    path = _config_dir() / "rewards.json"
    if path.exists():
        try: return json.loads(path.read_text())
        except Exception: pass
    return {"goals": [], "stars": 0, "history": []}

def _save_data(data):
    (_config_dir() / "rewards.json").write_text(json.dumps(data, indent=2, ensure_ascii=False))


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title=_("Reward Chart"))
        self.set_default_size(500, 650)
        self.data = _load_data()

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(main_box)

        header = Adw.HeaderBar()
        main_box.append(header)

        self.stars_label = Gtk.Label(label=f"⭐ {self.data.get('stars', 0)}")
        self.stars_label.add_css_class("title-2")
        header.pack_start(self.stars_label)

        add_btn = Gtk.Button(icon_name="list-add-symbolic", tooltip_text=_("Add Goal"))
        add_btn.add_css_class("suggested-action")
        add_btn.connect("clicked", self._on_add_goal)
        header.pack_start(add_btn)

        export_btn = Gtk.Button(icon_name="document-save-symbolic", tooltip_text=_("Export (Ctrl+E)"))
        export_btn.connect("clicked", lambda *_: self._on_export())
        header.pack_end(export_btn)

        menu = Gio.Menu()
        menu.append(_("Export Progress"), "win.export")
        menu.append(_("About Reward Chart"), "app.about")
        menu.append(_("Quit"), "app.quit")
        menu_btn = Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu)
        header.pack_end(menu_btn)

        ea = Gio.SimpleAction.new("export", None)
        ea.connect("activate", lambda *_: self._on_export())
        self.add_action(ea)

        ctrl = Gtk.EventControllerKey()
        ctrl.connect("key-pressed", self._on_key)
        self.add_controller(ctrl)

        # Title
        title = Gtk.Label(label=_("Your Goals"))
        title.add_css_class("title-2")
        title.set_margin_top(16)
        main_box.append(title)

        subtitle = Gtk.Label(label=_("Earn stars by completing tasks!"))
        subtitle.add_css_class("dim-label")
        main_box.append(subtitle)

        # Goals list
        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_margin_top(12)
        scroll.set_margin_start(12)
        scroll.set_margin_end(12)
        self.goals_list = Gtk.ListBox()
        self.goals_list.add_css_class("boxed-list")
        scroll.set_child(self.goals_list)
        main_box.append(scroll)

        # Quick star buttons
        star_box = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER)
        star_box.set_margin_top(12)
        star_box.set_margin_bottom(12)
        for label, stars in [(_("Good job! +1⭐"), 1), (_("Great! +3⭐"), 3), (_("Amazing! +5⭐"), 5)]:
            btn = Gtk.Button(label=label)
            btn.add_css_class("pill")
            btn.connect("clicked", self._on_add_stars, stars)
            star_box.append(btn)
        main_box.append(star_box)

        self.status = Gtk.Label(label="", xalign=0)
        self.status.add_css_class("dim-label")
        self.status.set_margin_start(12)
        self.status.set_margin_bottom(4)
        main_box.append(self.status)
        GLib.timeout_add_seconds(1, lambda: (self.status.set_label(GLib.DateTime.new_now_local().format("%Y-%m-%d %H:%M:%S")), True)[-1])

        self._refresh_goals()

    def _on_key(self, ctrl, keyval, keycode, state):
        if state & Gdk.ModifierType.CONTROL_MASK and keyval in (Gdk.KEY_e, Gdk.KEY_E):
            self._on_export()
            return True
        return False

    def _on_export(self):
        show_export_dialog(self, self.data.get("history", []), _("Reward Chart"), lambda m: self.status.set_label(m))

    def _on_add_stars(self, btn, count):
        self.data["stars"] = self.data.get("stars", 0) + count
        self.data.setdefault("history", []).append({
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "stars": count,
            "total": self.data["stars"],
        })
        self.stars_label.set_label(f"⭐ {self.data['stars']}")
        _save_data(self.data)
        self.status.set_label(_("Added %d stars! Total: %d") % (count, self.data["stars"]))

    def _on_add_goal(self, *_args):
        dialog = Adw.AlertDialog.new(_("Add Goal"), _("What do you want to work towards?"))
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        name_entry = Gtk.Entry()
        name_entry.set_placeholder_text(_("Goal name (e.g. 'New toy')"))
        box.append(name_entry)
        cost_spin = Gtk.SpinButton.new_with_range(1, 100, 1)
        cost_spin.set_value(10)
        cost_box = Gtk.Box(spacing=8)
        cost_box.append(Gtk.Label(label=_("Stars needed:")))
        cost_box.append(cost_spin)
        box.append(cost_box)
        dialog.set_extra_child(box)
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("add", _("Add"))
        dialog.set_response_appearance("add", Adw.ResponseAppearance.SUGGESTED)

        def on_resp(d, r):
            if r == "add" and name_entry.get_text().strip():
                self.data.setdefault("goals", []).append({
                    "name": name_entry.get_text().strip(),
                    "cost": int(cost_spin.get_value()),
                    "done": False,
                })
                _save_data(self.data)
                self._refresh_goals()
        dialog.connect("response", on_resp)
        dialog.present(self)

    def _refresh_goals(self):
        child = self.goals_list.get_first_child()
        while child:
            nc = child.get_next_sibling()
            self.goals_list.remove(child)
            child = nc
        stars = self.data.get("stars", 0)
        for i, goal in enumerate(self.data.get("goals", [])):
            row = Adw.ActionRow()
            row.set_title(goal["name"])
            progress = min(stars, goal["cost"])
            row.set_subtitle(f"{progress}/{goal['cost']} ⭐")
            if stars >= goal["cost"]:
                claim_btn = Gtk.Button(label=_("Claim! 🎉"))
                claim_btn.add_css_class("suggested-action")
                claim_btn.connect("clicked", self._on_claim, i)
                row.add_suffix(claim_btn)
            self.goals_list.append(row)

    def _on_claim(self, btn, idx):
        goals = self.data.get("goals", [])
        if idx < len(goals):
            cost = goals[idx]["cost"]
            self.data["stars"] = max(0, self.data.get("stars", 0) - cost)
            self.stars_label.set_label(f"⭐ {self.data['stars']}")
            self.data.setdefault("history", []).append({
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "claimed": goals[idx]["name"],
                "cost": cost,
            })
            goals.pop(idx)
            _save_data(self.data)
            self._refresh_goals()
            self.status.set_label(_("🎉 Goal claimed!"))


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)
        self.connect("activate", self._on_activate)

    def _on_activate(self, *_args):
        win = self.props.active_window or MainWindow(self)
        a = Gio.SimpleAction(name="about"); a.connect("activate", self._on_about); self.add_action(a)
        qa = Gio.SimpleAction(name="quit"); qa.connect("activate", lambda *_: self.quit()); self.add_action(qa)
        self.set_accels_for_action("app.quit", ["<Control>q"])
        win.present()

    def _on_about(self, *_args):
        dialog = Adw.AboutDialog(
            application_name=_("Reward Chart"), application_icon=APP_ID, version=__version__,
            developer_name="Daniel Nylander", license_type=Gtk.License.GPL_3_0,
            website="https://www.autismappar.se",
            developers=["Daniel Nylander <daniel@danielnylander.se>"],
            comments=_("Visual reward system with stars and goals"),
        )
        dialog.present(self.props.active_window)


def main():
    app = App()
    return app.run()
