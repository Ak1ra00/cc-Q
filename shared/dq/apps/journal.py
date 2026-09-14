# (c) 2026 cc-Q. One encrypted entry per day, written on the Q's own keyboard.
#
# The Q has no clock, so the date is never assumed: the owner confirms it on the
# first write of each session and everything keys off that.
#
from dq.apps import DQApp, register_app

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


def _ordinal(date):
    """Days since 1970-01-01 for YYYY-MM-DD. No datetime on the device.

    Howard Hinnant's days_from_civil: exact for every proleptic Gregorian date,
    which matters because the owner can set any date they like.
    """
    y, m, d = (int(x) for x in date.split('-'))
    y -= 1 if m <= 2 else 0
    era = (y if y >= 0 else y - 399) // 400
    yoe = y - era * 400
    doy = (153 * (m + (-3 if m > 2 else 9)) + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


def _from_ordinal(z):
    "the exact inverse of _ordinal"
    z += 719468
    era = (z if z >= 0 else z - 146096) // 146097
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    y = yoe + era * 400
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    d = doy - (153 * mp + 2) // 5 + 1
    m = mp + 3 if mp < 10 else mp - 9
    return '%04d-%02d-%02d' % (y + (1 if m <= 2 else 0), m, d)


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
