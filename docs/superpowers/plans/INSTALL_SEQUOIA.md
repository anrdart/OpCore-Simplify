# Panduan Instalasi macOS Sequoia — Dell Latitude 5310

Panduan ini berisi langkah-langkah untuk menyiapkan media instalasi macOS Sequoia, mengkonfigurasi BIOS, mempartisi disk secara aman (dual-boot dengan CachyOS Linux), dan melakukan konfigurasi post-install.

---

## 1. Konfigurasi BIOS Dell Latitude 5310

Sebelum memulai instalasi, pastikan pengaturan BIOS Anda sudah disesuaikan agar OpenCore dapat berjalan normal:

### Wajib Di-disable (Matikan):
* **Secure Boot** -> Disabled
* **Intel SGX** -> Disabled
* **SATA Operation** -> AHCI (Jika saat ini menggunakan RAID, harap ubah ke AHCI. *Peringatan: CachyOS mungkin memerlukan penyesuaian fstab jika diubah dari RAID ke AHCI*).
* **Fast Boot** -> Thorough (mencegah inisialisasi hardware yang terlewati).

### Wajib Di-enable (Aktifkan):
* **UEFI Boot** -> Enabled
* **VT-d** -> Enabled (Di-handle dengan aman di config.plist melalui `DisableIoMapper`).
* **USB Boot** -> Enabled

---

## 2. Membuat USB Installer macOS Sequoia di Linux

Karena Anda menggunakan Linux (CachyOS), Anda dapat membuat installer recovery resmi Apple menggunakan skrip `macrecovery` dari OpenCorePkg.

### Langkah-langkah:
1. Hubungkan flashdisk (minimal 4GB) ke laptop Anda.
2. Identifikasi nama drive flashdisk Anda (misalnya `/dev/sdX`):
   ```bash
   lsblk
   ```
3. Format flashdisk ke FAT32 dengan label `EFI`:
   ```bash
   sudo mkfs.vfat -F 32 -n "EFI" /dev/sdX1
   ```
4. Buat folder untuk mengunduh berkas recovery:
   ```bash
   mkdir -p ~/Downloads/macOS-installer && cd ~/Downloads/macOS-installer
   ```
5. Unduh skrip `macrecovery.py` langsung dari repositori resmi OpenCorePkg:
   ```bash
   curl -O https://raw.githubusercontent.com/acidanthera/OpenCorePkg/master/Utilities/macrecovery/macrecovery.py
   ```
6. Jalankan skrip berikut untuk mengunduh berkas recovery macOS 15 (Sequoia):
   ```bash
   python3 macrecovery.py -b Mac-827FAC58A8FDFA22 -m 00000000000000000 download
   ```
