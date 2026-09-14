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
        records, status = self.load_for_home()
        if status:
            return status
        rec = find_day(records, today)
        if rec and word_count(rec.get('text', '')):
            return ('%d words' % word_count(rec['text']), False)
        return ('not written', True)

    async def start(self):
        from dq import ui
        try:
            records = self.store().load()
        except Exception as exc:
            await ui.show_error('journal', exc)
            return

        while True:
            pick = await ui.menu_choice('journal', [
                ("write today's entry", 'write'),
                ('the week', 'week'),
                ('export', 'export'),
                ('import an export', 'import')])
            if pick is None:
                return
            try:
                if pick == 'write':
                    await self.write(records)
                elif pick == 'week':
                    await self.show_week(records)
                elif pick == 'export':
                    await ui.export_records('journal', records, 'journal')
                elif pick == 'import':
                    records, changed = await ui.import_records('journal', records, 'date')
                    if changed:
                        self.store().save(records)
            except Exception as exc:
                await ui.show_error('journal', exc)

    async def write(self, records):
        from dq.session import ask_today
        from dq.ui import edit_text
        today = await ask_today()
        if today is None:
            return
        rec = find_day(records, today)
        text = await edit_text('journal  %s' % today, (rec or {}).get('text', ''),
                               lines=VISIBLE_LINES)
        if text is None:
            return
        put_day(records, today, text)
        self.store().save(records)

    async def show_week(self, records):
        from glob import dis
        from dq import theme
        from dq.session import today_or_none
        from dq.ui import _key, BACK_KEYS

        today = today_or_none()
        if today is None:
            from ux import ux_show_story
            await ux_show_story('The week view needs to know what day it is.\n\n'
                                'Write an entry first and confirm the date.',
                                title='week')
            return

        days = week(records, today)
        biggest = max([w for _, w, _ in days] + [1])
        dis.clear()
        theme.header(dis, 'journal  week', '%d days' % len(days_written(records)))
        for n, (date, words, is_today) in enumerate(days):
            bar = '\u2588' * max(0, (words * 18) // biggest)
            label = date[-2:] + (' <' if is_today else '  ')
            theme.body(dis, n, '%s %s' % (label, bar), x=1, dark=not is_today)
        theme.footer(dis, 'longest run %d days' % longest_run(records), 'X back')
        dis.show()
        while True:
            if await _key() in BACK_KEYS:
                return
