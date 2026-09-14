# Run cc-Q's logic under CPython by standing in for the MicroPython modules it
# imports. The shims use the same primitives the device does (SHA-256, HMAC,
# AES-256-CTR), so a vector that passes here passes on hardware.
#
import sys, os, types, json, hashlib, hmac as _hmac, secrets
import pytest

TOP = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(TOP, 'shared'))


def _make_ngu():
    ngu = types.ModuleType('ngu')

    hash_mod = types.ModuleType('ngu.hash')
    hash_mod.sha256s = lambda b: hashlib.sha256(b).digest()
    hash_mod.sha256d = lambda b: hashlib.sha256(hashlib.sha256(b).digest()).digest()

    hmac_mod = types.ModuleType('ngu.hmac')
    hmac_mod.hmac_sha1 = lambda k, m: _hmac.new(k, m, hashlib.sha1).digest()
    hmac_mod.hmac_sha256 = lambda k, m: _hmac.new(k, m, hashlib.sha256).digest()
    hmac_mod.hmac_sha512 = lambda k, m: _hmac.new(k, m, hashlib.sha512).digest()

    rnd = types.ModuleType('ngu.random')
    rnd.bytes = lambda n: secrets.token_bytes(n)
    rnd.uniform = lambda n: secrets.randbelow(n)

    class _CTR:
        # AES-256-CTR, the same construction as the device's aes256ctr module
        def __init__(self, key, iv):
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            assert len(key) == 32 and len(iv) == 16
            self._c = Cipher(algorithms.AES(key), modes.CTR(iv)).encryptor()

        def cipher(self, data):
            return self._c.update(bytes(data))

    aes = types.ModuleType('ngu.aes')
    aes.CTR = _CTR

    ngu.hash, ngu.hmac, ngu.random, ngu.aes = hash_mod, hmac_mod, rnd, aes
    return ngu


def _fake_utime():
    import time as _t
    m = types.ModuleType('utime')
    m.ticks_ms = lambda: int(_t.monotonic() * 1000)
    m.ticks_diff = lambda a, b: a - b
    return m


class FakeSettings:
    "enough of nvstore.SettingsObject for our code: get / put / save"
    def __init__(self):
        self.current = {}
        self.saves = 0

    def get(self, kn, default=None):
        return self.current.get(kn, default)

    def put(self, kn, v):
        self.current[kn] = v

    set = put

    def save(self):
        self.saves += 1
        # round-trip through JSON: the real settings blob is JSON, so anything
        # we store has to survive that
        self.current = json.loads(json.dumps(self.current))

    def remove_key(self, kn):
        self.current.pop(kn, None)


@pytest.fixture(autouse=True)
def micropython(monkeypatch):
    "install the shims before any cc-Q module is imported"
    for name in list(sys.modules):
        if name == 'dq' or name.startswith('dq.'):
            del sys.modules[name]

    sys.modules['ngu'] = _make_ngu()
    sys.modules['ujson'] = json
    sys.modules['ustruct'] = __import__('struct')
    sys.modules['ubinascii'] = __import__('binascii')
    sys.modules['utime'] = _fake_utime()

    glob = types.ModuleType('glob')
    glob.settings = FakeSettings()
    glob.dis = None
    sys.modules['glob'] = glob

    yield glob

    for name in ('ngu', 'ujson', 'ustruct', 'ubinascii', 'utime', 'glob'):
        sys.modules.pop(name, None)


@pytest.fixture
def settings(micropython):
    return micropython.settings


@pytest.fixture
def no_seed(monkeypatch):
    import dq.keys
    monkeypatch.setattr(dq.keys, 'has_seed', lambda: False)
