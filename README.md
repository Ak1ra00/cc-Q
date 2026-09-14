# cc-Q

Custom firmware for the **Coldcard Q**. It takes the Bitcoin workflow out of the
way and puts a daily-use personal terminal behind the device PIN instead: a
password vault, sign-in codes, and an encrypted journal.

The hardware is the reason. A Coldcard Q is a secure element, a real keyboard, a
screen, a camera, NFC, and no radio of any kind — a good body for secrets that
should never touch a network. cc-Q keeps the security model and replaces the
application.

Built on [Coldcard/firmware](https://github.com/Coldcard/firmware), **Q1 target
only**. Not affiliated with, endorsed by, or supported by Coinkite.

> ### Read this first
>
> - cc-Q is signed with the **public developer key (key 0)** from the upstream
>   tree. A Q running it shows the unofficial-firmware warning and a long delay on
>   **every** boot, and the *genuine* light stays **red** until official Coinkite
>   firmware is reinstalled. That is the expected state, not a fault.
> - **Keep an official Coinkite `.dfu` for your Q on a spare microSD**, from
>   [coldcard.com/downloads](https://coldcard.com/downloads). That card is the way
>   back. Set it aside before you flash anything from here.
> - Treat any device you flash as a **testing device**.
> - Q only. The image refuses to install on Mk3, Mk4, or Mk5 (`hw_compat 0x10`).

## What it is

Three apps, all encrypted under keys that never leave the device, all reachable
from one home screen:

- **vault** — passwords, searchable by service and login. Each entry has a number
  that never changes and never gets reused. That number is what you write on a
  paper card; the card itself carries no passwords.
- **codes** — TOTP and HOTP sign-in codes, enrolled by scanning the QR the service
  shows you.
- **journal** — one encrypted entry per day, written on the device's own keyboard.

Behind them: a green-phosphor CRT theme applied globally, a plugin registry so the
home screen never hardcodes an app list, and an app-scoped record store on microSD
with a schema version and atomic writes.

### No seed required

cc-Q runs fully **without a BIP39 seed**, and that is the supported default. On
first run it generates a 32-byte device key from the hardware TRNG and keeps it in
the settings blob, which is already encrypted under a key tied to your PIN and the
secure element. Each app gets its own subkey derived from that.

A seed is optional and changes exactly one thing: the vault can additionally offer
passwords derived from `(seed, index)` via BIP-85, which need no stored ciphertext.
Journal, codes, and the store itself never use it.

**The consequence, stated plainly: if the device is wiped, seedless data is gone
unless you exported it.** Derived vault entries survive a wipe as long as the seed
and the index list survive. Stored entries, journal, and codes do not. This is the
trade for not requiring a seed, and it is also why the vault has an export.

## Status

**M0 — groundwork: done.** M1 is next.

| milestone | what | state |
|---|---|---|
| **M0** | Fork, Q1 build, signable DFU, simulator, clock finding | **done** \* |
| M1 | Theme layer, app registry, home screen | next |
| M2 | Key modes and the encrypted record store | |
| M3 | Vault, stored mode | |
| M4 | Vault, derived mode (BIP-85, seed present) | |
| M5 | Journal | |
| M6 | Codes | |
| M7 | Polish: boot sequence, first-run screen, settings | |

\* M0's placeholder screen never landed in the tree — there is no `shared/dq/`
yet. M1's home screen replaces it outright, so it is folded into M1 rather than
built twice.

M0 answered the question two later milestones depend on — **does the Q keep
wall-clock time across a power cycle?** It does not, and it has no wall clock
while running either: the RTC is compiled out of the port, there is no 32.768 kHz
crystal or backup cell on the board, and file timestamps come from a constant baked
in at build time. The evidence is in [`SPEC.md`](SPEC.md) under Findings. It is why
the journal will confirm the date with you, and why codes default to HOTP with a
QR resync flow for TOTP.

The plan lives in [`SPEC.md`](SPEC.md), the backlog in
[`FEATURES.md`](FEATURES.md), and the rules the code is held to in
[`CLAUDE.md`](CLAUDE.md).

## Firmware

The published build is the **M0 baseline**: upstream `2026-09-03T1540-v1.5.2Q`
rebuilt from this tree and signed with dev key 0. It proves the toolchain and
gives every later build something to diff against — **it contains no cc-Q app
yet**, so a Q flashed with it behaves as a normal Coldcard that warns about
unofficial firmware. The first build worth installing for its own sake arrives
with M1.

| file | version | target | key | sha256 |
|---|---|---|---|---|
| [`2026-09-03T1540-v1.5.2Q-q1-devkey0-cc-Q.dfu`](releases/cc-Q/2026-09-03T1540-v1.5.2Q-q1-devkey0-cc-Q.dfu) | 1.5.2Q (baseline) | Q (`hw_compat 0x10`) | dev key 0 | `86868b477a004c50c1dbb6c8497006206560ad89002124bc945ef9905e7a3d61` |

Download it from the tree above with GitHub's **Download raw file** button, or from
the [release page](https://github.com/Ak1ra00/cc-Q/releases/tag/2026-09-03T1540-v1.5.2Q).
Same bytes either way. Check it before it goes anywhere near hardware:

```shell
cd releases/cc-Q && sha256sum -c SHA256SUMS
```

`SHA256SUMS` is not PGP-signed. Upstream's `releases/signatures.txt` covers
Coinkite's official binaries only and says nothing about this file.

### Flashing, when you decide to

Flashing is a deliberate step you take, not part of any build routine — the
simulator is where cc-Q gets exercised. When you do want it on hardware: copy the
`.dfu` to a FAT32 microSD, then on the Q go **Advanced/Tools → Upgrade Firmware →
From MicroSD**, check the version on screen, and approve. The Q reboots and
installs. The first boot afterwards shows the unofficial-firmware warning and a
long delay; that is key 0 doing its job.

To go back: install the matching official `.dfu` from
[coldcard.com/downloads](https://coldcard.com/downloads) the same way. Coldcard
refuses downgrades below the installed version's timestamp, so use that version or
newer. The genuine light goes green again on the next PIN entry.
[`docs/upgrade-recovery.md`](docs/upgrade-recovery.md) covers an interrupted
upgrade.

## Running it

The simulator is the primary target. Everything must run clean there first, and
you do not need a Q to work on cc-Q.

```shell
git clone --recursive https://github.com/Ak1ra00/cc-Q.git
cd cc-Q
python3 -m venv ENV && source ENV/bin/activate
pip install -U pip setuptools && pip install -r requirements.txt

cd unix && make setup && make ngu-setup && make && ./simulator.py --q1
```

Needs SDL2. Per-platform package lists for macOS and Linux are in
[`docs/upstream-README.md`](docs/upstream-README.md).

### Building the firmware

Built with the Arm GNU Toolchain 13.3.rel1 (`arm-none-eabi-gcc`) and Python 3.11:

```shell
pip install --editable cli            # provides `signit`, used by the Makefiles
cd stm32
make -f Q1-Makefile setup
make -f Q1-Makefile CFLAGS_EXTRA=-Wno-error=dangling-pointer
make -f Q1-Makefile firmware-signed.dfu
```

`CFLAGS_EXTRA=-Wno-error=dangling-pointer` is only needed on GCC 13+, which
promotes that warning to an error inside bundled MicroPython. Check what you built
before it leaves your machine:

```shell
signit check stm32/firmware-signed.bin    # prints the version and `Signed by pubkey=0`
```

An unmodified checkout reproduces the published file byte for byte apart from the
build timestamp in `stm32/COLDCARD_Q1/file_time.c`. Coinkite's deterministic Docker
flow (`make -f Q1-Makefile repro`, see [`docs/notes-on-repro.md`](docs/notes-on-repro.md))
is for verifying *official* binaries against *upstream* source.

### Tests

```shell
cd testing && py.test dq/          # cc-Q tests
```

Upstream's suite under `testing/` still applies to upstream code and needs a
running simulator.

## Layout

cc-Q code lives in one namespace, `shared/dq/`, so that upstream can still be
merged and so a new app is cheap to add:

```
shared/dq/
    theme.py            palette, header and footer bars, list rendering
    keys.py             device key, per-app subkeys, optional BIP-85
    store.py            encrypted per-app record file, atomic write, card mirror
    apps/__init__.py    DQApp base class, @register_app, APPS registry
    apps/home.py        home screen — reads the registry, knows no app
    apps/vault.py  apps/journal.py  apps/codes.py
```

Adding an app is four steps: write the class, decorate it with `@register_app`, add
it to `manifest_q1.py`, add tests in `testing/dq/`. Storage, encryption subkey,
theming, and the home screen slot come from the framework. Any file we touch
*outside* `shared/dq/` is logged in [`PATCHES.md`](PATCHES.md) — that list is the
whole surface where an upstream merge can conflict.

Everything else is upstream's: `shared/` (application code), `stm32/` (embedded
build, bootloaders, signing), `unix/` (simulator), `testing/`, `external/`,
`docs/`, `graphics/`, `hardware/`, `cli/`.

Two boundaries that are not negotiable: the bootloader in `stm32/bootloader/` is
signed by Coinkite, runs first, and is never touched; the PIN entry and login
sequence are never modified, because a crash there bricks the device with no
recovery path.

## License and support

Code is © Coinkite Inc. under the terms in [`COPYING-CC`](COPYING-CC) —
source-available, not OSI open source. That license is kept intact and this fork
carries the same terms.

Do **not** take cc-Q problems to Coinkite support; they did not build this and cannot
help with it. Upstream Coldcard bugs belong at
[Coldcard/firmware](https://github.com/Coldcard/firmware). Anything about this
fork belongs in [its own issues](https://github.com/Ak1ra00/cc-Q/issues).
