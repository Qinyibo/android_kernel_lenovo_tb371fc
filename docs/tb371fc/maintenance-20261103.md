# TB371FC r104 maintenance baseline — 2026-11-03

## Later update: r106 installed; rear USB port passes

The r106 candidate source is 4b397325943e70d3dbaaff63b5f622ab48668d62,
on recovery-state-r106; main remains the r104 source baseline. Its normal boot
and partition readback passed. It preserves failed recovery eligibility without
changing firmware/reset/CRC or USB. INIT=0x9D is not root-cause fixed and no
exceptional hardware recovery was exercised. See recovery-state-r106/README.md.

After moving from the prior connection to a rear motherboard USB port, the
same incompressible 16 MiB payload passed USB pull and push with matching SHA256.
Bootloader fastboot downloaded the current 96 MiB r106 boot in 2.491 seconds and
wrote it in 0.378 seconds, without error 121. Full boot readback and normal boot
passed, with user data preserved. The user accepts the rear-port path; stop USB
kernel patching. The controller stayed the same; only port 4 -> 5 changed in
Windows topology. This points to the former connection path without proving
which component failed. Full-ROM fastboot scripts were not rerun, and no
lifetime USB stability claim is made. Evidence: usb-retest-20261103.json.

The sections below describe the earlier r104 publication, not the latest USB
status. The original v26/r104 archive has not been replaced with an r106 archive.


This source publication preserves the deployed commit chain from
ad9987077d8eb726a1be70801a2b7aa12e886b54 through
455927db6665e2b3696aa8a96bc97fb09c20bd3a. The publication commit adds
maintenance documentation only. The ROM source and build integration live at
https://github.com/Qinyibo/TB371FC-ColorOS16 .

## Serious unresolved issues

- USB / bootloader fastboot bulk transfer remains unreliable. Small vbmeta
  flashes succeeded, but the 96 MiB boot download timed out before flashing.
  ADB tests also failed with the stock 4.19.157 Recovery kernel. No cable,
  host-controller, PHY or kernel root cause has been established. Completion
  requires a full ROM flash through bootloader fastboot and normal Android boot.
- Intermittent black screen / failure to wake is not root-cause fixed. The
  touch controller can remain at INIT=0x9D despite the existing hard-reset
  firmware recovery attempt. r104 only lets the existing panel-dead rail
  recovery pass the keep-panel-power guard; exceptional recovery was not proven.

The user currently accepts standby, freezing, scheduling/memory, thermals,
speaker/rotation and existing keyboard/touchpad behavior. Pen validation lacks
hardware. These are user observations, not comprehensive hardware certification.

## Retained source changes

- r6/r97: display-failure containment and touch/display diagnostics.
- r98/r99: real programmable mixer acknowledgements and session/COPP ownership.
- r102: battery CURRENT_AVG with the existing normalized current convention.
- r103: recheck group exit on each get_signal loop; backport of upstream
  e7f7c99ba911f56bc338845c1cd72954ba591707 preserving vendor freezer cleanup.
- r104: allow the existing dead-panel power cycle while ordinary gesture
  suspend keeps its current rail policy.

The r105 USB reset/queue candidate did not fix the measured fault and was
rolled back. It is not part of this baseline. The separately built r100 HID
candidate is also not part of the deployed baseline. Preserve normal keyboard
behavior; do not claim it was broken merely because that candidate was untested.

## Build identity and validation

Use the toolchain and inputs documented in build/tb371fc/r99-source-record.json,
kernel43.config and build.sh. For the deployed r104 identity, pass the override:

    KBUILD_BUILD_HOST=r104-panel-recovery OUT_DIR=/path/to/output JOBS=8 bash build/tb371fc/build.sh

The build entry retains historical defaults; do not identify a binary solely
from those defaults. The actual full r104 Image build passed; config and
Module.symvers matched the accepted baseline. Existing warnings remain.

- Image SHA256: cd216f2cd47c38bd7a86499f87c8a1eca065f428cf4997d62454d13a24812e50
- Boot SHA256: f29c32c15c7276d777f243a322ca35495099c25d6e41e402dd4eacb77121f85b
- Exact v26 ROM ZIP SHA256: 93de4dc2e1f7ecfba1fedb763a0d4e71d9ea4c4b18e053fd5103dc9e235ec100

r103 has a same-binary regression: ptrace signal-stop, freeze, then SIGKILL
failed on the old kernel and reaped correctly in all four cases on the new one.
r104 normal boot and partition readback passed. The v26 ROM was installed as a
data-preserving TWRP upgrade with complete four-partition readbacks. The exact
v26 package has not passed clean-first-boot or full fastboot installation.

Runtime sleep_disabled is N under the existing vendor post-boot script despite
the boot command line containing 1. USB/charger wake sources were active during
the connected standby observation, so no unplugged battery-life claim is made.

Boot packing must preserve the accepted DTB, ramdisk, AVB-related inputs and
header invariants. A new kernel source checkout alone does not provide these
proprietary ROM inputs. For rollback, use the exact saved r104 boot or an
accepted full image set; never flash an interrupted diagnostic RAM payload.
