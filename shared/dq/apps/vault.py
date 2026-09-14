# (c) 2026 cc-Q. Passwords, searchable, each with a number that never changes.
#
# The id is the spine of the feature: assigned once, never reused, never
# renumbered. It is what the owner writes on paper, and for derived entries it is
# the only thing needed to regenerate the password from the seed.
#
# Two sources, and the difference is a backup story, so it is always on screen:
#   stored  -- password is sealed in the record; gone if the device is wiped
#   derived -- BIP-85 from (seed, id); survives a wipe if the seed does
#
from dq.apps import DQApp, register_app

NAME = 'vault'
AUTO_HIDE = 20                  # seconds; resets on any keypress


# ------------------------------------------------------------- pure logic --

def next_id(records):
    "ids are never reused, even after deletes"
    return max([int(r.get('id', 0)) for r in records] + [0]) + 1


def search(records, query):
    "case-insensitive substring over service and login"
    q = (query or '').strip().lower()
    if not q:
        return list(records)
    return [r for r in records
            if q in str(r.get('service', '')).lower()
            or q in str(r.get('login', '')).lower()]


def new_entry(records, service, login, source='stored', note='', created=None):
    if source not in ('stored', 'derived'):
        raise ValueError('source')
    rec = {'id': next_id(records), 'service': service, 'login': login,
           'source': source, 'note': note}
    # No clock on this device, so a date is only recorded when the owner has
    # actually told us what day it is. A guessed date is worse than none.
    if created:
        rec['created'] = created
    return rec


def export_lines(records):
    """The wallet card: service | login | id, and deliberately no passwords.

    For derived entries the id is sufficient to regenerate. For stored entries
    the file is useless without the device, which is the point.
    """
    out = ['service | login | id']
    for r in sorted(records, key=lambda r: int(r.get('id', 0))):
        out.append('%s | %s | %d' % (r.get('service', ''), r.get('login', ''),
                                     int(r.get('id', 0))))
    return out


TAG_LEN = 16            # truncated HMAC; enough to catch a wrong key, cheap to store


def _entry_key(app_key, rec_id):
    from dq.keys import hkdf_sha256
    return hkdf_sha256(app_key, info=b'vault/secret/%d' % int(rec_id))


def seal_secret(app_key, rec_id, password):
    """Per-entry ciphertext, so a password is never sitting in the record as text.

    Authenticated, so opening it under the wrong id fails as a clear error rather
    than handing back rubbish -- or throwing UnicodeDecodeError at the UI.
    """
    import ngu
    from ubinascii import b2a_base64
    key = _entry_key(app_key, rec_id)
    nonce = ngu.random.bytes(16)
    ct = ngu.aes.CTR(key, nonce).cipher(password.encode())
    tag = ngu.hmac.hmac_sha256(key, nonce + ct)[:TAG_LEN]
    return b2a_base64(nonce + ct + tag).decode().strip()


def open_secret(app_key, rec_id, sealed):
    import ngu
    from ubinascii import a2b_base64
    from dq.store import _eq
    raw = a2b_base64(sealed)
    if len(raw) < 16 + TAG_LEN:
        raise ValueError('entry secret is truncated')

    key = _entry_key(app_key, rec_id)
    body, tag = raw[:-TAG_LEN], raw[-TAG_LEN:]
    if not _eq(ngu.hmac.hmac_sha256(key, body)[:TAG_LEN], tag):
        raise ValueError('entry secret does not match this entry')
    return ngu.aes.CTR(key, body[:16]).cipher(body[16:]).decode()


def password_for(rec, app_key=None):
    "the password for a record, whichever source it uses"
    if rec.get('source') == 'derived':
        from dq.keys import derive_password
        return derive_password(int(rec['id']))
    if not rec.get('secret'):
        raise ValueError('entry has no stored secret')
    return open_secret(app_key, int(rec['id']), rec['secret'])


# -------------------------------------------------------------------- app --

@register_app
class Vault(DQApp):
    name = NAME
    title = 'vault'
    hotkey = 'v'

    def home_line(self):
        try:
            n = len(self.store().load())
        except Exception:
            return ('unreadable', True)
        return ('%d entries' % n if n != 1 else '1 entry', False)

    async def start(self):
        from dq.ui import pick_from_list, show_error
        try:
            records = self.store().load()
        except Exception as exc:
            await show_error('vault', exc)
            return

        while True:
            chosen = await pick_from_list(
                'vault', records,
                line=lambda r: (r.get('service', '?'), str(r.get('id', ''))),
                match=search,
                footer='OK open   X back')
            if chosen is None:
                return
            await self.show_entry(records, chosen)

    async def show_entry(self, records, rec):
        from dq.ui import show_secret, show_error
        try:
            pw = password_for(rec, self.store().key())
        except Exception as exc:
            await show_error('vault', exc)
            return
        await show_secret(title=rec.get('service', '?'),
                          right='#%s' % rec.get('id', ''),
                          subtitle=rec.get('login', ''),
                          secret=pw,
                          note=rec.get('source', 'stored'),
                          hide_after=AUTO_HIDE)
