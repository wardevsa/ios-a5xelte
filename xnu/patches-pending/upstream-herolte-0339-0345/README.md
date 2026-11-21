# Upstream herolte patches 0339-0345, held back (2026-11-21)

wardevsa/ios-a5xelte `herolte` added 0339-0345 after our common ancestor (haptic motor, MFC probe, PWM prescaler, the Note FE merge 0342 with
Bluetooth and the front camera, brightness floor, S7 defaults, v80emu). Placed at their numbers they make 62 of OUR patches (0401 onwards)
skip, because 0342 rewrites the same files (herolte_drop.c, herolte_gl.c, herolte_gpu.c, SweetFramebuffer.cpp, SweetBattery.cpp) and overlaps
our charger readout (0431/0432) and CPU governors (0434, 0467). Applied after ours (0490-0496) and with fuzz, 12 hunks reject (10 of
0342, 2 of 0339), and 0342's governor duplicates ours. Taking them needs a deliberate merge, hunk by hunk; the Metal stack does not need
them (only 0487). Tested with the local simulation of dxb's patch loop (git apply --check in the CI order).
