# (c) 2026 cc-Q. Snippets you retype constantly, typed for you over USB.
#
# Not passwords -- those live in the vault, and this app has no way to reach them.
# This is for the text you type into forms over and over: an address, a licence
# key, a wifi passphrase, an account number.
#
from dq.apps import DQApp, register_app

NAME = 'keypad'
MAX_LEN = 400


# ------------------------------------------------------------- pure logic --

def new_snippet(records, label, text, press_enter=False):
    from dq.hid import untypable
    label = (label or '').strip()
    text = text or ''
    if not label:
        raise ValueError('needs a label')
    if not text:
        raise ValueError('nothing to type')
    if len(text) > MAX_LEN:
        raise ValueError('too long to type (%d > %d)' % (len(text), MAX_LEN))
    bad = untypable(text)
    if bad:
        raise ValueError('cannot type: %s' % ' '.join(repr(c) for c in bad))
    rec = {'label': label, 'text': text}
    if press_enter:
        rec['enter'] = True
    records.append(rec)
    return rec


def search(records, query):
    q = (query or '').strip().lower()
    if not q:
        return list(records)
    return [r for r in records if q in str(r.get('label', '')).lower()]


def preview(rec, width=20):
    "what the list shows on the right: enough to recognise, never the whole thing"
    text = rec.get('text', '')
    if len(text) <= width:
        return text
    return text[:width - 1] + '⋯'


# -------------------------------------------------------------------- app --

@register_app
class Keypad(DQApp):
    name = NAME
    title = 'keypad'
    hotkey = 'k'

    def home_line(self):
        from dq.hid import enabled
        records, status = self.load_for_home()
        if status:
            return status
        n = len(records)
        if n and not enabled():
            return ('%d, USB kbd off' % n, True)
        return ('%d snippets' % n if n != 1 else '1 snippet', False)

    async def start(self):
        from dq.ui import pick_from_list, show_error
        from dq import hid
        try:
            records = self.store().load()
        except Exception as exc:
            await show_error('keypad', exc)
            return

        while True:
            chosen = await pick_from_list(
                'keypad', records,
                line=lambda r: (r.get('label', '?'), preview(r, 12)),
                match=search,
                footer='OK type   X back')
            if chosen is None:
                return
            try:
                await hid.send(chosen.get('text', ''),
                               press_enter=bool(chosen.get('enter')),
                               label=chosen.get('label'))
            except Exception as exc:
                await show_error('keypad', exc)
