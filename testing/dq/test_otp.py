# HOTP and TOTP against the RFC vectors, plus the otpauth:// URIs services hand out.
import pytest

RFC4226_SECRET = b'12345678901234567890'          # RFC 4226, appendix D
RFC4226 = ['755224', '287082', '359152', '969429', '338314',
           '254676', '287922', '162583', '399871', '520489']


def test_hotp_rfc4226_vectors(settings):
    from dq import otp
    for counter, expect in enumerate(RFC4226):
        assert otp.hotp(RFC4226_SECRET, counter) == expect


def test_totp_rfc6238_vectors(settings):
    "RFC 6238 appendix B, the SHA-1 rows"
    from dq import otp
    secret = b'12345678901234567890'
    for when, expect in [(59, '94287082'), (1111111109, '07081804'),
                         (1111111111, '14050471'), (1234567890, '89005924'),
                         (2000000000, '69279037'), (20000000000, '65353130')]:
        assert otp.totp(secret, when, digits=8) == expect


def test_totp_sha256_vector(settings):
    from dq import otp
    secret = b'12345678901234567890123456789012'
    assert otp.totp(secret, 59, digits=8, algo='SHA256') == '46119246'


def test_totp_refuses_unknown_time(settings):
    "the whole point: never invent a code when the clock is unset"
    from dq import otp
    with pytest.raises(ValueError):
        otp.totp(b'x' * 10, None)


def test_seconds_left(settings):
    from dq import otp
    assert otp.seconds_left(0) == 30
    assert otp.seconds_left(29) == 1
    assert otp.seconds_left(30) == 30


def test_base32_tolerates_how_people_paste_it(settings):
    from dq import otp
    want = otp.b32decode('JBSWY3DPEHPK3PXP')
    for variant in ['jbswy3dpehpk3pxp', 'JBSW Y3DP EHPK 3PXP',
                    'JBSW-Y3DP-EHPK-3PXP', 'JBSWY3DPEHPK3PXP====']:
        assert otp.b32decode(variant) == want


def test_parse_uri(settings):
    from dq import otp
    rec = otp.parse_uri('otpauth://totp/ACME%20Co:alice%40example.com'
                        '?secret=JBSWY3DPEHPK3PXP&issuer=ACME%20Co&digits=6&period=30')
    assert rec['kind'] == 'totp'
    assert rec['issuer'] == 'ACME Co'
    assert rec['account'] == 'alice@example.com'
    assert rec['secret'] == 'JBSWY3DPEHPK3PXP'
    assert rec['period'] == 30


def test_parse_uri_keeps_unknown_params(settings):
    from dq import otp
    rec = otp.parse_uri('otpauth://totp/x?secret=JBSWY3DPEHPK3PXP&image=https://a/b.png')
    assert rec['extra']['image'] == 'https://a/b.png'


def test_parse_uri_hotp_counter(settings):
    from dq import otp
    rec = otp.parse_uri('otpauth://hotp/bank?secret=JBSWY3DPEHPK3PXP&counter=7')
    assert rec['kind'] == 'hotp' and rec['counter'] == 7


def test_parse_uri_rejects_junk(settings):
    from dq import otp
    for bad in ['https://example.com', 'otpauth://xotp/a?secret=JBSWY3DPEHPK3PXP',
                'otpauth://totp/a?issuer=nope', 'otpauth://totp/a?secret=not!base32']:
        with pytest.raises(ValueError):
            otp.parse_uri(bad)


def test_code_for_hotp_needs_no_clock(settings):
    "HOTP is the fallback precisely because it works with time unknown"
    from dq import otp
    rec = otp.parse_uri('otpauth://hotp/bank?secret=GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ&counter=0')
    assert otp.code_for(rec, None) == '755224'


def test_code_for_totp_returns_none_without_time(settings):
    from dq import otp
    rec = otp.parse_uri('otpauth://totp/x?secret=JBSWY3DPEHPK3PXP')
    assert otp.code_for(rec, None) is None
