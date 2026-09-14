# (c) 2026 cc-Q. What the landing screen shows.
#
# Not a screen of its own any more. cc-Q's top level is a real MenuSystem -- so
# it gets upstream's proven scrolling, shortcuts and back handling for free --
# and this module supplies its rows: one line per app carrying that app's own
# status, plus the date and storage line above them.
#
# There is no second "status" screen. There used to be, and it listed the same
# apps a keypress away from the menu that listed them, which is a fork in the
# road at the very first thing you see.
#
from menu import MenuItem
from dq.apps import APPS

TITLE_W = 9                     # widest app title, plus a space

_status = {}                    # app name -> (text, is_alert), read from storage


def invalidate():
    """Forget cached statuses. Called when an app exits, because that is the
    only moment one can have changed -- polling storage on every redraw would
    spin the card for nothing."""
    _status.clear()


def status_for(app):
    if app.name not in _status:
        try:
            _status[app.name] = app.home_line()
        except Exception:
            _status[app.name] = ('?', True)
    return _status[app.name]


def row_label(app):
    "'vault     42 entries', padded so the statuses line up"
    text, _alert = status_for(app)
    title = app.title[:TITLE_W]
    return '%s%s %s' % (title, ' ' * (TITLE_W - len(title)), text) if text else title


class AppRow(MenuItem):
    """A menu row whose label is computed when it is drawn.

    MenuItem stores label as a plain attribute; overriding it as a property
    keeps each row's status current without rebuilding the menu.
    """

    def __init__(self, app, launcher):
        self._app = app
        super().__init__('', f=launcher, arg=app.hotkey, shortcut=app.hotkey)

    @property
    def label(self):
        return row_label(self._app)

    @label.setter
    def label(self, _value):
        pass                    # MenuItem.__init__ assigns one; ours is computed


def info_label():
    "the date, and whether anything can be saved"
    from dq.session import today_or_none
    today = today_or_none() or 'date not set'
    return '%s  %s' % (today, storage())


def storage():
    try:
        from files import CardSlot
        if not CardSlot.is_inserted():
            return 'no card'
        return 'card A+B' if CardSlot.both_inserted() else 'card A'
    except Exception:
        return ''


async def set_date(*a):
    "the info row is not decoration: it is how you tell the Q what day it is"
    from dq.session import ask_today, forget
    forget()
    await ask_today()
    invalidate()


def rows(launcher):
    "the app rows, in registration order"
    return [AppRow(app, launcher) for app in APPS]
