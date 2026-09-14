# (c) 2026 cc-Q. HOTP (RFC 4226) and TOTP (RFC 6238), and the otpauth:// URI
# that services put in their enrolment QR.
#
# HOTP needs no clock and is the fallback whenever time is unknown, which on this
# device is after every power cycle.
#
import ngu

B32 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567'


def b32decode(txt):
    "RFC 4648 base32, case-insensitive, padding optional -- as services write it"
    txt = txt.strip().replace(' ', '').replace('-', '').upper().rstrip('=')
    acc = bits = 0
    out = bytearray()
    for ch in txt:
        idx = B32.find(ch)
        if idx < 0:
            raise ValueError('bad base32: %r' % ch)
        acc = (acc << 5) | idx
        bits += 5
        if bits >= 8:
            bits -= 8
            out.append((acc >> bits) & 0xff)
    return bytes(out)


def b32encode(raw):
    "RFC 4648 base32 without padding; the inverse of b32decode"
    acc = bits = 0
    out = ''
    for byte in raw:
        acc = (acc << 8) | byte
        bits += 8
        while bits >= 5:
            bits -= 5
            out += B32[(acc >> bits) & 0x1f]
    if bits:
        out += B32[(acc << (5 - bits)) & 0x1f]
    return out


def hotp(secret, counter, digits=6, algo='SHA1'):
    "RFC 4226. secret is raw bytes."
    msg = counter.to_bytes(8, 'big')
    if algo == 'SHA1':
        mac = ngu.hmac.hmac_sha1(secret, msg)
    elif algo == 'SHA256':
        mac = ngu.hmac.hmac_sha256(secret, msg)
    elif algo == 'SHA512':
        mac = ngu.hmac.hmac_sha512(secret, msg)
    else:
        raise ValueError(algo)

    off = mac[-1] & 0x0f
    code = ((mac[off] & 0x7f) << 24 | (mac[off + 1] & 0xff) << 16 |
            (mac[off + 2] & 0xff) << 8 | (mac[off + 3] & 0xff))
    # no str.rjust in MicroPython, and this runs for every code shown
    return ('%0' + str(digits) + 'd') % (code % (10 ** digits))


def totp(secret, unix_time, period=30, digits=6, algo='SHA1'):
    "RFC 6238. Raises if unix_time is None -- callers must handle unknown time."
    if unix_time is None:
        raise ValueError('time is not known')
    return hotp(secret, int(unix_time) // period, digits, algo)


def seconds_left(unix_time, period=30):
    return period - (int(unix_time) % period)


def parse_uri(uri):
    """otpauth://totp/Issuer:account?secret=...&issuer=...&digits=6&period=30

    Returns a record ready for the store. Unknown query parameters are kept, so a
    service that adds one does not lose it on the next write.
    """
    if not uri.startswith('otpauth://'):
        raise ValueError('not an otpauth URI')

    rest = uri[10:]
    kind, _, rest = rest.partition('/')
    kind = kind.lower()
    if kind not in ('totp', 'hotp'):
        raise ValueError('unknown OTP type: %s' % kind)

    label, _, query = rest.partition('?')
    label = unquote(label)
    issuer, _, account = label.partition(':')
    if not account:
        issuer, account = '', issuer

    args = {}
    for pair in query.split('&'):
        if not pair:
            continue
        k, _, v = pair.partition('=')
        args[k.lower()] = unquote(v)

    if 'secret' not in args:
        raise ValueError('no secret in URI')
    b32decode(args['secret'])            # validate now, not at first use

    rec = {
        'kind': kind,
        'issuer': args.get('issuer') or issuer.strip(),
        'account': account.strip(),
        'secret': args['secret'].upper().rstrip('='),
        'digits': int(args.get('digits', 6)),
        'algo': args.get('algorithm', 'SHA1').upper(),
    }
    if kind == 'totp':
        rec['period'] = int(args.get('period', 30))
    else:
        rec['counter'] = int(args.get('counter', 0))

    extra = {k: v for k, v in args.items()
             if k not in ('secret', 'issuer', 'digits', 'algorithm', 'period', 'counter')}
    if extra:
        rec['extra'] = extra
    return rec


def label(rec):
    "what the codes list shows on the left, inside 34 columns"
    name = rec.get('issuer') or rec.get('account') or 'unnamed'
    who = rec.get('account')
    if who and rec.get('issuer') and who != rec['issuer']:
        name = '%s (%s)' % (name, who)
    return name


def code_for(rec, unix_time=None):
    "current code for a record, or None when a TOTP has no time to work from"
    secret = b32decode(rec['secret'])
    digits, algo = int(rec.get('digits', 6)), rec.get('algo', 'SHA1')
    if rec.get('kind') == 'hotp':
        return hotp(secret, int(rec.get('counter', 0)), digits, algo)
    if unix_time is None:
        return None
    return totp(secret, unix_time, int(rec.get('period', 30)), digits, algo)


def unquote(s):
    "percent-decoding, and + for space; MicroPython has no urllib"
    out = bytearray()
    i = 0
    while i < len(s):
        c = s[i]
        if c == '%' and i + 2 < len(s):
            try:
                out.append(int(s[i + 1:i + 3], 16))
                i += 3
                continue
            except ValueError:
                pass
        out.extend(b' ' if c == '+' else c.encode())
        i += 1
    return bytes(out).decode()
