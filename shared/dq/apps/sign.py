# (c) 2026 cc-Q. Sign text with a key that has nothing to do with Bitcoin.
#
# Proving "I wrote this" from a device that has never been on a network is
# genuinely hard to do anywhere else, and it needs no seed: the identity key
# comes off the device key, so it works on a seedless Q like everything else.
#
# Signatures are recoverable (65 bytes), so a verifier needs the message and the
# signature and nothing else -- the public key falls out of the verification.
#
from dq.apps import DQApp, register_app

NAME = 'sign'
PREAMBLE = b'cc-Q signed message v1\n'


# ------------------------------------------------------------- pure logic --

def digest(text):
    "what actually gets signed: a domain-separated double SHA-256"
    import ngu
    body = text.encode() if isinstance(text, str) else text
    return ngu.hash.sha256d(PREAMBLE + body)


def identity_key(app_key, index=0):
    "a signing key per index, so the owner can hold more than one identity"
    from dq.keys import hkdf_sha256
    return hkdf_sha256(app_key, info=b'sign/identity/%d' % int(index))


def fingerprint(pubkey_bytes):
    "short, readable, and enough for someone to compare across a table"
    import ngu
    from dq.otp import b32encode
    h = ngu.hash.sha256s(pubkey_bytes)[:5]
    raw = b32encode(h)
    return '-'.join(raw[i:i + 4] for i in range(0, 8, 4))


def armor(text, sig_bytes, fp):
    "the block someone pastes elsewhere; parse_armor is its exact inverse"
    from ubinascii import b2a_base64
    sig = b2a_base64(sig_bytes).decode().strip()
    return ('----- cc-Q signed -----\n'
            '%s\n'
            '----- signature -----\n'
            '%s\n'
            'key %s\n'
            '----- end -----' % (text, sig, fp))


def parse_armor(blob):
    "-> (text, signature bytes, claimed fingerprint or None)"
    from ubinascii import a2b_base64
    lines = (blob or '').replace('\r\n', '\n').split('\n')
    try:
        start = lines.index('----- cc-Q signed -----')
        mid = lines.index('----- signature -----')
    except ValueError:
        raise ValueError('not a cc-Q signed block')

    end = len(lines)
    for marker in ('----- end -----',):
        if marker in lines:
            end = lines.index(marker)

    text = '\n'.join(lines[start + 1:mid])
    fp = None
    sig_lines = []
    for line in lines[mid + 1:end]:
        if line.startswith('key '):
            fp = line[4:].strip()
        elif line.strip():
            sig_lines.append(line.strip())
    if not sig_lines:
        raise ValueError('no signature in block')

    sig = a2b_base64(''.join(sig_lines))
    if len(sig) != 65:
        raise ValueError('signature is %d bytes, want 65' % len(sig))
    return text, sig, fp


# ------------------------------------------------------ device operations --

def sign_text(app_key, text, index=0):
    "-> (armored block, fingerprint)"
    import ngu
    priv = identity_key(app_key, index)
    sig = ngu.secp256k1.sign(priv, digest(text), 0).to_bytes()
    pub = ngu.secp256k1.keypair(priv).pubkey().to_bytes()
    return armor(text, sig, fingerprint(pub)), fingerprint(pub)


def verify_blob(blob):
    """-> (text, fingerprint of whoever signed it)

    The key is recovered from the signature, so this verifies a block from any
    cc-Q, not just this one.
    """
    import ngu
    text, sig, claimed = parse_armor(blob)
    pub = ngu.secp256k1.signature(sig).verify_recover(digest(text))
    if pub is None:
        raise ValueError('signature does not match the text')
    fp = fingerprint(pub.to_bytes())
    if claimed and claimed != fp:
        raise ValueError('block claims key %s but signs as %s' % (claimed, fp))
    return text, fp


# -------------------------------------------------------------------- app --

@register_app
class Sign(DQApp):
    name = NAME
    title = 'sign'
    hotkey = 's'

    def home_line(self):
        try:
            from dq.keys import is_first_run
            if is_first_run():
                return ('ready on first use', False)
            return (self.my_fingerprint(), False)
        except Exception:
            return ('', False)

    def my_fingerprint(self, index=0):
        import ngu
        priv = identity_key(self.store().key(), index)
        return fingerprint(ngu.secp256k1.keypair(priv).pubkey().to_bytes())

    async def start(self):
        from dq.ui import menu_choice, show_error
        pick = await menu_choice('sign', [
            ('sign some text', 'sign'),
            ('verify a block', 'verify'),
            ('show my key', 'key')])
        try:
            if pick == 'sign':
                await self.do_sign()
            elif pick == 'verify':
                await self.do_verify()
            elif pick == 'key':
                await self.do_key()
        except Exception as exc:
            await show_error('sign', exc)

    async def do_sign(self):
        from dq.ui import edit_text, offer_export
        text = await edit_text('sign', '', lines=5)
        if not text:
            return
        blob, fp = sign_text(self.store().key(), text)
        await offer_export('signed', blob, filename='signed.txt', qr_ok=True)

    async def do_verify(self):
        from ux import ux_show_story
        from dq.ui import import_text
        blob = await import_text('verify')
        if not blob:
            return
        text, fp = verify_blob(blob)
        await ux_show_story('Good signature.\n\nkey %s\n\n%s' % (fp, text),
                            title='verified')

    async def do_key(self):
        from dq.ui import show_secret
        fp = self.my_fingerprint()
        await show_secret(title='my key', right='', subtitle='fingerprint',
                          secret=fp, note='from the device key', hide_after=60)
