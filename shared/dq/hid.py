# (c) 2026 cc-Q. Typing text into a machine over USB.
#
# A service, not an app: the vault types passwords, keypad types snippets, and
# neither knows the other exists. Any app can call send().
#
# The Q presents as a USB keyboard only while this is running, and only after the
# owner confirms -- the whole point is that they are watching the target window.
#
SETTING_ENABLED = 'emu'         # upstream's keyboard-emulation toggle


def enabled():
    try:
        from glob import settings
        return bool(settings.get(SETTING_ENABLED, False))
    except ImportError:
        return False


# US layout: what the emulated keyboard can actually produce. Anything else would
# arrive as the wrong character on the far machine, which for a password means a
# failed login the owner cannot see the cause of.
TYPABLE = ('abcdefghijklmnopqrstuvwxyz'
           'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
           '0123456789'
           ' !"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~')


def untypable(text):
    "the characters we would get wrong, in order, without duplicates"
    seen = []
    for ch in text or '':
        if ch not in TYPABLE and ch not in seen:
            seen.append(ch)
    return seen


def plan(text, press_enter=False):
    """Exactly what will be sent, or raise saying which characters cannot be.

    Refusing is better than sending a mangled password: a silent wrong character
    looks like a wrong password on the other machine.
    """
    bad = untypable(text)
    if bad:
        raise ValueError('cannot type: %s' % ' '.join(repr(c) for c in bad))
    return text + ('\r' if press_enter else '')


async def send(text, press_enter=False, label=None):
    "confirm, then type. Returns True if it was sent."
    keys = plan(text, press_enter)
    if not enabled():
        from ux import ux_show_story
        await ux_show_story(
            'USB keyboard emulation is off.\n\n'
            'Turn it on in Settings > USB Keyboard first. It is off by default '
            'because it lets this device type into whatever is in front of it.',
            title='keyboard')
        return False

    from drv_entro import single_send_keystrokes
    await single_send_keystrokes(keys, label)
    return True
