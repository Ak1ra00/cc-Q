# (c) 2026 cc-Q. The plugin layer: apps register here, and nothing else knows they exist.
#
# An app gets its storage, its encryption subkey, its theming and its slot on the
# home screen from the framework. It must not reach outside its own namespace for
# any of them, and it must not know about any other app.

APPS = []


class DQApp:
    name = None         # storage namespace, e.g. "vault". Stable forever: it keys the file.
    title = None        # shown in the UI
    hotkey = None       # single character, pressed from the home screen

    def home_line(self):
        """Right-hand status for the home screen, and whether to alert on it.

        Returns (text, is_alert). Called on every home screen draw, so keep it
        cheap and never let it raise -- the home screen shows every app or none.
        """
        return ('', False)

    async def start(self):
        raise NotImplementedError

    # -- storage, handed out by the framework -------------------------------
    def store(self):
        from dq.store import RecordStore
        return RecordStore(self.name)


def register_app(cls):
    "Decorator. Collisions raise at import time, not when someone presses a key."
    app = cls()
    for f in ('name', 'title', 'hotkey'):
        if not getattr(app, f, None):
            raise ValueError('%s has no %s' % (cls.__name__, f))
    if len(app.hotkey) != 1:
        raise ValueError('%s: hotkey must be one character' % cls.__name__)
    for other in APPS:
        if other.hotkey == app.hotkey:
            raise ValueError('hotkey %r: %s and %s' % (app.hotkey, other.title, app.title))
        if other.name == app.name:
            raise ValueError('two apps named %r' % app.name)
    APPS.append(app)
    return cls


def find(hotkey):
    for app in APPS:
        if app.hotkey == hotkey:
            return app
    return None
