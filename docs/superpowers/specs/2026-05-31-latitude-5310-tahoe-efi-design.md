# Dell Latitude 5310 — macOS Tahoe 26 EFI (Design Spec)

**Date:** 2026-05-31
**Target device:** Dell Latitude 5310 (this machine, currently running CachyOS Linux)
**Target OS:** macOS Tahoe 26 (Darwin 25)
**Tool:** OpCore-Simplify (this repo)
**Approach:** C — Tool generates EFI base, then hand-tune device-specific items.

---

## 1. Goal & Success Criteria

Produce a working OpenCore EFI for this Latitude 5310 that boots macOS Tahoe 26 and is **daily-usable**, plus a full install kit (USB recovery installer, BIOS settings, USB port map, post-install fixes) — all produced **on Linux, without a Mac or Windows**.

**Success = (verifiable by user on hardware):**
- OpenCore boots, macOS Tahoe installer loads from USB recovery.
- Tahoe installs to disk alongside CachyOS (dual-boot preserved).
- Post-install: iGPU accelerated (QE/CI), Ethernet, USB, trackpad, keyboard, audio output, Bluetooth all functional.
- WiFi functional via AirportItlwm (with itlwm+HeliPort as documented fallback).
- Dual-boot: OpenCore picker shows both macOS and CachyOS; both boot.

**Explicitly NOT promised:** literal zero bugs. Tahoe 26 is new; OCLP 3.0.0 is early-stage. Known-fragile items (AirportItlwm on Tahoe, audio via OCLP rollback, laptop sleep) are called out with fallbacks. Each residual quirk will be reported honestly, not hidden.

**Out of scope:** Sidecar/Continuity/iServices login setup, FileVault, fingerprint reader (no macOS driver), the SD card reader is optional (disable or Sinetek-rtsx).

---

## 2. Confirmed Hardware (detected on Linux)

| Component | Detail | IDs | macOS plan |
|-----------|--------|-----|-----------|
| CPU | Intel i5-10210U, Comet Lake-U (10th gen), 4C/8T | family 6 model 142 stepping 12 | Native → Tahoe. CPUID `55060A00`. `AppleXcpmCfgLock` quirk (Dell BIOS hides CFG-Lock). |
| iGPU | Intel UHD Graphics (CometLake-U GT2) | `8086:9b41`, subsys `1028:099f` | Native. platform-id `0900A53E`, device-id spoof `9B3E0000`, WhateverGreen. |
| Audio | Realtek ALC3254 (ALC295 family) | `10ec:0295` (HDA `10ec0295`) | AppleALC + tested `layout-id`. Tahoe: AppleHDA removed → OCLP rollback (primary) or VoodooHDA (fallback). |
| Ethernet | Intel I219-V (10) | `8086:0d4f` | IntelMausi. Native, reliable. |
| WiFi | Intel AX201 (CNVi) | `8086:02f0` | **AirportItlwm** (user choice) for native-style menu; itlwm+HeliPort documented fallback. |
| Bluetooth | Intel AX201 BT (USB) | `8087:0026` | IntelBluetoothFirmware + BlueToolFixup + IntelBTPatcher. |
| Storage | KYO 476.9 GB **SATA** SSD (no NVMe) | AHCI `8086:02d3` | Native AHCI. `built-in` property so it shows internal. |
| Trackpad | Dell I2C precision touchpad | `DELL099F:00 044E:120A` | VoodooI2C + VoodooI2CHID. |
| Keyboard | PS/2 | — | VoodooPS2Controller (keyboard + Dell-specific map). |
| Card reader | Realtek RTS525A | `10ec:525a` | Sinetek-rtsx (optional) or disable via ACPI. |
| Webcam | USB Realtek Integrated_Webcam_HD | `0bda:5676` | UVC native (USB cam). |
| Firmware | Dell BIOS 1.19.0, UEFI, TPM2, DMAR (VT-d), LPIT | — | Secure Boot OFF, AHCI, VT-d handled by `DisableIoMapper`. |
| Platform | Laptop, chassis type 10 | — | SMBIOS `MacBookPro16,2` (tool default for CML laptop). |

ACPI tables present and dumpable (`/sys/firmware/acpi/tables/`): DSDT + SSDT1–8 static, SSDT9–15 dynamic. Root read required.

---

## 3. Architecture / Pipeline

Five stages, each independently runnable and verifiable. Artifacts flow forward.

