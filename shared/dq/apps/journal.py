# (c) 2026 cc-Q. One encrypted entry per day, written on the Q's own keyboard.
#
# The Q has no clock, so the date is never assumed: the owner confirms it on the
# first write of each session and everything keys off that.
#
from dq.apps import DQApp, register_app
from dq.dates import ordinal as _ordinal, from_ordinal as _from_ordinal

NAME = 'journal'
VISIBLE_LINES = 5


# ------------------------------------------------------------- pure logic --

def word_count(text):
    return len((text or '').split())


def find_day(records, date):
    for r in records:
        if r.get('date') == date:
            return r
    return None


def put_day(records, date, text):
    """Write one day, preserving every other field on an existing record.

    Mutates and returns the list, so unknown fields a later version added are
    carried through untouched (CLAUDE.md invariant 5).
    """
    rec = find_day(records, date)
    if rec is None:
        rec = {'date': date}
        records.append(rec)
    rec['text'] = text
    rec['words'] = word_count(text)
    return records


def days_written(records):
    return sorted(r['date'] for r in records
                  if r.get('date') and word_count(r.get('text', '')))


def week(records, today, days=7):
    """The week view: (date, words, is_today) oldest first.

    Unwritten days are present with a zero count -- the screen draws them as
    outlines, and says nothing else about them.
    """
    end = _ordinal(today)
    out = []
    for n in range(days - 1, -1, -1):
        date = _from_ordinal(end - n)
        rec = find_day(records, date)
        out.append((date, word_count(rec.get('text', '')) if rec else 0, date == today))
    return out


def longest_run(records):
    "consecutive days written; plain fact, no streak pressure attached"
    days = [_ordinal(d) for d in days_written(records)]
    best = run = 0
    prev = None
    for d in days:
        run = run + 1 if prev is not None and d == prev + 1 else 1
        best = max(best, run)
        prev = d
    return best


# -------------------------------------------------------------------- app --

@register_app
class Journal(DQApp):
    name = NAME
    title = 'journal'
    hotkey = 'j'

    def home_line(self):
        from dq.session import today_or_none
        today = today_or_none()
        if today is None:
            return ('date unknown', False)
        try:
            rec = find_day(self.store().load(), today)
        except Exception:
            return ('unreadable', True)
        if rec and word_count(rec.get('text', '')):
            return ('%d words' % word_count(rec['text']), False)
        return ('not written', True)

    async def start(self):
        from dq.session import ask_today
        from dq.ui import edit_text, show_error
        today = await ask_today()
        if today is None:
            return
        try:
            records = self.store().load()
        except Exception as exc:
            await show_error('journal', exc)
            return

        rec = find_day(records, today)
        text = await edit_text('journal  %s' % today, (rec or {}).get('text', ''),
                               lines=VISIBLE_LINES)
        if text is None:
            return
        put_day(records, today, text)
        try:
            self.store().save(records)
        except Exception as exc:
            await show_error('journal', exc)
