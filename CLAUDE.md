# CLAUDE.md — OpCore-Simplify (fork: anrdart) + Dell Latitude 5310 EFI

Konteks buat AI berikutnya. Dua hal hidup di repo ini:
1. **Upstream OpCore-Simplify** (tool generik bikin OpenCore EFI otomatis) — di `Scripts/`.
2. **Kerjaan kustom Latitude 5310** (bikin EFI macOS Sequoia 15 buat 1 laptop spesifik) — di `tools/`, `SysReport/`, `efi-builds/`.

User (anrdart / ekalliptus) bahasa Indonesia. Mesin = Dell Latitude 5310 yang lagi jalanin CachyOS Linux; semua kerjaan EFI dilakukan **dari Linux, tanpa Mac/Windows**.

---

## 1. Upstream tool (jangan diubah kecuali perlu)

`Scripts/` = OpCore-Simplify asli (lzhoang2801). Menu-driven, baca `Report.json` + ACPI dump → generate `Results/EFI/`. Alur: `OpCore-Simplify.py` → compatibility_checker → hardware_customizer → acpi_guru (SSDT via iasl) → kext_maestro → config_prodigy → smbios. `updater.py` self-update dari GitHub (jangan taruh kerjaan kustom di `Scripts/`, bisa ke-clobber).

Catatan: 4 file di `Scripts/` (config_prodigy, dsdt, resource_fetcher, utils) ada modifikasi minor lokal. `iasl` + `macserial.linux` ada di `Scripts/` (auto-download, gitignored).

---

## 2. Kerjaan Latitude 5310 — pipeline kustom (`tools/`)

Semua **reproducible**, jalan dari repo root:

- **`tools/gen_report_latitude5310.py`** — tulis `SysReport/Report.json` (hardware report 1 mesin ini). Fix 4 bug vs versi awal: chipset HARUS persis `"Comet Lake"` (IntelChipsets[112]), Input Device-Type harus mengandung `"PS/2"`/`"I2C"` (biar kext_maestro nambah VoodooPS2/VoodooI2CHID), CPU Codename `"Comet Lake-U"`, jangan kasih ACPI Path ke Network/Storage (biar dapat built-in=01 → iServices + internal disk).
- **`tools/build_latitude5310.py`** — driver headless. Rekonstruksi OCPE dari `OpCore-Simplify.py` (nama ada hyphen, nggak importable; strip `__main__`), feed jawaban canned. Var penting di atas file: `WIFI_CHOICE` ("1"=AirportItlwm native, "2"=itlwm+HeliPort), `MACOS_VERSION="24.0.0"` (Sequoia), `AUDIO_LAYOUT="77"`. **GOTCHA: build hapus seluruh isi `Results/` (`create_folder remove_content=True`) — simpan artifact di luar `Results/`, mis. `efi-builds/`.**
- **`tools/tune_latitude5310.py`** — override per-device terverifikasi (idempotent, backup `config.plist.orig`). INI inti semua fix. Lihat bagian 4.
- **`tools/ssdt/SSDT-GPRW.aml`** — SSDT instant-wake fix (di-compile dari source, di-copy ke EFI ACPI oleh tune).

ACPI tables udah di-dump di `SysReport/ACPI/` (DSDT + SSDT1-8, extensionless tapi tool baca by 4-byte sig). Dump butuh root: `sudo cp /sys/firmware/acpi/tables/{DSDT,SSDT*} ...`.

### Build 2 versi (ada di `efi-builds/`, gitignored):
- **`efi-builds/EFI-itlwm`** — WiFi via itlwm + HeliPort app. Anti-rusak, survive update macOS, NO OCLP. HeliPort.dmg v1.5.0 ada di `Results/macOS-apps/`.
- **`efi-builds/EFI-native`** — WiFi native AirportItlwm. Butuh OCLP root patch. **INI yang sekarang dipakai user.**

Rebuild satu versi: edit `WIFI_CHOICE` di build driver → `python3 tools/build_latitude5310.py` → `python3 tools/tune_latitude5310.py` → set csr 03080000 → copy ke `efi-builds/`.

