# (c) 2026 cc-Q. Random numbers you can prove you did not choose.
#
# Anyone can roll a die. The point here is the commitment: the Q rolls from its
# hardware TRNG, then shows you a hash of (roll + secret nonce) BEFORE revealing
# anything. Write that hash down, or photograph it. When the roll is revealed,
# the other party can recompute the hash and see it matches -- so the result was
# fixed before they knew it, and you could not have re-rolled until you liked it.
#
# Settling a bet, picking who goes first, choosing a name out of a hat: things
# that normally need someone to be trusted.
#
from dq.apps import DQApp, register_app

NAME = 'dice'
TAG = b'cc-Q/dice/v1'
NONCE_LEN = 16
MAX_ROLLS = 20
SETTING_LAST = 'dq_dice'        # the open commitment, if one is waiting


# ------------------------------------------------------------- pure logic --

def roll(sides, count=1, rng=None):
    "unbiased rolls from the TRNG; ngu.random.uniform(n) is already uniform"
    if not 2 <= sides <= 1000:
        raise ValueError('2 to 1000 sides')
    if not 1 <= count <= MAX_ROLLS:
        raise ValueError('1 to %d rolls' % MAX_ROLLS)
    if rng is None:
        import ngu
        rng = ngu.random.uniform
    return [rng(sides) + 1 for _ in range(count)]


def encode(sides, rolls):
    "canonical text for hashing, so two devices agree byte for byte"
    return ('d%d:%s' % (sides, ','.join(str(r) for r in rolls))).encode()


def commitment(sides, rolls, nonce):
    "the hash you show before revealing: binds the rolls AND the die"
    import ngu
    return ngu.hash.sha256s(TAG + nonce + encode(sides, rolls))


def short(digest):
    "what a person copies down: enough to compare, short enough to bother"
    from ubinascii import hexlify
    h = hexlify(digest).decode()
    return '-'.join(h[i:i + 4] for i in range(0, 16, 4))


def verify(sides, rolls, nonce, claimed):
    """Recompute and compare. Accepts the short form or the full digest, since
    the short form is what anyone actually wrote down."""
    from ubinascii import hexlify
    got = commitment(sides, rolls, nonce)
    claimed = (claimed or '').strip().lower().replace('-', '').replace(' ', '')
    full = hexlify(got).decode()
    if not claimed:
        return False
    if len(claimed) < 8:
        return False                    # too short to mean anything
    return full.startswith(claimed) or claimed == full


def new_nonce():
    import ngu
    return ngu.random.bytes(NONCE_LEN)


def describe(sides, rolls):
    "'3, 5, 1  (d6)  total 9' -- fits the Q's 34 columns for a sane count"
    body = ', '.join(str(r) for r in rolls)
    if len(rolls) > 1:
        return '%s  total %d' % (body, sum(rolls))
    return body


def pending():
    "an unrevealed commitment, if one is waiting"
    try:
        from glob import settings
        return settings.get(SETTING_LAST) or None
    except ImportError:
        return None


def hold(sides, rolls, nonce):
    "remember the roll behind a commitment, so a power cycle does not lose it"
    from ubinascii import hexlify
    from glob import settings
    settings.put(SETTING_LAST, {'sides': sides, 'rolls': rolls,
                                'nonce': hexlify(nonce).decode()})
    settings.save()


def release():
    from glob import settings
    settings.remove_key(SETTING_LAST)
    settings.save()


# -------------------------------------------------------------------- app --

@register_app
class Dice(DQApp):
    name = NAME
    title = 'dice'
    hotkey = 'd'

    def home_line(self):
        got = pending()
        if got:
            return ('a roll is sealed', True)
        return ('', False)

    async def start(self):
        from dq import ui
        while True:
            options = [('roll now', 'open'),
                       ('sealed roll', 'sealed'),
                       ('check a sealed roll', 'verify')]
            if pending():
                options.insert(0, ('reveal the sealed roll', 'reveal'))
            pick = await ui.menu_choice('dice', options)
            if pick is None:
                return
            try:
                if pick == 'open':
                    await self.open_roll()
                elif pick == 'sealed':
                    await self.sealed_roll()
                elif pick == 'reveal':
                    await self.reveal()
                elif pick == 'verify':
                    await self.check()
            except Exception as exc:
                await ui.show_error('dice', exc)

    async def ask_die(self):
        from ux_q1 import ux_enter_number
        sides = await ux_enter_number('sides', 1000)
        if not sides:
            return (None, None)
        count = await ux_enter_number('how many', MAX_ROLLS)
        if not count:
            return (None, None)
        return (int(sides), int(count))

    async def open_roll(self):
        from ux import ux_show_story
        sides, count = await self.ask_die()
        if not sides:
            return
        rolls = roll(sides, count)
        await ux_show_story('%s\n\nd%d, from the hardware random number '
                            'generator.' % (describe(sides, rolls), sides),
                            title='roll')

    async def sealed_roll(self):
        from ux import ux_show_story
        if pending():
            await ux_show_story('There is already a sealed roll waiting. Reveal '
                                'it first.', title='dice')
            return

        sides, count = await self.ask_die()
        if not sides:
            return

        rolls = roll(sides, count)
        nonce = new_nonce()
        hold(sides, rolls, nonce)

        await ux_show_story(
            'Sealed.\n\n%s\n\nd%d, %d roll(s). Show this to the other person, or '
            'write it down, BEFORE revealing.\n\nThe result is already decided and '
            'cannot be changed -- revealing it later will produce this same code.'
            % (short(commitment(sides, rolls, nonce)), sides, count),
            title='sealed')

    async def reveal(self):
        from ux import ux_show_story
        from ubinascii import unhexlify
        got = pending()
        if not got:
            return
        sides, rolls = got['sides'], got['rolls']
        nonce = unhexlify(got['nonce'])
        code = short(commitment(sides, rolls, nonce))
        release()
        await ux_show_story(
            '%s\n\nd%d\n\nsealed as\n%s\n\nnonce\n%s\n\nAnyone can check those '
            'three against the code you showed earlier.'
            % (describe(sides, rolls), sides, code, got['nonce']),
            title='revealed')

    async def check(self):
        from ux import ux_show_story
        from ux_q1 import ux_input_text, ux_enter_number
        from ubinascii import unhexlify

        sides = await ux_enter_number('sides', 1000)
        if not sides:
            return
        raw = await ux_input_text('', prompt='rolls, comma separated', max_len=80)
        if not raw:
            return
        nonce_hex = await ux_input_text('', prompt='nonce', max_len=64, scan_ok=True)
        if not nonce_hex:
            return
        claimed = await ux_input_text('', prompt='the sealed code', max_len=40)
        if not claimed:
            return

        rolls = [int(x) for x in raw.replace(' ', '').split(',') if x]
        ok = verify(int(sides), rolls, unhexlify(nonce_hex.strip()), claimed)
        await ux_show_story(
            'MATCHES.\n\nThat roll was sealed before it was shown.' if ok else
            'DOES NOT MATCH.\n\nThese numbers are not what was sealed under that '
            'code -- or something was typed wrong.', title='check')