7. Setelah selesai, Anda akan mendapatkan folder `com.apple.recovery.boot`. Salin folder tersebut ke root dari flashdisk FAT32 Anda.
8. Salin folder `EFI` yang telah kita buat dari project ini ([Results/EFI](file:///home/ekalliptus/dev/OpCore-Simplify/Results/EFI)) ke root dari flashdisk Anda berdampingan dengan folder `com.apple.recovery.boot`.
9. Struktur akhir pada USB installer harus terlihat seperti ini:
   ```text
   USB (Root)
   ├── com.apple.recovery.boot/
   │   ├── BaseSystem.dmg
   │   └── BaseSystem.chunklist
   └── EFI/
       ├── BOOT/
       └── OC/
           ├── config.plist
           ├── ACPI/
           ├── Drivers/
           ├── Kexts/
           ├── Resources/
           └── Tools/
   ```

---

## 3. Skema Partisi Aman (Dual-Boot CachyOS)

PENTING: Jangan menghapus partisi EFI Linux (ESP) yang sudah ada. Kita akan meletakkan OpenCore berdampingan dengan bootloader Linux.

1. **Shrink Partisi Linux**:
   Gunakan alat GUI seperti `GParted` di CachyOS untuk memperkecil partisi sistem Linux Anda guna memberikan ruang kosong (unallocated space) sebesar minimal 50-80GB untuk macOS Sequoia.
2. **Biarkan Ruang Kosong Tersebut**:
   Jangan memformat ruang kosong tersebut di Linux. Kita akan memformatnya menjadi APFS langsung dari Disk Utility macOS Installer.

---

## 4. Proses Instalasi

1. Colokkan USB Installer, nyalakan laptop, dan tekan **F12** untuk masuk ke One-Time Boot Menu Dell.
2. Pilih USB flashdisk Anda di bawah kategori **UEFI**.
3. Menu OpenCore Boot Picker akan muncul. Pilih **macOS Recovery (external)** atau **BaseSystem**.
4. Setelah masuk ke Recovery:
   - Buka **Disk Utility**.
   - Pilih opsi **View -> Show All Devices** di pojok kiri atas.
   - Cari ruang kosong/unallocated space yang sudah Anda siapkan. Buat partisi baru dengan format **APFS** dan beri nama `macOS`.
   - Tutup Disk Utility, pilih **Reinstall macOS Sequoia**, lalu pilih partisi `macOS` sebagai tujuan instalasi.
5. Laptop akan melakukan restart beberapa kali selama proses instalasi. Setiap kali restart, tekan **F12** jika bootloader default Linux memotongnya, lalu pilih USB dan pilih entri **macOS Installer** di menu OpenCore Picker hingga instalasi selesai.

---

## 5. Konfigurasi Post-Install

Setelah masuk ke desktop macOS Sequoia untuk pertama kalinya, jalankan langkah-langkah berikut:

### A. Mengaktifkan WiFi (itlwm + HeliPort)
1. Driver WiFi `itlwm.kext` sudah aktif di EFI.
2. Untuk menghubungkan ke jaringan WiFi, Anda memerlukan aplikasi pembantu bernama **HeliPort**.
3. Unduh **HeliPort.dmg** dari halaman rilis resmi: [OpenIntelWireless/HeliPort](https://github.com/OpenIntelWireless/HeliPort/releases).
4. Pindahkan HeliPort ke folder `/Applications`, jalankan aplikasi tersebut, dan hubungkan ke WiFi Anda melalui menu bar.

### B. Akselerasi Grafis (OCLP Root Patching)
Karena Comet Lake GT2 iGPU tidak lagi didukung secara native di macOS Sequoia, kita perlu menggunakan **OpenCore Legacy Patcher (OCLP)** untuk mengembalikan akselerasi grafis (QE/CI):
1. Unduh rilis terbaru **OpenCore-Legacy-Patcher.app** dari GitHub (gunakan OCLP v3.0.0 atau yang lebih baru untuk macOS Sequoia).
2. Jalankan aplikasi OCLP di macOS Anda.
3. Klik **Post-Install Root Patch** -> **Start Root Patching**.
4. Ikuti instruksi di layar, masukkan kata sandi Anda, lalu lakukan restart setelah patch selesai diterapkan.
5. Setelah restart, grafis Anda akan terakselerasi penuh dengan visual transisi yang mulus.

### C. Memindahkan EFI ke Disk Internal (Dual-Boot Permanent)
Agar Anda dapat booting ke macOS/Linux tanpa mencolokkan USB:
1. Di macOS, mount partisi EFI internal Anda (ESP) dan partisi EFI di USB.
2. Buat folder baru bernama `OC` di dalam `EFI/` pada EFI internal Anda, lalu salin berkas dari `EFI/OC` di USB ke folder tersebut.
3. Partisi EFI internal Anda sekarang akan memiliki struktur:
   ```text
   EFI/
   ├── BOOT/
   ├── systemd/ (atau bootloader CachyOS)
   └── OC/
   ```
4. Di BIOS Dell, Anda dapat mendaftarkan boot file `/EFI/OC/OpenCore.efi` sebagai opsi boot pertama Anda. OpenCore akan mendeteksi bootloader Linux secara otomatis di picker menu berkat pengaturan `ScanPolicy = 0`.