---

## 3. Hardware Latitude 5310 (verified)

i5-10210U Comet Lake-U (CPUID 0x806EC = U62), UHD 620 (8086:9B41), ALC3254/ALC295 (10EC:0295), Intel AX201 WiFi+BT (8086:02F0 / 8087:0026), I219-V LAN (8086:0D4F), Comet Lake AHCI SATA SSD (KYO, no NVMe), RTS525A card reader (10EC:525A), DELL099F I2C trackpad (di ACPI TPD1, addr 0x2C, I2C1), eDP 1366×768. SMBIOS = **MacBookPro16,3** (tier 15W-quad Dortania; bukan arsitektur — nggak ada Mac Comet Lake). BIOS 1.19. CFG-Lock di-handle `AppleXcpmCfgLock=true`.

Disk: single SATA SSD. `sda1`=ESP (vfat, mount /boot di Linux, ada `EFI/limine` bootloader Linux + sekarang `EFI/OC` OpenCore), `sda2`=btrfs Linux root, `sda3`=APFS macOS Sequoia (~192GB, dibuat via `diskutil addPartition disk0s2 APFS macOS 0b` — Linux UTUH, dual-boot aman).

---

## 4. Fix terverifikasi (semua di `tune_latitude5310.py`) + status

Tiap fix hasil riset adversarial (banyak workflow). Referensi EFI teruji: **github.com/apollohackintosh/Dell-5310-Hackintosh** (Ventura/Sonoma, itlwm) + amane1234/Latitude-5410.

