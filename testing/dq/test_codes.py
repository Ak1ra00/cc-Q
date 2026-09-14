# The codes screen's behaviour when the clock is unknown, which on this device
# is after every single power cycle.
import pytest

TOTP = 'otpauth://totp/ACME:alice?secret=JBSWY3DPEHPK3PXP&issuer=ACME'
HOTP = 'otpauth://hotp/bank?secret=JBSWY3DPEHPK3PXP&counter=3'


def test_rows_grey_totp_without_time(settings):
    from dq import otp
    from dq.apps import codes
    recs = [otp.parse_uri(TOTP)]
    (label, code, frac), = codes.rows(recs, None)
    assert code is None, 'never invent digits when time is unknown'
    assert frac == 0.0


def test_rows_show_hotp_without_time(settings):
    "HOTP is the fallback precisely because it needs no clock"
    from dq import otp
    from dq.apps import codes
    (label, code, frac), = codes.rows([otp.parse_uri(HOTP)], None)
    assert code and code.replace(' ', '').isdigit()


def test_rows_with_time(settings):
    from dq import otp
    from dq.apps import codes
    (label, code, frac), = codes.rows([otp.parse_uri(TOTP)], 1_700_000_000)
    assert code.replace(' ', '').isdigit()
    assert 0 < frac <= 1.0


def test_code_is_spaced_for_reading(settings):
    from dq import otp
    from dq.apps import codes
    (_, code, _), = codes.rows([otp.parse_uri(TOTP)], 1_700_000_000)
    assert ' ' in code and len(code) == 7


def test_three_at_a_time(settings):
    from dq import otp
    from dq.apps import codes
    recs = [otp.parse_uri(TOTP) for _ in range(5)]
    assert len(codes.rows(recs, 1_700_000_000)) == codes.VISIBLE == 3


def test_needs_clock(settings):
    from dq import otp
    from dq.apps import codes
    assert codes.needs_clock([otp.parse_uri(TOTP)])
    assert not codes.needs_clock([otp.parse_uri(HOTP)])


def test_hotp_counter_advances(settings):
    from dq import otp
    from dq.apps import codes
    rec = otp.parse_uri(HOTP)
    codes.bump_counter([rec], rec)
    assert rec['counter'] == 4


def test_a_broken_record_does_not_take_the_screen_down(settings):
    from dq.apps import codes
    (label, code, frac), = codes.rows([{'kind': 'totp', 'secret': 'not-base32!'}], 1)
    assert code is None


def test_parse_time_qr(settings):
    from dq.apps import codes
    assert codes.parse_time_qr('1700000000') == 1_700_000_000
    assert codes.parse_time_qr(' time=1700000000 ') == 1_700_000_000
    assert codes.parse_time_qr('t=1700000000') == 1_700_000_000
    for bad in ('', 'hello', 'otpauth://totp/x'):
        with pytest.raises(ValueError):
            codes.parse_time_qr(bad)
