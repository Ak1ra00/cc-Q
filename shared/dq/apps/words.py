# (c) 2026 cc-Q. Guess the word in six tries.
#
# The dictionary is the BIP-39 wordlist, which is already in flash for seed
# handling: 555 five-letter words, costing nothing to reuse. That also makes the
# game quietly useful -- the words you learn to recognise here are the words on
# your paper backup.
#
# No clock is involved, which is why a game is possible on this device at all.
#
from dq.apps import DQApp, register_app

NAME = 'words'
LEN = 5
TRIES = 6
SETTING_STATS = 'dq_words'      # in settings, not on a card: a game should not
                                # demand a microSD to be playable

HIT, NEAR, MISS = 2, 1, 0       # right place / in the word / not in it


# ------------------------------------------------------------- pure logic --

def dictionary():
    "the five-letter BIP-39 words, in list order"
    from bip39 import wordlist_en
    return [w for w in wordlist_en if len(w) == LEN]


def pick(rng=None):
    "a word from the hardware TRNG unless one is handed in (tests do)"
    words = dictionary()
    if rng is None:
        import ngu
        rng = ngu.random.uniform
    return words[rng(len(words))]


def allowed(word, words=None):
    return (word or '').lower() in (words if words is not None else dictionary())


def score(guess, answer):
    """Per-letter HIT / NEAR / MISS, counting duplicates the way people expect.

    Two passes: exact matches are taken first and removed from the pool, so a
    second 'e' in the guess is only NEAR if the answer still has a spare 'e'.
    Getting this wrong is the classic bug in every clone of this game.
    """
    guess, answer = guess.lower(), answer.lower()
    if len(guess) != len(answer):
        raise ValueError('lengths differ')

    out = [MISS] * len(guess)
    pool = {}
    for i, ch in enumerate(answer):
        if guess[i] == ch:
            out[i] = HIT
        else:
            pool[ch] = pool.get(ch, 0) + 1

    for i, ch in enumerate(guess):
        if out[i] == HIT:
            continue
        if pool.get(ch, 0):
            out[i] = NEAR
            pool[ch] -= 1
    return out


def won(marks):
    return all(m == HIT for m in marks)


def keyboard_state(guesses, answer):
    "best-known state per letter, for the little alphabet hint line"
    known = {}
    for g in guesses:
        for ch, m in zip(g.lower(), score(g, answer)):
            if m > known.get(ch, -1):
                known[ch] = m
    return known


def load_stats():
    try:
        from glob import settings
        got = settings.get(SETTING_STATS) or {}
    except ImportError:
        got = {}
    return {'played': got.get('played', 0), 'won': got.get('won', 0),
            'streak': got.get('streak', 0), 'best': got.get('best', 0)}


def record(stats, did_win):
    stats['played'] += 1
    if did_win:
        stats['won'] += 1
        stats['streak'] += 1
        stats['best'] = max(stats['best'], stats['streak'])
    else:
        stats['streak'] = 0
    try:
        from glob import settings
        settings.put(SETTING_STATS, stats)
        settings.save()
    except ImportError:
        pass
    return stats


# -------------------------------------------------------------------- app --

@register_app
class Words(DQApp):
    name = NAME
    title = 'words'
    hotkey = 'g'

    def home_line(self):
        s = load_stats()
        if not s['played']:
            return ('never played', False)
        return ('%d/%d, streak %d' % (s['won'], s['played'], s['streak']), False)

    async def start(self):
        from dq import ui
        while True:
            again = await self.play()
            if not again:
                return

    async def play(self):
        "one game. Returns True if they want another."
        from glob import dis
        from dq import theme, ui
        from charcodes import KEY_ENTER, KEY_DELETE

        answer = pick()
        words = dictionary()
        guesses = []
        typing = ''
        note = 'guess a word'

        while True:
            dis.clear()
            theme.header(dis, 'words', '%d left' % (TRIES - len(guesses)))

            for row in range(TRIES):
                y = theme.BODY_TOP + row
                if row < len(guesses):
                    self._draw_scored(dis, y, guesses[row], answer)
                elif row == len(guesses):
                    dis.text(2, y, ' '.join(typing.upper()))
                    dis.text(2 + (len(typing) * 2), y, '_')

            theme.body(dis, 6, note, x=2, dark=True)
            theme.footer(dis, 'type a word', 'X give up')
            dis.show()

            ch = await ui._key()
            if ch in ui.BACK_KEYS:
                if not typing:
                    return await self.finish(answer, False, guesses)
                typing = typing[:-1]
            elif ch == KEY_DELETE:
                typing = typing[:-1]
            elif ch == KEY_ENTER:
                if len(typing) != LEN:
                    note = 'needs %d letters' % LEN
                elif not allowed(typing, words):
                    note = 'not a BIP-39 word'
                else:
                    guesses.append(typing.lower())
                    marks = score(typing, answer)
                    typing, note = '', ''
                    if won(marks):
                        return await self.finish(answer, True, guesses)
                    if len(guesses) >= TRIES:
                        return await self.finish(answer, False, guesses)
            elif ch and ch.isalpha() and len(typing) < LEN:
                typing += ch.lower()
                note = ''

    def _draw_scored(self, dis, y, guess, answer):
        """One guessed row. The three palettes the hardware has map exactly onto
        the three states: reverse video for a hit, normal for near, dim for a
        miss."""
        for i, ch in enumerate(guess.upper()):
            mark = score(guess, answer)[i]
            dis.text(2 + (i * 2), y, ch,
                     invert=(mark == HIT), dark=(mark == MISS))

    async def finish(self, answer, did_win, guesses):
        from ux import ux_show_story
        stats = record(load_stats(), did_win)
        head = 'Got it in %d.' % len(guesses) if did_win else 'The word was %s.' % answer
        ch = await ux_show_story(
            '%s\n\nPlayed %d, won %d. Streak %d, best %d.\n\n'
            'Press OK for another, X to stop.'
            % (head, stats['played'], stats['won'], stats['streak'], stats['best']),
            title='words')
        return ch == 'y'
