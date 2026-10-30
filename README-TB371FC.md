# TB371FC ColorOS16 kernel43 corresponding source

This is the complete Linux 4.19 source used as the kernel43 build baseline, with the exact touch/USB/display/audio files from the verified kernel43 build folded into the tree. Original copyright and license notices are retained; see COPYING and component headers. It is not a claim that proprietary ColorOS framework/application sources are available.

The historical build used LLVM21, GNU aarch64 cross binutils, the supplied full configuration, KBUILD_BUILD_VERSION=43 and the recorded timestamp. Run build/tb371fc/build.sh in Linux with the required toolchain and build dependencies. The original compiler environment also used /root/tc-shim/lib; compiler/runtime provisioning must be reproduced separately. The build recipe is provided; this exported Git tree has not yet been independently rebuilt, so bit-for-bit reproducibility is not asserted.

Expected historical Image SHA256: c234e5c0ed600369816fb98f5d4a54748dc46bc4dcd5bff07529c82e165a2519.
Expected historical boot image SHA256: 09d3c1bd67946575de8b0dad434f651e746747da2686fa227719142ad47cfbbe.

drivers/net/oplus_vnet contains the actual external vnet module source/Makefile whose historical built module matches the ROM payload SHA256 01cb1335daddcf308d11076af1db50f5386c6bb94312243b02197d1a7bfc66bd. Build it with the matching configured kernel output and compiler; it is not silently enabled as a built-in driver by this export.

Upstream lineage includes Linux, Qualcomm/Android and the TB371FC kernel project previously referenced as https://github.com/smith-dog/kernel-tb371fc . This working baseline was preserved without a .git history directory; this release does not invent upstream history or authorship. Generated objects, local signing private keys and machine credentials are excluded. This repository contains source and configuration, not personal tablet data or private keys.

## Development records

See [docs/tb371fc](docs/tb371fc/README.md) for the stock11-to-kernel43 patch, source hashes, IRQ/Hall/PM design notes and historical test scope. The ROM-side research history and failed performance trials are documented in [TB371FC-ColorOS16/docs](https://github.com/Qinyibo/TB371FC-ColorOS16/tree/main/docs).