```
[Stage 1: Report]  Linux sysfs/lspci/DMI + sudo ACPI dump
       │  produces: SysReport/Report.json + SysReport/ACPI/*.aml
       ▼
[Stage 2: Validate] Scripts/report_validator.py must pass
       ▼
[Stage 3: Build]   python3 OpCore-Simplify.py → option1 → Tahoe → build
       │  produces: Results/EFI/
       ▼
[Stage 4: Hand-tune]  patch config.plist + swap/add kexts (USB map, audio, WiFi build)
       │  produces: tuned Results/EFI/
       ▼
[Stage 5: Install kit] macrecovery Tahoe BaseSystem + docs (BIOS, USB, post-install)
       │  produces: USB layout + INSTALL.md
       ▼
[User] flashes USB, sets BIOS, installs, reports back → iterate quirks
```

### Stage 1 — Hardware report generator (`tools/gen_report_latitude5310.py`, new)
A standalone Python3 script (stdlib only) that:
- Reads `lspci -nn -mm`, `/sys/class/dmi/id/*`, `/proc/cpuinfo`, `/sys/class/drm`, sysfs net/usb/sound.
- Emits `SysReport/Report.json` conforming to `report_validator.py` schema (Motherboard, BIOS, CPU, GPU, Network, USB Controllers, Input, Storage Controllers, Sound, Bluetooth, optional SD/Monitor/Biometric/System Devices).
- Device ID format `XXXX-XXXX` (vendor-device). PCI paths and ACPI paths derived from `lspci` topology + ACPI `_ADR`/`_UID` where derivable; fall back to documented Latitude 5310 paths where sysfs is insufficient.
- ACPI dump: requires one `sudo` step — `sudo cp /sys/firmware/acpi/tables/{DSDT,SSDT*} SysReport/ACPI/` and strip the `dynamic/` ones appropriately. Script prints the exact command; user runs it (sudo not assumed silently).
- Hardcodes/validates values specific to this exact machine (the detected IDs above) — this is a one-device tool, not a general sniffer.

**Why a script, not hand-written JSON:** repeatable, reviewable, and re-runnable if BIOS/hardware changes. Kept in `tools/` so it does not touch upstream `Scripts/`.

### Stage 2 — Validation
Run `Scripts/report_validator.py` against the generated report. Must pass with zero errors before building. If it fails, fix the generator (TDD-style: validator is the test).

### Stage 3 — EFI build
Drive `OpCore-Simplify.py`:
- Option 1: provide `SysReport/Report.json`, then `SysReport/ACPI/` folder.
- Compatibility check → select **Tahoe (26 / Darwin 25)**.
- Accept tool's ACPI patch + kext + SMBIOS selections (review them).
- Option 6: build (downloads OpenCorePkg + kexts; needs internet; iasl + macserial.linux auto-fetched).
- Output: `Results/EFI/`.

Interactive prompts: the tool is menu-driven. Drive it interactively (it reads stdin paths). Where automatable via piped input we will; otherwise the plan documents exact keystrokes.

### Stage 4 — Hand-tune (the "lancar" delta)
Post-process `Results/EFI/` for items the tool can't get right blind:

1. **USB mapping** — true port personalities can only be captured from macOS/Windows USBToolBox, not Linux. So Stage 4 ships a **known-good CometLake-U PCH-LP template `UTBMap.kext`** (single `XHC@14`, ≤15 ports: internal for AX201 BT / webcam / card-reader, external for the physical USB-A and USB-C ports), and `INSTALL.md` documents finalizing it on-hardware post-install with USBToolBox.app. This replaces reliance on `XhciPortLimit`.
2. **Audio** — set ALC295 `layout-id` (candidate layouts 11, 21, 28, 66, 99 — documented to test with `alcid` boot-arg); ensure AppleALC present.
3. **WiFi** — replace tool's WiFi kext with the **AirportItlwm build matching Tahoe 26 (Darwin 25)** from the OpenIntelWireless repo; keep itlwm + HeliPort.app staged as fallback in the kit.
4. **config.plist quirks** — confirm `AppleXcpmCfgLock=true`, `DisableIoMapper=true` (VT-d/DMAR present), `ResizeAppleGpuBars=-1` (no Resizable BAR on 10th gen), boot-args (`-v keepsyms=1 debug=0x100` for first boot, `alcid=` for audio test), SMBIOS `MacBookPro16,2` with generated serial/MLB/UUID.
5. **Dual-boot** — `Misc>Security>ScanPolicy=0`, `Misc>Boot` picker enabled; OpenCanopy theme present; verify it scans the CachyOS systemd-boot/ESP entry. Do NOT touch the existing Linux ESP contents — OpenCore is added alongside.

