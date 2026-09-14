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

def live(records):
    "the entries that still exist; deleted ones leave a tombstone behind"
    return [r for r in records if not r.get('deleted')]


def next_id(records):
    "ids are never reused, even after deletes -- tombstones keep them claimed"
    return max([int(r.get('id', 0)) for r in records] + [0]) + 1


def search(records, query):
    "case-insensitive substring over service and login"
    rows = live(records)
    q = (query or '').strip().lower()
    if not q:
        return rows
    return [r for r in rows
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


def delete_entry(records, rec):
    """Delete the entry's content, keep its number claimed forever.

    A reused id would point a paper card at the wrong account, and for a derived
    entry it would regenerate a different password. So the record is emptied --
    secret, service, login, everything -- and what remains is a tombstone: the
    id, and the fact that it is gone. It travels with the file, so the guarantee
    survives a card swap or a restore onto another device.
    """
    rec_id = int(rec.get('id', 0))
    rec.clear()
    rec['id'] = rec_id
    rec['deleted'] = True
    return records


def edit_entry(rec, service=None, login=None, note=None):
    "change the label fields; never the id, never the source"
    if service is not None:
        rec['service'] = service
    if login is not None:
        rec['login'] = login
    if note is not None:
        rec['note'] = note
    return rec


def export_lines(records):
    """The wallet card: service | login | id, and deliberately no passwords.

    For derived entries the id is sufficient to regenerate. For stored entries
    the file is useless without the device, which is the point.
    """
    out = ['service | login | id']
    for r in sorted(live(records), key=lambda r: int(r.get('id', 0))):
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
        records, status = self.load_for_home()
        if status:
            return status
        n = len(live(records))
        return ('%d entries' % n if n != 1 else '1 entry', False)

    async def start(self):
        from dq import ui
        try:
            records = self.store().load()
        except Exception as exc:
            await ui.show_error('vault', exc)
            return

        while True:
            pick = await ui.menu_choice('vault', [
                ('find an entry', 'find'),
                ('new entry', 'new'),
                ('export the card list', 'export'),
                ('import an export', 'import')])
            if pick is None:
                return
            try:
                if pick == 'find':
                    await self.browse(records)
                elif pick == 'new':
                    if await self.new(records):
                        self.store().save(records)
                elif pick == 'export':
                    await self.export_card(records)
                elif pick == 'import':
                    records, changed = await ui.import_records('vault', records, 'id')
                    if changed:
                        self.store().save(records)
            except Exception as exc:
                await ui.show_error('vault', exc)

    async def browse(self, records):
        from dq.ui import pick_from_list
        while True:
            chosen = await pick_from_list(
                'vault', records,
                line=lambda r: (r.get('service', '?'), str(r.get('id', ''))),
                match=search,
                footer='OK open   X back')
            if chosen is None:
                return
            await self.show_entry(records, chosen)

    async def new(self, records):
        "returns True if something was added"
        from ux import ux_show_story
        from ux_q1 import ux_input_text
        from dq import ui
        from dq.keys import has_seed

        service = await ux_input_text('', prompt='service', max_len=40)
        if not service:
            return False
        login = await ux_input_text('', prompt='login', max_len=60) or ''

        source = 'stored'
        if has_seed():
            # The only place a seed is ever mentioned in the UI, and it is simply
            # absent when there is not one.
            pick = await ui.menu_choice('password', [
                ('type or paste one', 'stored'),
                ('derive it from the seed', 'derived')])
            if pick is None:
                return False
            source = pick

        from dq.session import today_or_none
        rec = new_entry(records, service.strip(), login.strip(), source=source,
                        created=today_or_none())

        if source == 'stored':
            pw = await ux_input_text('', prompt='password', max_len=128)
            if not pw:
                return False
            rec['secret'] = seal_secret(self.store().key(), rec['id'], pw)

        records.append(rec)
        await ux_show_story('Added as #%d.\n\nWrite that number on your card. '
                            'For a derived entry it is the only thing needed to '
                            'get the password back.' % rec['id'], title='vault')
        return True

    async def export_card(self, records):
        from dq.ui import offer_export
        await offer_export('card list', '\n'.join(export_lines(records)),
                           filename='dq-vault-card.txt')

    async def show_entry(self, records, rec):
        from dq import ui
        while True:
            pick = await ui.menu_choice('#%s %s' % (rec.get('id', ''),
                                                    rec.get('service', '?')), [
                ('show the password', 'show'),
                ('type it over USB', 'type'),
                ('rename', 'edit'),
                ('delete', 'delete')])
            if pick is None:
                return
            try:
                if pick == 'show':
                    await self.reveal(rec)
                elif pick == 'type':
                    from dq import hid
                    await hid.send(password_for(rec, self.store().key()),
                                   label=rec.get('service'))
                elif pick == 'edit':
                    if await self.rename(rec):
                        self.store().save(records)
                elif pick == 'delete':
                    if await self.remove(records, rec):
                        self.store().save(records)
                        return
            except Exception as exc:
                await ui.show_error('vault', exc)

    async def reveal(self, rec):
        from dq.ui import show_secret
        pw = password_for(rec, self.store().key())
        await show_secret(title=rec.get('service', '?'),
                          right='#%s' % rec.get('id', ''),
                          subtitle=rec.get('login', ''),
                          secret=pw,
                          note=rec.get('source', 'stored'),
                          hide_after=AUTO_HIDE)

    async def rename(self, rec):
        from ux_q1 import ux_input_text
        service = await ux_input_text(rec.get('service', ''), prompt='service', max_len=40)
        if service is None:
            return False
        login = await ux_input_text(rec.get('login', ''), prompt='login', max_len=60)
        if login is None:
            return False
        edit_entry(rec, service=service.strip(), login=login.strip())
        return True

    async def remove(self, records, rec):
        from ux import ux_confirm
        extra = ('' if rec.get('source') == 'derived' else
                 '\n\nThis password is stored only here. Deleting it is the end of it.')
        if not await ux_confirm('Delete #%s %s?%s' % (rec.get('id'),
                                                      rec.get('service', ''), extra),
                                title='delete'):
            return False
        delete_entry(records, rec)
        return True
