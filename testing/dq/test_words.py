# The word game. Duplicate-letter scoring is the classic bug in every clone of
# this, so it gets most of the attention here.
import pytest

WORDS = ['crane', 'sleep', 'abbey', 'eerie', 'llama', 'array']


def test_dictionary_is_the_five_letter_words(settings):
    """Shape only. That the real list holds 555 of them is checked on the
    device, in microcheck.py, where the real bip39 module exists."""
    from dq.apps import words
    d = words.dictionary()
    assert all(len(w) == 5 for w in d)
    assert 'crane' in d and 'alarm' in d
    assert 'abandon' not in d and 'acid' not in d


def test_all_hits(settings):
    from dq.apps import words
    assert words.score('crane', 'crane') == [words.HIT] * 5
    assert words.won(words.score('crane', 'crane'))


def test_all_misses(settings):
    from dq.apps import words
    assert words.score('sleep', 'about') == [words.MISS] * 5


def test_near_vs_hit(settings):
    from dq.apps import words
    H, N, M = words.HIT, words.NEAR, words.MISS
    # answer 'eagle', guess 'sleep': l, e, e are all present, none in place
    assert words.score('sleep', 'eagle') == [M, N, N, N, M]


def test_two_of_a_letter_in_the_guess_one_in_the_answer(settings):
    """'about' has a single 'a'. 'alarm' offers two. Only one may be marked, and
    it must be the one in the right place."""
    from dq.apps import words
    H, N, M = words.HIT, words.NEAR, words.MISS
    assert words.score('alarm', 'about') == [H, M, M, M, M]


def test_two_of_a_letter_in_both(settings):
    """'eagle' has two 'e's, 'agree' has two. One is exact, so the other is NEAR
    -- the case a single-pass implementation gets wrong."""
    from dq.apps import words
    H, N, M = words.HIT, words.NEAR, words.MISS
    assert words.score('agree', 'eagle') == [N, N, M, N, H]


def test_a_word_against_itself_is_all_hits(settings):
    from dq.apps import words
    assert words.score('alley', 'alley') == [words.HIT] * 5


def test_only_one_a_is_marked_when_the_answer_has_one(settings):
    from dq.apps import words
    H, N, M = words.HIT, words.NEAR, words.MISS
    # 'crane' has a single 'a', in position 2. 'alarm' offers two.
    marks = words.score('alarm', 'crane')
    assert marks[2] == H, 'the one in the right place takes it'
    assert marks[0] == M, 'the spare must not also be marked'
    assert [marks[i] for i in (0, 2)].count(H) + [marks[i] for i in (0, 2)].count(N) == 1


def test_score_rejects_length_mismatch(settings):
    from dq.apps import words
    with pytest.raises(ValueError):
        words.score('four', 'crane')


def test_allowed_only_accepts_the_wordlist(settings):
    from dq.apps import words
    d = words.dictionary()
    assert words.allowed('crane', d)
    assert words.allowed('CRANE', d), 'case should not matter'
    assert not words.allowed('zzzzz', d)


def test_pick_is_from_the_list(settings):
    from dq.apps import words
    d = words.dictionary()
    assert words.pick(rng=lambda n: 0) == d[0]
    assert words.pick(rng=lambda n: n - 1) == d[-1]
    assert words.pick() in d, 'the TRNG path must stay in range'


def test_keyboard_state_keeps_the_best_news(settings):
    from dq.apps import words
    H, N, M = words.HIT, words.NEAR, words.MISS
    state = words.keyboard_state(['sleep', 'eagle'], 'eagle')
    assert state['e'] == H and state['a'] == H
    assert state['s'] == M and state['p'] == M
    assert state['l'] == H, 'a later exact match must beat an earlier NEAR' 


def test_stats_record_a_win(settings):
    from dq.apps import words
    s = words.record(words.load_stats(), True)
    assert (s['played'], s['won'], s['streak'], s['best']) == (1, 1, 1, 1)
    s = words.record(s, True)
    assert (s['won'], s['streak'], s['best']) == (2, 2, 2)


def test_a_loss_breaks_the_streak_but_keeps_the_best(settings):
    from dq.apps import words
    s = words.load_stats()
    s = words.record(s, True)
    s = words.record(s, True)
    s = words.record(s, False)
    assert (s['played'], s['won'], s['streak'], s['best']) == (3, 2, 0, 2)


def test_stats_survive_the_settings_blob(settings):
    from dq.apps import words
    words.record(words.load_stats(), True)
    settings.save()                     # JSON round-trip, as the real one does
    assert words.load_stats()['played'] == 1
