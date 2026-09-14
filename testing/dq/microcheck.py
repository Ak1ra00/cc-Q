import sys
sys.path.insert(0, '../shared')

fails = []
def check(name, fn):
    try:
        fn()
        print('  ok    ' + name)
    except Exception as e:
        print('  FAIL  %s: %r' % (name, e))
        fails.append(name)

# theme: palette maths and the in-place swap lcd_display depends on
def t_theme():
    from dq import theme
    pals = theme.palettes()
    assert len(pals) == 3 and all(len(p) == 32 for p in pals), 'palette shape'
    assert theme.rgb565(theme.PHOSPHOR, 255) != 0
    assert theme.pad('vault', '42 entries', 34).endswith('42 entries')
    assert len(theme.fit('x' * 50, 34)) == 34
check('theme palettes + layout', t_theme)

def t_palette_swap():
    from dq import theme
    from font_iosevka import TEXT_PALETTES
    before = bytes(TEXT_PALETTES[0])
    theme.apply()
    assert bytes(TEXT_PALETTES[0]) != before, 'apply() did not recolour'
check('palette swap recolours in place', t_palette_swap)

# store: real ngu.aes + ngu.hmac on this build
def t_store():
    from dq import store
    key = b'\x11' * 32
    recs = [{'id': 1, 'service': 'protonmail', 'extra': {'kept': True}}]
    blob = store.encode('vault', recs, key)
    back = store.decode('vault', blob, key)
    assert back == recs, back
    bad = bytearray(blob); bad[-40] ^= 1
    try:
        store.decode('vault', bytes(bad), key)
        raise AssertionError('tamper not caught')
    except store.BadMAC:
        pass
check('store roundtrip + MAC (real AES/HMAC)', t_store)

# otp: RFC vectors against the device's own hmac_sha1
def t_otp():
    from dq import otp
    s = b'12345678901234567890'
    assert otp.hotp(s, 0) == '755224', otp.hotp(s, 0)
    assert otp.hotp(s, 9) == '520489'
    assert otp.totp(s, 59, digits=8) == '94287082'
    assert otp.b32encode(otp.b32decode('JBSWY3DPEHPK3PXP')) == 'JBSWY3DPEHPK3PXP'
    r = otp.parse_uri('otpauth://totp/ACME:alice?secret=JBSWY3DPEHPK3PXP')
    assert r['secret'] == 'JBSWY3DPEHPK3PXP'
check('OTP RFC vectors (real hmac_sha1)', t_otp)

def t_dates():
    from dq import dates
    for d in ('1970-01-01', '2026-09-14', '2028-02-29', '2100-03-01'):
        assert dates.from_ordinal(dates.ordinal(d)) == d, d
check('calendar round-trip', t_dates)

def t_recovery():
    from dq.apps import recovery
    secret = bytes(range(32))
    sh = recovery.split(secret, 3)
    assert recovery.combine(sh) == secret
    try:
        recovery.combine(sh[:2]); raise AssertionError('short set accepted')
    except ValueError:
        pass
check('recovery split/combine (real TRNG)', t_recovery)

def t_vault():
    from dq.apps import vault
    key = b'\x22' * 32
    sealed = vault.seal_secret(key, 14, 'hunter2-but-longer')
    assert vault.open_secret(key, 14, sealed) == 'hunter2-but-longer'
    try:
        vault.open_secret(key, 15, sealed); raise AssertionError('wrong id accepted')
    except ValueError:
        pass
check('vault seal/open (real AES)', t_vault)

def t_sign():
    import ngu
    from dq.apps import sign
    priv = sign.identity_key(b'\x33' * 32, 0)
    d = sign.digest('hello there')
    sig = ngu.secp256k1.sign(priv, d, 0).to_bytes()
    pub = ngu.secp256k1.keypair(priv).pubkey().to_bytes()
    blob = sign.armor('hello there', sig, sign.fingerprint(pub))
    text, got, fp = sign.parse_armor(blob)
    assert text == 'hello there' and got == sig
    rec = ngu.secp256k1.signature(sig).verify_recover(d)
    assert sign.fingerprint(rec.to_bytes()) == fp, 'recovered key mismatch'
check('sign: real secp256k1 sign + recover', t_sign)

def t_witness():
    from dq.apps import witness
    import uhashlib
    data = b'a' * 3000
    chunks = [data[i:i+1024] for i in range(0, len(data), 1024)]
    assert witness.hexed(witness.hash_chunks(chunks)) == \
           witness.hexed(uhashlib.sha256(data).digest())
check('witness streaming sha256', t_witness)

def t_registry():
    import dq.apps.vault, dq.apps.codes, dq.apps.journal
    import dq.apps.recovery, dq.apps.sign, dq.apps.witness, dq.apps.keypad
    from dq.apps import APPS, find
    assert len(APPS) == 7, len(APPS)
    keys = [a.hotkey for a in APPS]
    assert len(set(keys)) == 7, keys
    assert find('v').name == 'vault'
check('all 7 apps register under MicroPython', t_registry)

print('')
print('RESULT: %d failed' % len(fails))
