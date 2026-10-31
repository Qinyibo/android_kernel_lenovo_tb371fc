#!/bin/bash
set -euo pipefail
BASE=/work/tb371fc-wake-20261031
W=/mnt/c/Users/Administrator/Documents/Codex/2026-10-28/yu/work/wake-repair
OLD=/mnt/d/TB371FC-release/R94T-v23-20261030-TEST/images/boot_a.img
P=$BASE/pack
test "$(sha256sum "$OLD" | cut -d' ' -f1)" = 09d3c1bd67946575de8b0dad434f651e746747da2686fa227719142ad47cfbbe
test -f "$W/Image-wake-cache-r1"
mkdir -p "$P/before" "$P/candidate" "$P/after"
cp /work/tb371fc-c16-r7-20261010/r94-reclaim-coop-pack-v1/magiskboot "$P/magiskboot"
chmod 755 "$P/magiskboot"
cd "$P/before"
../magiskboot unpack "$OLD" >"$W/boot-original-unpack.log" 2>&1
test "$(sha256sum kernel | cut -d' ' -f1)" = c234e5c0ed600369816fb98f5d4a54748dc46bc4dcd5bff07529c82e165a2519
cd ../candidate
cp ../before/* .
cp "$W/Image-wake-cache-r1" kernel
../magiskboot repack "$OLD" "$W/boot-wake-cache-r1.img" >"$W/boot-repack.log" 2>&1
cd ../after
../magiskboot unpack "$W/boot-wake-cache-r1.img" >"$W/boot-candidate-unpack.log" 2>&1
cmp kernel "$W/Image-wake-cache-r1"
for payload in ../before/*; do
    name=$(basename "$payload")
    test "$name" = kernel || cmp "$payload" "$name"
done
test "$(stat -c%s "$W/boot-wake-cache-r1.img")" = 100663296
python3 - "$OLD" "$W/boot-wake-cache-r1.img" <<'PY'
from pathlib import Path
import struct,sys
old,new=[p.read_bytes() for p in map(Path,sys.argv[1:])]
assert old[:8]==new[:8]==b'ANDROID!'
page=struct.unpack_from('<I',old,36)[0]
assert page==struct.unpack_from('<I',new,36)[0]
assert struct.unpack_from('<I',old,40)[0]==2
a,b=bytearray(old[:page]),bytearray(new[:page])
# Kernel size, boot image digest and derived recovery-DTBO position are
# allowed to change. Every other header field/padding must be identical.
for start,end in [(8,12),(576,608),(1636,1644)]:
    a[start:end]=b'\0'*(end-start);b[start:end]=b'\0'*(end-start)
assert a==b,'Unexpected boot-header change'
print('BOOT_HEADER_AND_NONKERNEL_PAYLOADS_MATCH')
PY
sha256sum "$W/boot-wake-cache-r1.img"
echo CANDIDATE_PACKED_NOT_FLASHED
