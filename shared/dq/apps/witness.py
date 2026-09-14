# (c) 2026 cc-Q. A tamper-evident log of files you held.
#
# Hash a file off the card, record the digest and the date you confirmed, and
# later prove that the file you are holding is bit-for-bit the one you saw. The
# log itself is encrypted like everything else, so the record of what you
# witnessed is as private as the files were.
#
# Storage-shaped rather than keyboard-shaped: this uses the card reader, and one
# entry is under a hundred bytes, so the log stays cheap for years.
#
from dq.apps import DQApp, register_app

NAME = 'witness'
CHUNK = 1024


# ------------------------------------------------------------- pure logic --

def hash_chunks(chunks):
    """Streaming SHA-256, because a file is bigger than free RAM often enough.

    uhashlib, not ngu.hash: ngu only offers one-shot sha256s/sha256d, and holding
    a whole file in memory to use them is exactly the failure this avoids.
    """
    from uhashlib import sha256
    h = sha256()
    for chunk in chunks:
        h.update(chunk)
    return h.digest()


def hexed(digest):
    from ubinascii import hexlify
    return hexlify(digest).decode()


def short(digest_hex, width=16):
    "enough of a digest to compare by eye, in the Q's columns"
    return '%s⋯%s' % (digest_hex[:width // 2], digest_hex[-(width // 2):])


def find_digest(records, digest_hex):
    for r in records:
        if r.get('sha256') == digest_hex:
            return r
    return None


def note_file(records, name, digest_hex, size, seen=None):
    """Record a file. Re-witnessing the same bytes updates, never duplicates.

    A file seen under two names is one entry with both names: it is the bytes
    that are being witnessed, not the filename.
    """
    rec = find_digest(records, digest_hex)
    if rec is None:
        rec = {'sha256': digest_hex, 'size': int(size), 'names': []}
        records.append(rec)
    if name and name not in rec.setdefault('names', []):
        rec['names'].append(name)
    # No clock on this device: a date is recorded only when the owner confirmed one.
    if seen and not rec.get('seen'):
        rec['seen'] = seen
    return rec


def check_file(records, digest_hex):
    """-> ('match', rec) | ('changed', rec) | ('unknown', None)

    'changed' is the interesting one: a file whose name we have witnessed before
    but whose bytes are now different.
    """
    rec = find_digest(records, digest_hex)
    if rec:
        return ('match', rec)
    return ('unknown', None)


def check_name(records, name, digest_hex):
    "did a file by this name have different bytes last time?"
    for r in records:
        if name in r.get('names', []) and r.get('sha256') != digest_hex:
            return r
    return None


def describe(rec):
    names = rec.get('names') or ['(unnamed)']
    return '%s  %s' % (names[0], short(rec.get('sha256', '')))


# -------------------------------------------------------------------- app --

@register_app
class Witness(DQApp):
    name = NAME
    title = 'witness'
    hotkey = 'w'

    def home_line(self):
        records, status = self.load_for_home()
        if status:
            return status
        n = len(records)
        return ('%d files' % n if n != 1 else '1 file', False)

    async def start(self):
        from dq.ui import menu_choice, show_error
        pick = await menu_choice('witness', [
            ('witness a file', 'add'),
            ('check a file', 'check'),
            ('the log', 'log')])
        try:
            if pick == 'add':
                await self.do_add()
            elif pick == 'check':
                await self.do_check()
            elif pick == 'log':
                await self.do_log()
        except Exception as exc:
            await show_error('witness', exc)

    async def _hash_a_file(self):
        "-> (filename, digest hex, size) or (None, None, None)"
        from dq.ui import pick_file
        from files import CardSlot
        path = await pick_file('witness')
        if not path:
            return (None, None, None)

        from uhashlib import sha256
        size = 0
        h = sha256()
        with CardSlot() as card:
            with open(path, 'rb') as fd:
                while True:
                    part = fd.read(CHUNK)
                    if not part:
                        break
                    size += len(part)
                    h.update(part)          # streamed: never held whole in RAM
        name = path.split('/')[-1]
        return (name, hexed(h.digest()), size)

    async def do_add(self):
        from ux import ux_show_story
        from dq.session import ask_today
        name, digest_hex, size = await self._hash_a_file()
        if not name:
            return
        records = self.store().load()
        seen = await ask_today()
        rec = note_file(records, name, digest_hex, size, seen)
        self.store().save(records)
        await ux_show_story('Witnessed.\n\n%s\n%d bytes\n\nsha256\n%s'
                            % (name, size, digest_hex), title='witness')

    async def do_check(self):
        from ux import ux_show_story
        name, digest_hex, size = await self._hash_a_file()
        if not name:
            return
        records = self.store().load()
        verdict, rec = check_file(records, digest_hex)
        if verdict == 'match':
            await ux_show_story('These exact bytes are in the log.\n\nseen %s\nas %s'
                                % (rec.get('seen', 'date unknown'),
                                   ', '.join(rec.get('names', []))), title='match')
            return
        older = check_name(records, name, digest_hex)
        if older:
            await ux_show_story('CHANGED.\n\nA file called %s was witnessed with '
                                'different bytes.\n\nwas %s\nnow %s'
                                % (name, short(older['sha256']), short(digest_hex)),
                                title='changed')
        else:
            await ux_show_story('Not in the log.\n\n%s\n%s'
                                % (name, digest_hex), title='unknown')

    async def do_log(self):
        from dq.ui import pick_from_list
        records = self.store().load()
        await pick_from_list('witness', records,
                             line=lambda r: ((r.get('names') or ['?'])[0],
                                             r.get('seen', '')),
                             match=lambda recs, q: [
                                 r for r in recs
                                 if not q or any(q.lower() in n.lower()
                                                 for n in r.get('names', []))],
                             footer='X back')
