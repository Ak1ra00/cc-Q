# Journal record logic, including the week view's deliberate lack of nagging.
import pytest


def test_word_count(settings):
    from dq.apps import journal
    assert journal.word_count('') == 0
    assert journal.word_count('   ') == 0
    assert journal.word_count('one two  three\nfour') == 4


def test_one_record_per_day(settings):
    from dq.apps import journal
    recs = []
    journal.put_day(recs, '2026-09-14', 'first')
    journal.put_day(recs, '2026-09-14', 'first, edited')
    assert len(recs) == 1
    assert recs[0]['text'] == 'first, edited'
    assert recs[0]['words'] == 2


def test_editing_a_day_keeps_unknown_fields(settings):
    from dq.apps import journal
    recs = [{'date': '2026-09-14', 'text': 'old', 'words': 1, 'mood': 'fine'}]
    journal.put_day(recs, '2026-09-14', 'new text here')
    assert recs[0]['mood'] == 'fine'
    assert recs[0]['text'] == 'new text here'


def test_week_shows_unwritten_days_as_zero(settings):
    from dq.apps import journal
    recs = [{'date': '2026-09-14', 'text': 'a b c'},
            {'date': '2026-09-12', 'text': 'one'}]
    wk = journal.week(recs, '2026-09-14')
    assert len(wk) == 7
    assert wk[-1] == ('2026-09-14', 3, True)
    assert wk[-3] == ('2026-09-12', 1, False)
    assert wk[0][1] == 0 and wk[0][2] is False


def test_week_crosses_a_month_boundary(settings):
    from dq.apps import journal
    wk = journal.week([], '2026-03-02')
    assert wk[0][0] == '2026-02-24' and wk[-1][0] == '2026-03-02'


def test_week_crosses_a_leap_day(settings):
    from dq.apps import journal
    wk = journal.week([], '2028-03-01')
    assert '2028-02-29' in [d for d, _, _ in wk]


def test_longest_run(settings):
    from dq.apps import journal
    recs = [{'date': d, 'text': 'x'} for d in
            ('2026-09-01', '2026-09-02', '2026-09-03', '2026-09-08', '2026-09-09')]
    assert journal.longest_run(recs) == 3


def test_empty_days_do_not_count_as_written(settings):
    from dq.apps import journal
    recs = [{'date': '2026-09-01', 'text': ''}, {'date': '2026-09-02', 'text': '  '}]
    assert journal.days_written(recs) == []
    assert journal.longest_run(recs) == 0


def test_date_round_trip(settings):
    from dq.apps import journal
    for date in ('1970-01-01', '2026-09-14', '2028-02-29', '2100-03-01', '1999-12-31'):
        assert journal._from_ordinal(journal._ordinal(date)) == date
