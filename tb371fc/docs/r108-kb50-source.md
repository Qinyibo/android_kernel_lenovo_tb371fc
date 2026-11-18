# r108 / KB50 kernel source record

- Device: Lenovo TB371FC (spinel, SM8250/kona), kernel 4.19.325
- Release identity: `#50 r108-force-rek-keyboard-bias-wake-idle-ab`
- Source base commit: `41082098de91855a809239bf64f339a16d39effe`
  ("drm: complete panel recovery after native touch readiness")
  This was the HEAD of the old build worktree `/work/r108-src` (worktree metadata preserved in the
  local bare repository; working tree no longer exists).
- Delta applied for r108: `0001-TB371FC-restore-native-keyboard.patch`
  - original file sha256 (CRLF): `2eedc0f0688ec084e6c614a89a32a143547b90a1bc64b79e1fc3aee42bf31132`
  - normalized (LF) copy included for reproducible `git apply`
  - touches only `drivers/hid/i2c-hid/i2c-hid-core.c`
  - result file sha256: `79f5f1142939e33e03c3249ecb2d9cb1a82d3a287486d9c730501092ecdd5f94`
    (matches the r108 release record in TB371FC-ColorOS16 release-v27-r108-KB50-R5)

## Build artefacts recorded by the release manifest

| item | sha256 |
| --- | --- |
| kernel Image | `36ecd89712bc20b0b86da94909447d401f6ad441efe4212cbfdfd8629d0faa03` |
| .config | `4dcaebca4ccca59c5172b4e6c573bea22ed5b039a1cb8eab0fa45ff39bc6bf52` |
| Module.symvers | `502bf4adbc23f0d9f5c4885beb55833ce0f86882e9bfcec2c2d4720b50b27b1b` |

- Toolchain recorded at handoff: Clang 21.1.8, binutils 2.42.
- The exact `.config` contents were not preserved; only its sha256 is recorded above.
- Build recipe (from kernel README): `make -j6 ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- CC=clang
  CLANG_TRIPLE=aarch64-linux-gnu- AS=aarch64-linux-gnu-as KCFLAGS=-Wno-error Image`
- Force REK markers are part of the source base and were left untouched.

## Status

- This branch is an archived source snapshot for the running r108/#50 kernel; it has NOT been
  re-flashed or re-validated from this branch.
- `main` is untouched; this is an independent `local/r108-kb50-source` branch.

## Verified against the recovered r108 builder disk (D:\WSL\TB371FC-Builder\ext4.vhdx)

The old builder WSL disk was mounted read-only and the following were confirmed byte-for-byte
against the release manifest:

| item | recovered file | sha256 | matches manifest |
| --- | --- | --- | --- |
| build config | /work/r108-out/.config | `4dcaebca4ccca59c5172b4e6c573bea22ed5b039a1cb8eab0fa45ff39bc6bf52` | yes |
| Module.symvers | /work/r108-out/Module.symvers | `502bf4adbc23f0d9f5c4885beb55833ce0f86882e9bfcec2c2d4720b50b27b1b` | yes |
| source tree | /work/r108-src (worktree HEAD 41082098d, clean) | file sha `ed6794…` before patch | base tree |

The exact `.config` is now committed at `tb371fc/configs/r108-kb50.config`.
The final KB50 `Image` with sha `36ecd897…` was not present on this builder disk; it was produced later
and only its hash is recorded.