### Stage 5 — Install kit (no Mac/Windows)
- **Recovery installer:** `OpenCorePkg/Utilities/macrecovery/macrecovery.py` to download Tahoe `BaseSystem.dmg`/`.chunklist` → place under `com.apple.recovery.boot` on a USB; put the tuned `EFI/` on the USB ESP. Boot the USB → OpenCore → "macOS Recovery" → reinstall macOS Tahoe over internet.
- **Docs (`INSTALL.md`):** exact Latitude 5310 BIOS settings (Secure Boot Off, SATA=AHCI, disable Intel SGX/optional, enable USB boot, etc.), USB-stick prep commands on Linux, the install walkthrough, dual-boot partitioning (shrink CachyOS safely — **backup first**), and post-install (OCLP 3.0.0 from `lzhoang2801/OpenCore-Legacy-Patcher` for AppleHDA rollback on Tahoe, copy EFI to internal ESP, verify each device).

---

## 4. Data Flow & Interfaces

- **`SysReport/Report.json`** — interface between Stage 1 and Stage 3; schema owned by `Scripts/report_validator.py` (the contract).
- **`SysReport/ACPI/*.aml`** — raw tables consumed by `Scripts/acpi_guru.py`/`dsdt.py` (decompiled via auto-downloaded Linux iasl).
- **`Results/EFI/`** — tool output; mutated in place by Stage 4.
- **`tools/`** (new dir) — our additions (report generator, tuning notes, kit scripts). Kept separate from upstream `Scripts/` so the repo's self-updater doesn't clobber them.
- **`OCK_Files/`** — tool's download cache (kexts, OpenCorePkg). Internet required once.

No upstream `Scripts/` files are modified. All new work lives in `tools/` and `docs/`. The repo's `updater.py` self-update stays compatible.

---

## 5. Error Handling & Risks

| Risk | Handling |
|------|----------|
| Report fails validator | Validator is the test; iterate generator until clean before building. |
| iGPU `9b41` not in native IDs | Tool injects device-id `9B3E0000` — verified in `config_prodigy.py:194`. |
| **AirportItlwm breaks on Tahoe build** | Stage 4 fetches the exact Darwin-25 build; kit ships itlwm+HeliPort fallback + switch instructions. |
| **Audio (AppleHDA removed in Tahoe)** | Primary: OCLP 3.0.0 post-install rollback. Fallback: VoodooHDA. Documented, not silently assumed. |
| Laptop sleep/lid quirks | SSDT-PNLF/EC + sleep `_PRW` fixes from tool; may need iteration on hardware. |
| Dual-boot partition damage | Backup-first warning; prefer shrinking from macOS installer Disk Utility; never write to Linux ESP. |
| USB port count >15 / wrong personalities | UTBMap.kext with correct LP map instead of XhciPortLimit. |
| ACPI dump needs root | One explicit `sudo cp` step; command printed, user runs it. |
| Can't boot-verify from Linux | Honest: user runs hardware; we iterate on reported symptoms. No false "it works" claims. |
| Tool self-update overwrites work | Our files live outside `Scripts/`; pin tool to current SHA during build if needed. |

---

## 6. Testing / Verification Strategy

- **Stage 1–2:** `report_validator.py` passes (automated, on Linux now).
- **Stage 3:** `Results/EFI/` exists with `config.plist`, ACPI SSDTs, expected kexts; `config.plist` parses as valid plist; OpenCore `ocvalidate` (from OpenCorePkg) passes.
- **Stage 4:** `ocvalidate` still passes after tuning; kext list + config keys diff-reviewed against this spec; UTBMap port count ≤15.
- **Stage 5:** macrecovery downloads complete + checksums; USB layout correct.
- **Hardware (user):** boot → install → per-device checklist in `INSTALL.md`. Iterate on reported failures using systematic-debugging.

Everything up to and including `ocvalidate` is verifiable on this Linux box now. Boot/install verification is the user's hardware step; the plan treats their reported symptoms as the test signal for iteration.

---

## 7. Deliverables

1. `tools/gen_report_latitude5310.py` + generated `SysReport/Report.json` + `SysReport/ACPI/`.
2. `Results/EFI/` — tuned OpenCore EFI for Tahoe 26.
3. `tools/` helper(s) for the install kit (macrecovery wrapper / USB layout).
4. `docs/.../INSTALL.md` — BIOS settings, USB prep, install walkthrough, dual-boot, post-install (OCLP), WiFi/audio fallbacks, per-device verification checklist.
5. Honest status report of what is verified-on-Linux vs. pending-hardware.
