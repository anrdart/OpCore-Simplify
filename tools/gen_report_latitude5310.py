#!/usr/bin/env python3
"""
Hardware report generator for Dell Latitude 5310 (this exact machine).

Emits SysReport/Report.json conforming to Scripts/report_validator.py and the
field semantics consumed by Scripts/{compatibility_checker,hardware_customizer,
kext_maestro,config_prodigy,smbios}.py.

This is a ONE-DEVICE tool. Verified IDs (detected on this Linux box):
  CPU   i5-10210U Comet Lake-U  family6 model142 stepping12  CPUID 55060A00
  iGPU  Intel UHD 620 (CometLake-U GT2)  8086:9B41  subsys 1028:099F
  Audio Realtek ALC3254/ALC295  HDA 10EC:0295  ctrlr 8086:02C8  subsys 1028:099F
  WiFi  Intel AX201 (CNVi)  8086:02F0  subsys 8086:4070
  BT    Intel AX201 BT (USB)  8087:0026
  LAN   Intel I219-V (10)  8086:0D4F
  xHCI  Comet Lake PCH-LP USB 3.1  8086:02ED
  SATA  Comet Lake AHCI  8086:02D3   (KYO 512GB SATA SSD, no NVMe)
  TPAD  Dell I2C precision touchpad  ACPI DELL099F  HID 044E:120A
  KBD   PS/2  PNP0303
  SD    Realtek RTS525A PCIe card reader  10EC:525A
  eDP   internal panel 1366x768

Design choices that make the tool behave correctly (see analysis):
  * Chipset MUST be exactly "Comet Lake" (it is IntelChipsets[112]) so the
    UEFI/Booter quirks lookups (DevirtualiseMmio/ProtectUefiServices/...) fire.
  * CPU Codename "Comet Lake-U" (IntelCPUGenerations[33]) for the index checks.
  * Input "Device Type" MUST contain "PS/2" / "I2C" so kext_maestro adds
    VoodooPS2Controller / VoodooI2CHID respectively.
  * No "ACPI Path" on Network / Storage / SD so config_prodigy injects
    built-in=01 (fixes iServices on Ethernet + internal-drive display).

ACPI tables are dumped separately (needs root) — see the printed command.
"""
import json
import os

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
OUT_DIR = os.path.join(REPO_ROOT, "SysReport")
ACPI_DIR = os.path.join(OUT_DIR, "ACPI")
OUT_FILE = os.path.join(OUT_DIR, "Report.json")

# Dell subsystem (subvendor 1028 / subdevice 099F) in subdevice+subvendor form.
DELL_SUBSYS = "0x099F1028"
IGPU_NAME = "Intel UHD Graphics"