| Fix | Detail | Status hardware |
|-----|--------|-----------------|
| **CPU PM (lag/kipas/baterai)** | `Cpuid1Data=ec060800...` / `Cpuid1Mask=ffffffff...` (U62→U42 XCPM spoof). AKAR dari lag+fan+battery. | ✅ `sysctl machdep.xcpm.mode=1` confirmed |
| **Backlight** | boot-arg `-igfxblt` (apollo pakai; tanpa ini panel redup). + iGPU block A53E0000. | ✅ fixed |
| **iGPU** | `AAPL,ig-platform-id=0900a53e` + `device-id=a53e0000` + framebuffer-con0/1/2 + backlight-registers-fix. Proven 5310 block. JANGAN 9b3e0000 (mismatch fb). | ✅ accel jalan |
| **Audio** | AppleALC layout-id **77** (Dell 5290 ALC295). | ✅ |
| **Ethernet** | IntelMausi, native. | ✅ |
| **Fan readout** | SMCDellSensors (di-copy dari VirtualSMC bundle; tool skip krn nama mobo nggak persis "DELL"). | ✅ |
| **WiFi native** | AirportItlwm Ventura + IOSkywalkFamily + IO80211FamilyLegacy + AMFIPass + Block IOSkywalk Exclude. csr **03080000** (BUKAN 030A0000=NVIDIA-only). **Butuh OCLP root patch**. | ✅ JALAN (lihat resep ↓) |
| **Sleep** | ACPI patch GPRW→XPRW (`4750525702`→`5850525702`) + SSDT-GPRW (neuter USB GPE 0x6D wake). DSDT pakai Method(GPRW,2). | 🔧 belum di-test (tutup lid 30s) |
| **Trackpad** | force-polling di `PciRoot(0x0)/Pci(0x15,0x1)`. VoodooI2C **2.9.1** (JANGAN 2.8 — beku Sequoia #552). JANGAN AlpsHID (DELL099F=HID precision). | 🔧 usable tapi belum smooth |
| **Card reader** | Sinetek-rtsx (stale, opsional). | ✅ acceptable |
| **Dibuang** | AlpsHID.kext, XHCI-unsupported.kext, VoodooPS2Mouse/Trackpad plugins (disabled). | ✅ |

### Resep WiFi native yang BERHASIL (penting, beda dari dugaan awal):
1. Deploy EFI-native dengan **spoof BCM4360 LENGKAP** (IOName pci14e4,43a0 + device-id a0430000 + vendor-id e4140000 + model). Spoof bikin OCLP (Dortania biasa, Broadcom-only) **deteksi** AX201 sebagai Broadcom.
2. Jalanin **OCLP biasa (Dortania 2.4.1)** → Post-Install Root Patch → Start Root Patching. **Payload bundled, NO internet needed.** Reboot.
3. **BUANG SEMUA spoof** dari config (sisakan built-in=01). AirportItlwm match AX201 asli (0x02F08086).
4. Reboot → WiFi connect.
- **KEEP semua kext post-patch** (AirportItlwm butuh IO80211FamilyLegacy yang di-inject; jangan dibuang).
- Root patch DIES tiap update macOS → re-run OCLP. Makanya user mau update diblok (`Results/block_macos_updates.sh`).

### Trackpad — temuan penting (jangan buang waktu):
- ioreg confirmed: **cuma 1 VoodooI2CHIDDevice** nempel ke TPD1. TPD0 udah mati by firmware (gate `I2C1.I2CN==0` permanen). "Magic Trackpad 2" + "(unknown)" di LinearMouse = presentasi VoodooI2C normal, BUKAN driver double. **Jangan bikin SSDT disable TPD0 (no-op).**
- Jitter = kurva akselerasi macOS + force-polling sampling. Ceiling: nggak bisa se-mulus libinput Linux. Fix terbaik = **LinearMouse** (akselerasi flat, no reboot). Interrupt mode (buang force-polling) udah pernah gagal (lag) — opsional gamble, gampang revert.

---

## 5. Deploy & lokasi penting

- OpenCore live di **ESP internal `/boot/EFI/OC`** (lepas dari USB). NVRAM entry `Boot0001 OpenCore` → `\EFI\OC\OpenCore.efi` (dibuat via `Misc/Boot/LauncherOption=Short`). `efibootmgr -o 0001,0000` (OpenCore dulu, Limine fallback).
- **Deploy = copy dari Linux:** `sudo cp -r efi-builds/EFI-native/OC /boot/EFI/OC`. JANGAN sentuh `/boot/EFI/BOOT` (= Limine BOOTX64.EFI) atau `/boot/EFI/limine`.
- Edit config bisa juga langsung di macOS (mount EFI: `sudo diskutil mount disk0s1`).
- Dell firmware gotcha: USB OpenCore boot kadang jatuh ke ePSA Diagnostics — fix `LauncherOption=Short` + Secure Boot OFF + USB Boot Support ON.

---

## 6. Keamanan / yang JANGAN dipublish (gitignored)

`Results/`, `efi-builds/`, `SysReport/`, `screenshoot/`, `scratch/` di-gitignore. Berisi: **SMBIOS serial/MLB/UUID asli**, **WiFiConfig itlwm (SSID + password WiFi user)**, hardware report, foto layar. JANGAN pernah commit/push ini. Sebelum push apa pun ke GitHub (anrdart/OpCore-Simplify), scan: `git add -A --dry-run | grep -iE "Results|efi-builds|SysReport|config.plist"` harus kosong.

---

## 7. Gaya kerja yang dipakai

- Riset device-specific fragile pakai **Workflow tool** (multi-agent + adversarial verify) — JANGAN nebak config Hackintosh, banyak yang counter-intuitive (contoh: "buang spoof" vs "double-load" vs "version mismatch" — semua salah kecuali yang terverifikasi).
- Verifikasi runtime dari macOS (ioreg/kextstat/sysctl/log show) ngalahkan analisa config — minta user foto hasil.
- Bolak-balik Linux↔macOS lama buat user — minimalkan reboot, batch perubahan, siapin config sebelum minta deploy.
- Operasi irreversible (partisi, /boot) — selalu konfirmasi + verifikasi dulu, jangan asumsi user udah jalanin command.

Memory tambahan: `~/.claude/projects/-home-ekalliptus-dev-OpCore-Simplify/memory/` (latitude-5310-efi, latitude-5310-device-quirks, latitude-5310-macos-update-block).
