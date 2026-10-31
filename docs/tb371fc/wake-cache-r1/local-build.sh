#!/bin/bash
set -euo pipefail
BASE=/work/tb371fc-wake-20261031
TREE=$BASE/src
OUT=$BASE/out
W=/mnt/c/Users/Administrator/Documents/Codex/2026-10-28/yu/work/wake-repair
exec 9>"$BASE/build.lock"
flock -n 9
python3 - "$W" "$TREE" <<'PY'
import hashlib,json,sys
from pathlib import Path
w,tree=map(Path,sys.argv[1:])
m=json.loads((w/'source-manifest.json').read_text())
previous=json.loads((w/'source-manifest-initial-build.json').read_text())
assert previous['base_commit']==m['base_commit']
for name,hashes in m['changes'].items():
    src=tree/name
    current=hashlib.sha256(src.read_bytes()).hexdigest()
    if current not in (hashes['before'],hashes['after'],previous['changes'][name]['after']):
        raise SystemExit('Unexpected build input: '+name)
    data=(w/'overrides'/src.name).read_bytes()
    assert hashlib.sha256(data).hexdigest()==hashes['after']
    src.write_bytes(data)
print('THREE_SOURCE_INPUTS_VERIFIED',flush=True)
PY
mkdir -p "$OUT"
if [ ! -e "$OUT/.config" ]; then cp "$TREE/build/tb371fc/kernel43.config" "$OUT/.config"; fi
export PATH=/usr/lib/llvm-21/bin:/usr/sbin:/usr/bin:/bin
export LD_LIBRARY_PATH=/root/tc-shim/lib
# Keep the existing #43 ABI family; the host and timestamp identify this
# candidate unambiguously, independently of the historical accepted image.
export KBUILD_BUILD_USER=tb371fc-offline
export KBUILD_BUILD_HOST=r94-wake-cache-r1
export KBUILD_BUILD_VERSION=43
export KBUILD_BUILD_TIMESTAMP='Sat Oct 31 2026 12:00:00 +0800'
FLAGS="-Wno-error -Wno-error=strict-prototypes -Wno-error=implicit-int -Wno-error=incompatible-pointer-types -Wno-error=date-time -include $TREE/drivers/staging/fw-api/fw/p226_compat.h"
make -C "$TREE" --output-sync=target -j8 O="$OUT" ARCH=arm64 CC=clang CLANG_TRIPLE=aarch64-linux-gnu- CROSS_COMPILE=aarch64-linux-gnu- AS=aarch64-linux-gnu-as LOCALVERSION= KCFLAGS="$FLAGS" DYNAMIC_SINGLE_CHIP=qca6390 Image >"$W/kernel-build.log" 2>&1
cmp "$TREE/build/tb371fc/kernel43.config" "$OUT/.config"
cp "$OUT/arch/arm64/boot/Image" "$W/Image-wake-cache-r1"
cp "$OUT/Module.symvers" "$W/Module.symvers-wake-cache-r1"
cp "$OUT/.config" "$W/kernel.config"
sha256sum "$W/Image-wake-cache-r1"
echo KERNEL_BUILT_NOT_FLASHED
