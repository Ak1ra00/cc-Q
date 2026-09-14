# SPEC.md

Build spec for `cc-Q`. Milestones are ordered; do not start one before the
previous is merged and green in the simulator.

---

## M0 — Groundwork

Fork `Coldcard/firmware`, Q1 target only. Get the simulator running
(`unix/simulator.py`, needs SDL2) and confirm a Q1 build produces a signable
DFU using the non-production key zero that ships in the upstream tree.

Deliverable: simulator boots, `make -f Q1-Makefile` succeeds, a placeholder
screen renders. Push to `origin`.

Also in M0, answer this question and write the answer into `SPEC.md` under
"Findings", because two later milestones depend on it:

> **Does the Coldcard Q keep wall-clock time across a power cycle?**

Read the upstream source rather than guessing. If yes, the journal and codes
can trust the clock. If no, both need the resync flow described in M6, and the
journal must confirm the date with the owner on first write each session.

---

## M1 — Shell

### Theme layer — `shared/dq/theme.py`

A green phosphor CRT treatment, applied globally, not per screen.

```
bg          #030805
phosphor    #4dff9e   primary text, active elements
dim         #35d47f   body text
faint       #1f8f5c   labels, secondary info
alert       #ffb347   time pressure, attention, unsaved state
```

Monospace throughout. Header bar and footer bar on every screen, 22px each,
tinted phosphor at 13% opacity. Footer always shows the available keys for the
current screen. A scanline overlay at low opacity if it can be done without
costing frame time — drop it if it can't.

The 320x240 panel fits roughly 26 characters per line at 11px. Design to that,
and truncate with an ellipsis rather than wrapping in list views.

### App registry — `shared/dq/apps/__init__.py`

```python
class DQApp:
    name: str          # "vault" — storage namespace, must be stable forever
    title: str         # "vault" — shown in UI
    hotkey: str        # "v"
    def home_line(self) -> tuple[str, str, bool]:
        """Right-hand status for the home screen, and whether to alert on it."""
    def start(self): ...
```

`@register_app` appends to `APPS`. Home screen iterates `APPS`. Hotkey
collisions raise at import time, not at runtime.

### Home screen — `shared/dq/apps/home.py`

Date large at top. One row per registered app showing its `home_line()`.
Storage status underneath. Footer lists hotkeys. This screen must contain zero
app-specific logic.

---

## M2 — Keys and storage

### Key modes — `shared/dq/keys.py`

The firmware has two modes. Seedless is the default and everything must work in
it. A seed is optional and changes exactly one thing: where vault passwords
come from.

**Seedless (default).** On first run, generate a 32-byte device key from the
hardware TRNG (`ngu.random`) and store it in the settings blob, which is
already AES-encrypted under a key tied to the PIN and secure element. This is
the root for everything.

**Seed present (optional).** If a BIP39 seed happens to be loaded, the vault
additionally offers derived passwords via BIP-85, so a password is reproducible
from `(seed, index)` and needs no stored ciphertext. Everything else — journal,
codes, the store itself — still uses the device key and is unaffected.

```python
def has_seed() -> bool: ...
def device_key() -> bytes:      # 32 bytes, created on first run
def app_key(app_name) -> bytes: # HKDF(device_key, info=app_name)
def derive_password(index: int) -> str:   # BIP-85; raises if no seed
```

Never prompt the owner to add a seed. Never gate a feature on one. The only
place a seed may be mentioned in the UI is the vault's "new entry" screen,
where derived mode appears as an extra option when one is present and is simply
absent when one is not.

The seedless mode has a real consequence that must be stated plainly in the
README and in the first-run screen: **if the device is wiped, seedless data is
gone unless it was exported.** Derived vault entries survive a wipe if the seed
and index list survive. Stored entries, journal, and codes do not.

### Record store — `shared/dq/store.py`

One file per app on microSD: `dq-<app>.dat`.

```
magic "DQ01" | app name | schema version | nonce | AES-256-CTR ciphertext | HMAC-SHA256
```

Encrypted under `app_key(app_name)`. Verify the HMAC before decrypting anything.
Records are JSON objects. **Unknown fields are read, held, and written back
unchanged** — this is what lets a future version add fields without the current
one destroying them.

Write via temp file plus atomic rename. A yanked card mid-write must never
leave a truncated file as the only copy. If card B is present, mirror to it.

---

## M3 — Vault, stored mode

`shared/dq/apps/vault.py`

Record:

```json
{
  "id": 14,
  "service": "protonmail",
  "login": "akira@protonmail.com",
  "source": "stored",
  "secret": "<ciphertext, stored mode only>",
  "note": "",
  "created": "2026-09-13"
}
```

