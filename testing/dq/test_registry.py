# The plugin layer. CLAUDE.md says adding an app is four steps and that no app
# knows another; these are the tests that keep that true.
import pytest

ALL = ('vault', 'codes', 'journal', 'recovery', 'sign', 'witness', 'keypad',
       'words', 'dice')


def _load_all():
    import importlib
    from dq.apps import APPS
    for name in ALL:
        importlib.import_module('dq.apps.%s' % name)
    return APPS


def test_every_app_registers(settings):
    assert len(_load_all()) == len(ALL)


def test_hotkeys_are_unique(settings):
    apps = _load_all()
    keys = [a.hotkey for a in apps]
    assert len(set(keys)) == len(keys), 'collision: %s' % keys
    assert all(len(k) == 1 for k in keys)


def test_storage_names_are_unique(settings):
    apps = _load_all()
    names = [a.name for a in apps]
    assert len(set(names)) == len(names)


def test_collisions_raise_at_import_time(settings):
    "not when someone presses the key months later"
    from dq.apps import DQApp, register_app
    _load_all()

    with pytest.raises(ValueError):
        @register_app
        class Clash(DQApp):
            name, title, hotkey = 'something-else', 'clash', 'v'   # vault's key

    with pytest.raises(ValueError):
        @register_app
        class SameName(DQApp):
            name, title, hotkey = 'vault', 'clash', 'Z'            # vault's name


def test_incomplete_app_is_refused(settings):
    from dq.apps import DQApp, register_app
    with pytest.raises(ValueError):
        @register_app
        class NoHotkey(DQApp):
            name, title = 'nope', 'nope'

    with pytest.raises(ValueError):
        @register_app
        class LongHotkey(DQApp):
            name, title, hotkey = 'nope2', 'nope', 'ab'


def test_apps_do_not_import_each_other(settings):
    "invariant 4: an app that reaches into another breaks the plugin layer"
    import os
    here = os.path.dirname(__file__)
    appdir = os.path.normpath(os.path.join(here, '..', '..', 'shared', 'dq', 'apps'))
    for name in ALL:
        src = open(os.path.join(appdir, '%s.py' % name)).read()
        for other in ALL:
            if other == name:
                continue
            assert 'dq.apps.%s' % other not in src, '%s imports %s' % (name, other)


def test_framework_does_not_import_apps(settings):
    """The other half of invariant 4: theme, store, keys, dates and session are
    the framework. If one of them reaches into an app, the app is no longer a
    plugin and cannot be removed."""
    import os
    here = os.path.dirname(__file__)
    dqdir = os.path.normpath(os.path.join(here, '..', '..', 'shared', 'dq'))
    for mod in ('theme', 'keys', 'store', 'clock', 'otp', 'session', 'ui',
                'hid', 'dates'):
        src = open(os.path.join(dqdir, '%s.py' % mod)).read()
        assert 'dq.apps.' not in src, '%s imports an app' % mod


def test_every_app_fits_the_home_screen(settings):
    """Seven rows are visible; the status screen scrolls past that.

    Titles have to fit beside their status text in 32 columns, and no hotkey may
    collide with the two rows the top menu adds itself.
    """
    apps = _load_all()
    for app in apps:
        assert len(app.title) <= 10, app.title
        assert app.hotkey not in ('0', 'z'), 'clashes with status / Coldcard'
    assert len(apps) > 7, 'this test is only interesting once it scrolls'


def test_home_line_never_raises(settings, monkeypatch):
    """The home screen shows every app or none, so a broken store must not
    take the whole screen down with it."""
    from dq.store import RecordStore
    def boom(self):
        raise OSError('no card')
    monkeypatch.setattr(RecordStore, 'load', boom)

    for app in _load_all():
        text, alert = app.home_line()
        assert isinstance(text, str) and isinstance(alert, bool)
