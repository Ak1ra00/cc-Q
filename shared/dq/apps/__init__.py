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

    def load_for_home(self):
        """Records for a home_line, or a status to show instead.

        Returns (records, None) or (None, (text, is_alert)). "No card" and
        "this file is damaged" are very different things -- one means put a card
        in, the other means something is wrong with your data -- so they never
        share a message.
        """
        try:
            from files import CardMissingError
        except ImportError:
            CardMissingError = None
        try:
            return (self.store().load(), None)
        except Exception as exc:
            if CardMissingError and isinstance(exc, CardMissingError):
                return (None, ('no card', False))
            from dq.store import BadMAC
            if isinstance(exc, BadMAC):
                return (None, ('damaged file', True))
            return (None, ('unreadable', True))


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