report = {
    "Motherboard": {
        "Name": "Dell Inc. Latitude 5310",
        "Chipset": "Comet Lake",
        "Platform": "Laptop",
    },
    "BIOS": {
        "Version": "1.19.0",
        "Release Date": "03/13/2023",
        "System Type": "x64-based PC",
        "Firmware Type": "UEFI",
        "Secure Boot": "Disabled",
    },
    "CPU": {
        "Manufacturer": "Intel",
        "Processor Name": "Intel(R) Core(TM) i5-10210U CPU @ 1.60GHz",
        "Codename": "Comet Lake-U",
        "Core Count": "4",
        "CPU Count": "1",
        "SIMD Features": "SSE, SSE2, SSE3, SSSE3, SSE4.1, SSE4.2, AVX, AVX2, FMA3",
    },
    "GPU": {
        IGPU_NAME: {
            "Manufacturer": "Intel",
            "Codename": "Comet Lake",
            "Device ID": "8086-9B41",
            "Device Type": "Integrated GPU",
            "Subsystem ID": DELL_SUBSYS,
            "PCI Path": "PciRoot(0x0)/Pci(0x2,0x0)",
            "Resizable BAR": "Disabled",
        },
    },
    "Monitor": {
        "Internal Display": {
            "Connector Type": "eDP",
            "Resolution": "1366x768",
            "Connected GPU": IGPU_NAME,
        },
    },
    "Network": {
        # No ACPI Path -> config_prodigy injects built-in=01 (fixes iServices).
        "Intel Ethernet Connection (10) I219-V": {
            "Bus Type": "PCI",
            "Device ID": "8086-0D4F",
            "Subsystem ID": DELL_SUBSYS,
            "PCI Path": "PciRoot(0x0)/Pci(0x1f,0x6)",
        },
        "Intel Wi-Fi 6 AX201 160MHz": {
            "Bus Type": "PCI",
            "Device ID": "8086-02F0",
            "Subsystem ID": "0x40708086",
            "PCI Path": "PciRoot(0x0)/Pci(0x14,0x3)",
        },
    },
    "Sound": {
        "Realtek ALC3254 (ALC295)": {
            "Bus Type": "PCI",
            "Device ID": "10EC-0295",
            "Subsystem ID": DELL_SUBSYS,
            "Controller Device ID": "8086-02C8",
            "Audio Endpoints": ["Speaker", "Headphone", "Internal Microphone"],
        },
    },
    "System Devices": {
        # The cAVS/HDAS controller must be present with its PCI Path so
        # select_audio_codec_layout() can inject layout-id onto it.
        "Intel Smart Sound Technology Audio Controller": {
            "Bus Type": "PCI",
            "Device": "HDAS",
            "Device ID": "8086-02C8",
            "Subsystem ID": DELL_SUBSYS,
            "PCI Path": "PciRoot(0x0)/Pci(0x1f,0x3)",
        },
        "Intel Management Engine Interface": {
            "Bus Type": "PCI",
            "Device": "IMEI",
            "Device ID": "8086-02E0",
            "Subsystem ID": DELL_SUBSYS,
            "PCI Path": "PciRoot(0x0)/Pci(0x16,0x0)",
        },
    },
    "USB Controllers": {
        "Comet Lake PCH-LP USB 3.1 xHCI Controller": {
            "Bus Type": "PCI",
            "Device ID": "8086-02ED",
            "Subsystem ID": DELL_SUBSYS,
            "PCI Path": "PciRoot(0x0)/Pci(0x14,0x0)",
        },
    },
    "Input": {
        # Device Type MUST contain "PS/2" -> VoodooPS2Controller.
        "AT Translated Set 2 keyboard": {
            "Bus Type": "ACPI",
            "Device": "PNP0303",
            "Device Type": "PS/2 Keyboard",
        },
        # Device Type MUST contain "I2C" -> VoodooI2CHID (+ VoodooI2C dep).
        # Device DELL099F (InputIDs[61]) also pulls AlpsHID; we uncheck that in
        # the build step because this is a standard precision (HID) touchpad.
        "Dell I2C HID Touchpad": {
            "Bus Type": "ACPI",
            "Device": "DELL099F",
            "Device ID": "044E-120A",
            "Device Type": "I2C Device",
        },
    },
    "Storage Controllers": {
        # Name contains "AHCI" -> no extra SATA kext (native). No ACPI Path ->
        # built-in=01 injected so the SSD shows as internal.
        "Intel Comet Lake SATA AHCI Controller": {
            "Bus Type": "PCI",
            "Device ID": "8086-02D3",
            "Subsystem ID": DELL_SUBSYS,
            "PCI Path": "PciRoot(0x0)/Pci(0x17,0x0)",
            "Disk Drives": ["KYO 512GB SATA SSD"],
        },
    },
    "Bluetooth": {
        "Intel AX201 Bluetooth": {
            "Bus Type": "USB",
            "Device ID": "8087-0026",
        },
    },
    "SD Controller": {
        # 10EC-525A is RealtekCardReaderIDs[10] (>=5) -> tool selects
        # Sinetek-rtsx, which has no Sonoma cap (works on Sequoia).
        "Realtek RTS525A PCIe Card Reader": {
            "Bus Type": "PCI",
            "Device ID": "10EC-525A",
            "Subsystem ID": DELL_SUBSYS,
            "PCI Path": "PciRoot(0x0)/Pci(0x1d,0x0)/Pci(0x0,0x0)",
        },
    },
}


def main():
    os.makedirs(ACPI_DIR, exist_ok=True)
    with open(OUT_FILE, "w") as f:
        json.dump(report, f, indent=4)
    print("Wrote {}".format(OUT_FILE))
    print("")
    print("=" * 64)
    print("ACTION REQUIRED (needs root): dump ACPI tables")
    print("=" * 64)
    print("sudo sh -c 'cp /sys/firmware/acpi/tables/DSDT {0}/DSDT.aml; "
          "for f in /sys/firmware/acpi/tables/SSDT*; do "
          "cp \"$f\" {0}/$(basename \"$f\").aml; done; "
          "chown -R $SUDO_USER {1}'".format(ACPI_DIR, OUT_DIR))
    print("=" * 64)


if __name__ == "__main__":
    main()