`id` is the index number and is the spine of the whole feature. It is assigned
once, never reused, never renumbered. It is what the owner writes on paper.

**Search screen.** Type to filter on service and login, case-insensitive
substring. Results show service left, id right. Selected row highlighted at 18%
phosphor. Footer shows match count against total.

**Detail screen.** Service and id in the header. Login. Password in large
phosphor, wrapped across two lines if needed. An auto-hide countdown in alert
colour — 20 seconds, resets on keypress. A QR of the password rendered at right
so a phone can read it. Footer offers the NFC push.

**Export.** Write a print-ready list of `service | login | id` to microSD as
plain text. This is the wallet card. It deliberately contains no passwords —
for derived entries the id is sufficient, and for stored entries the file is
useless without the device, which is the point.

---

## M4 — Vault, derived mode

When `has_seed()` is true, the new-entry screen offers derived alongside
stored. Derived records carry `"source": "derived"` and no `secret` field; the
password is regenerated from `(seed, id)` on each view via BIP-85.

The detail screen shows which mode an entry uses, because the backup story
differs and the owner needs to know at a glance.

Mixed vaults are normal and fully supported. Do not offer to convert entries
between modes — a converted password is a changed password, and the firmware
cannot change it on the remote service.

---

## M5 — Journal

`shared/dq/apps/journal.py`

One record per day, keyed by date. Full-screen editor, five visible lines,
scrolling. Word count and save state in the footer area. Encrypted under the
journal app key, written to card A, mirrored to card B when present.

Week view: seven bars sized by word count, today highlighted, unwritten days
as outlines only. Longest run and total days written underneath. Keep this
factual. No streak pressure, no nagging, no guilt copy — an unwritten day is
shown as an outline and nothing more.

---

## M6 — Codes

`shared/dq/apps/codes.py`

Depends on the M0 clock finding.

HOTP works with no clock at all and is the fallback if the finding is negative.
TOTP needs time: enroll by scanning `otpauth://` QRs, and resync by scanning a
QR containing the current Unix time. The header shows how long ago the clock
was set, and the footer always offers resync. If the clock is unset or stale
past a threshold, show codes greyed with an explicit warning rather than
showing numbers that might be wrong.

Three codes visible at once, each with a countdown bar.

---

## M7 — Polish

Boot sequence in the theme. First-run screen explaining the seedless backup
consequence. Settings: auto-hide duration, card B mirroring on/off, export path.
README with build, flash, and recovery instructions.

---

## Findings

### Does the Coldcard Q keep wall-clock time across a power cycle?

**No.** It has no usable wall clock at all, running or powered off. From the
source and the board BOM, not from guessing:

- `hardware/bom-q1d.xlsx` lists exactly one oscillator: an 8 MHz ceramic
  resonator (`OSC_CSTCE8M00G55-R0`, Y1), the HSE. There is no 32.768 kHz LSE
  crystal, and no coin cell or supercap on VBAT. The AAA cells (`BATT_CLIP_L/R`)
  power the whole device and are removable; nothing on the board is keeping a
  standby domain alive when it is off.
- `stm32/COLDCARD_Q1/mpconfigboard.h:17` sets `MICROPY_HW_ENABLE_RTC (0)`. The
  STM32 RTC is compiled out of the MicroPython port, so `pyb.RTC` does not exist
  at runtime. Mk3, Mk4 and Mk5 are the same.
- `stm32/COLDCARD_Q1/file_time.c` overrides `get_fattime()` with a constant baked
  in at build time. Every file written to microSD carries the firmware's build
  date — which is what you do when there is no clock to ask.
- Nothing under `shared/` reads a wall clock. All timing goes through
  `utime.ticks_ms()`, which counts from boot and restarts at every power cycle.
- Upstream's own time-adjacent feature, the far-future locktime warning, compares
  against a block height baked in at build time by `stm32/make_block_height.py`.

This is a hardware fact, not a firmware limitation we can patch around.

**Consequences, now binding:**

- **M5 journal.** The date is unknown at boot. Confirm it with the owner on the
  first write of each session, as M5 already requires.
- **M6 codes.** HOTP is the default and the only counter that survives a power
  cycle unattended. TOTP requires the owner to set the clock by QR after *every*
  power cycle; cc-Q holds `(unix_time_at_sync, ticks_ms_at_sync)` in RAM only, and
  time is unset again on the next boot. The last known time may be persisted to
  settings as a *lower bound* — useful for detecting a stale sync, never
  presentable as the current time. When time is unset or stale, grey the codes and
  say why, per M6.
