# Q1 only files; would not be needed on Mk4
freeze_as_mpy('', [
	'battery.py',
	'bbqr.py',
	'calc.py',
	'decoders.py',
	'gpu.py',
	'keyboard.py',
	'lcd_display.py',
	'notes.py',
	'q1.py',
	'scanner.py',
	'st7788.py',
	'teleport.py',
	'ux_q1.py'
], opt=0)

# cc-Q: our namespace. Everything of ours is here.
freeze_as_mpy('', [
	'dq/__init__.py',
	'dq/theme.py',
	'dq/keys.py',
	'dq/store.py',
	'dq/clock.py',
	'dq/dates.py',
	'dq/backup.py',
	'dq/otp.py',
	'dq/session.py',
	'dq/ui.py',
	'dq/hid.py',
	'dq/apps/__init__.py',
	'dq/apps/home.py',
	'dq/apps/vault.py',
	'dq/apps/journal.py',
	'dq/apps/codes.py',
	'dq/apps/recovery.py',
	'dq/apps/sign.py',
	'dq/apps/witness.py',
	'dq/apps/keypad.py',
], opt=0)

# Optimize data-like files, since no need to debug them.
freeze_as_mpy('', [
	'font_iosevka.py',
	'gpu_binary.py',        # remove someday?
	'graphics_q1.py',
], opt=3)

