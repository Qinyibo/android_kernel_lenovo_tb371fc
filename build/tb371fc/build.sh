#!/bin/bash
set -euo pipefail
TREE=$(cd "$(dirname "$0")/../.." && pwd)
OUT=${OUT_DIR:-"$TREE/out-tb371fc"}
mkdir -p "$OUT"
cp "$TREE/build/tb371fc/kernel43.config" "$OUT/.config"
export PATH="${LLVM_BIN:-/usr/lib/llvm-21/bin}:$PATH"
export KBUILD_BUILD_USER=tb371fc-offline KBUILD_BUILD_HOST=r94-wake-cache-r1
export KBUILD_BUILD_VERSION=43
export KBUILD_BUILD_TIMESTAMP='Sat Oct 31 2026 12:00:00 +0800'
FLAGS="-Wno-error -Wno-error=strict-prototypes -Wno-error=implicit-int -Wno-error=incompatible-pointer-types -Wno-error=date-time -include $TREE/drivers/staging/fw-api/fw/p226_compat.h"
make -C "$TREE" --output-sync=target -j"${JOBS:-4}" O="$OUT" ARCH=arm64 CC=clang CLANG_TRIPLE=aarch64-linux-gnu- CROSS_COMPILE=aarch64-linux-gnu- AS=aarch64-linux-gnu-as LOCALVERSION= KCFLAGS="$FLAGS" DYNAMIC_SINGLE_CHIP=qca6390 Image
echo 'Image output:' "$OUT/arch/arm64/boot/Image"
