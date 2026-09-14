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


def _char_map():
    "the keyboard's own table: the only honest answer to 'can this be typed?'"
    from usb import EmulatedKeyboard
    return EmulatedKeyboard.char_map


def untypable(text):
    "the characters the emulated keyboard has no key for, in order, no repeats"
    try:
        char_map = _char_map()
    except ImportError:
        return []                       # off-device: nothing to check against
    seen = []
    for ch in text or '':
        if ch.lower() not in char_map and ch not in seen:
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
    """Confirm, then type. Returns True if it was sent.

    Drives EmulatedKeyboard directly rather than going through
    drv_entro.single_send_keystrokes, which appends a carriage return to
    everything it sends. That is right for a password going into a login box and
    wrong for a snippet going into a form field, so the choice has to be ours.
    """
    keys = plan(text, press_enter)

    if not enabled():
        from ux import ux_show_story
        await ux_show_story(
            'USB keyboard emulation is off.\n\n'
            'Turn it on in Settings > USB Keyboard first. It is off by default '
            'because it lets this device type into whatever is in front of it.',
            title='keyboard')
        return False

    from ux import ux_show_story, ux_dramatic_pause, OK
    from usb import EmulatedKeyboard

    msg = 'Put the cursor where you want it typed, then press %s.' % OK
    if label:
        msg = '%s\n\n%s' % (label, msg)
    if press_enter:
        msg += '\n\nEnter will be pressed afterwards.'

    if await ux_show_story(msg, title='type') != 'y':
        return False

    with EmulatedKeyboard() as kbd:
        if await kbd.connect():
            return False                # host would not enumerate us; it said so
        await kbd.send_keystrokes(keys)

    await ux_dramatic_pause('Sent.', 0.25)
    return True
