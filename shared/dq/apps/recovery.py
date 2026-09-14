# (c) 2026 cc-Q. The answer to "if this Q is wiped, it all goes with it".
#
# The device key is the root of every app's storage. Split it into shares, put
# them in different places, and the vault, journal and codes files on a microSD
# become readable again on a replacement device. Without it they are noise.
#
# n-of-n XOR, not k-of-n Shamir. Every share is needed. That is a real
# limitation and it is stated on screen, not buried: SLIP-39 would give k-of-n
# but needs GF(256) arithmetic and a wordlist this does not have room to get
# wrong quietly.
#
# One share on its own is uniformly random and reveals nothing, which is the
# property that makes it safe to store them apart.
#
from dq.apps import DQApp, register_app

NAME = 'recovery'
VERSION = 1
SECRET_LEN = 32
CHECK_LEN = 4                   # bytes of digest carried in each share


# ------------------------------------------------------------- pure logic --

def split(secret, n, _randoms=None):
    "secret -> n shares that XOR back to it. Every share is required."
    if len(secret) != SECRET_LEN:
        raise ValueError('want %d bytes' % SECRET_LEN)
    if not 2 <= n <= 8:
        raise ValueError('2 to 8 shares')

    import ngu
    parts = []
    for i in range(n - 1):
        parts.append(_randoms[i] if _randoms else ngu.random.bytes(SECRET_LEN))

    last = bytearray(secret)
    for p in parts:
        for j in range(SECRET_LEN):
            last[j] ^= p[j]
    parts.append(bytes(last))

    check = _check(secret)
    return [encode(i + 1, n, p, check) for i, p in enumerate(parts)]


def combine(shares):
    "shares -> the secret. Raises if they do not belong together or are short."
    if not shares:
        raise ValueError('no shares')

    decoded = [decode(s) for s in shares]
    n = decoded[0][1]
    check = decoded[0][3]

    seen = set()
    acc = bytearray(SECRET_LEN)
    for idx, total, part, chk in decoded:
        if total != n or chk != check:
            raise ValueError('shares are from different splits')
        if idx in seen:
            raise ValueError('share %d given twice' % idx)
        seen.add(idx)
        for j in range(SECRET_LEN):
            acc[j] ^= part[j]

    if len(seen) != n:
        missing = sorted(set(range(1, n + 1)) - seen)
        raise ValueError('need all %d shares, missing %s'
                         % (n, ', '.join(str(m) for m in missing)))

    secret = bytes(acc)
    if _check(secret) != check:
        raise ValueError('shares do not reconstruct: one is damaged')
    return secret


def encode(idx, total, part, check):
    "ccq1 2/3 <base32 of the share> <base32 of the check>"
    from dq.otp import b32encode
    return 'ccq%d %d/%d %s %s' % (VERSION, idx, total,
                                  b32encode(part), b32encode(check))


def decode(text):
    "-> (index, total, part bytes, check bytes)"
    from dq.otp import b32decode
    bits = (text or '').strip().split()
    if len(bits) != 4 or not bits[0].startswith('ccq'):
        raise ValueError('not a cc-Q share')
    if bits[0] != 'ccq%d' % VERSION:
        raise ValueError('share version %s is not %d' % (bits[0][3:], VERSION))

    try:
        idx, total = (int(x) for x in bits[1].split('/'))
    except ValueError:
        raise ValueError('bad share number')
    if not 1 <= idx <= total or not 2 <= total <= 8:
        raise ValueError('bad share number %d/%d' % (idx, total))

    part = b32decode(bits[2])
    check = b32decode(bits[3])
    if len(part) != SECRET_LEN:
        raise ValueError('share is %d bytes, want %d' % (len(part), SECRET_LEN))
    if len(check) != CHECK_LEN:
        raise ValueError('bad check field')
    return idx, total, part, check


def _check(secret):
    import ngu
    return ngu.hash.sha256s(b'cc-Q/recovery/v%d' % VERSION + secret)[:CHECK_LEN]


# -------------------------------------------------------------------- app --

@register_app
class Recovery(DQApp):
    name = NAME
    title = 'recovery'
    hotkey = 'b'                # b for backup; r is taken by resync inside codes

    def home_line(self):
        from dq.keys import is_first_run
        if is_first_run():
            return ('no device key yet', False)
        from glob import settings
        return ('backed up' if settings.get('dq_split') else 'never split', True)

    async def start(self):
        from dq.ui import menu_choice, show_error
        pick = await menu_choice('recovery', [
            ('split the device key', 'split'),
            ('restore from shares', 'restore'),
            ('check a share', 'check')])
        try:
            if pick == 'split':
                await self.do_split()
            elif pick == 'restore':
                await self.do_restore()
            elif pick == 'check':
                await self.do_check()
        except Exception as exc:
            await show_error('recovery', exc)

    async def do_split(self):
        from ux import ux_show_story, ux_confirm
        from dq.keys import device_key
        from dq.ui import show_secret
        from glob import settings

        ok = await ux_confirm(
            'Split this device key into shares?\n\n'
            'EVERY share is needed to rebuild it. Lose one and the vault, '
            'journal and codes on your cards can never be read again.\n\n'
            'Each share on its own reveals nothing, so keep them apart.',
            title='split')
        if not ok:
            return

        n = 3
        shares = split(device_key(), n)
        for i, share in enumerate(shares):
            await show_secret(title='share %d of %d' % (i + 1, n), right='',
                              subtitle='write it down, then press a key',
                              secret=share, note='all %d needed' % n,
                              hide_after=120)
        settings.put('dq_split', n)
        settings.save()
        await ux_show_story(
            'Done. %d shares.\n\nTest them now: choose Restore and enter all '
            '%d. Better to find a copying mistake today.' % (n, n), title='split')

    async def do_restore(self):
        from ux import ux_show_story, ux_confirm
        from ubinascii import hexlify as b2a_hex
        from dq.ui import collect_lines
        from dq.keys import SETTINGS_KEY, is_first_run
        from glob import settings

        shares = await collect_lines('restore', 'share %d', done_when=combine)
        if not shares:
            return
        secret = combine(shares)

        if not is_first_run():
            ok = await ux_confirm(
                'Replace the device key on this Q?\n\n'
                'Anything stored under the current key becomes unreadable. '
                'Only do this on a device you are rebuilding.', title='restore')
            if not ok:
                return

        settings.put(SETTINGS_KEY, b2a_hex(secret).decode())
        settings.save()
        await ux_show_story('Device key restored.\n\nPut a card in and open the '
                            'vault to check.', title='restore')

    async def do_check(self):
        from ux import ux_show_story
        from dq.ui import collect_lines
        got = await collect_lines('check', 'share', limit=1)
        if not got:
            return
        idx, total, _, _ = decode(got[0])
        await ux_show_story('Share %d of %d. It is well formed.\n\nThat does not '
                            'prove the set rebuilds: only a restore does.'
                            % (idx, total), title='check')
