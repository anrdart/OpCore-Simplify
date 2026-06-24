#!/usr/bin/env python3
"""
Hand-tune the freshly-built Results/EFI for the Latitude 5310 on Sequoia.

Applies the adversarially-verified device-specific overrides that OpCore-Simplify
cannot get right blind. Idempotent: safe to re-run. Operates in place on
Results/EFI. A backup of config.plist is written next to it once.

Overrides (see tools/ research + apollohackintosh/Dell-5310-Hackintosh):
  1. iGPU: align to the proven Latitude-5310 framebuffer block
     (platform-id 0900A53E + device-id A53E0000 + eDP connector data +
      backlight-registers-fix). The tool emitted device-id 9B3E0000 which
      mismatches the 0900A53E framebuffer.
  2. Remove AlpsHID.kext  (DELL099F is a standard HID precision touchpad,
     handled by VoodooI2CHID; AlpsHID is for Alps I2C pads).
  3. Disable VoodooPS2Mouse + VoodooPS2Trackpad plugins (I2C trackpad drives
     pointer; keep only the PS2 keyboard plugin).
  4. Remove XHCI-unsupported.kext (CometLake xHCI works natively; USB is mapped
     via USBToolBox/UTBDefault placeholder, finalize on-hardware).
  5. boot-args: drop -igfxblt (CometLake needs no backlight boot-arg; backlight
      is handled by the framebuffer fix). Add -vi2c-force-polling with
      VoodooI2C's DEFAULT poll interval — this is the proven working baseline
      for the DELL099F trackpad. Do NOT override the interval (a 2 ms override
      caused trackpad stutter).
"""
import os
import plistlib
import shutil

# Tune script is bidirectional: it can also patch the live
# efi-builds/EFI-<variant>/OC tree. We pick the path that exists; if both
# exist we patch Results (the canonical build output) and the caller is
# expected to copy it into efi-builds/ after re-running.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
EFIB_ROOT = os.path.join(REPO_ROOT, "efi-builds")
RESULTS_EFI = os.path.join(REPO_ROOT, "Results", "EFI")

# Prefer Results/EFI (post-build, the canonical state). Fall back to
# efi-builds/EFI-native/OC (the currently-deployed tree) so the script is
# also useful for hot-patching a live EFI without re-running the build.
if os.path.isdir(RESULTS_EFI):
    EFI = RESULTS_EFI
elif os.path.isdir(os.path.join(EFIB_ROOT, "EFI-native")):
    EFI = os.path.join(EFIB_ROOT, "EFI-native")
elif os.path.isdir(os.path.join(EFIB_ROOT, "EFI-itlwm")):
    EFI = os.path.join(EFIB_ROOT, "EFI-itlwm")
else:
    raise SystemExit(
        "No EFI tree found. Build first (python3 tools/build_latitude5310.py) "
        "or deploy a copy to efi-builds/EFI-native/."
    )
OC = os.path.join(EFI, "OC")
CONFIG = os.path.join(OC, "config.plist")
KEXTS = os.path.join(OC, "Kexts")
print("tuning: {}".format(EFI))

IGPU_PATH = "PciRoot(0x0)/Pci(0x2,0x0)"

# DELL099F trackpad = Synaptics 0x044E:0x120A behind I2C#1.
# macOS pointer pipeline adds 5-15 ms baseline latency vs Linux libinput's
# 1-3 ms (4 layers vs 2) — this is the source of perceived "jitter" on
# i5-10210U. Counter-measures: enable VoodooI2C force-polling via the
# global boot-arg (default interval), drop macOS palm-rejection debounce.
#
# HISTORY: a previous revision set polling-interval=2 (500 Hz) both as a
# DeviceProperties per-controller key AND a vi2c-force-poll-interval=2
# boot-arg, which made the DELL099F trackpad choppy/stuttery. The proven
# working baseline (EFIdulu) uses the bare -vi2c-force-polling boot-arg
# with VoodooI2C's default interval — so we reverted to that and do NOT
# override the interval at all.
TRACKPAD_QUIET_TIME_MS = 150

# Proven Latitude 5310 iGPU block (from apollohackintosh/Dell-5310-Hackintosh,
# tested on this exact model). Bytes are little-endian as stored in plist.
IGPU_BLOCK = {
    "AAPL,ig-platform-id": bytes.fromhex("0900a53e"),
    "device-id": bytes.fromhex("a53e0000"),
    "framebuffer-patch-enable": bytes.fromhex("01000000"),
    "framebuffer-stolenmem": bytes.fromhex("00003001"),
    "framebuffer-con0-enable": bytes.fromhex("01000000"),
    "framebuffer-con0-alldata": bytes.fromhex("000008000200000098000000"),
    "framebuffer-con1-enable": bytes.fromhex("01000000"),
    "framebuffer-con1-alldata": bytes.fromhex("0101090000080000c7010000"),
    "framebuffer-con2-enable": bytes.fromhex("01000000"),
    "framebuffer-con2-alldata": bytes.fromhex("02060a0000040000c7010000"),
    "enable-backlight-registers-fix": bytes.fromhex("01000000"),
}

REMOVE_KEXTS = ("AlpsHID.kext", "XHCI-unsupported.kext")
DISABLE_PS2_PLUGINS = ("VoodooPS2Mouse.kext", "VoodooPS2Trackpad.kext")
NVRAM_GUID = "7C436110-AB2A-4BBB-A880-FE41995C9F82"

# I2C controller #1 (the trackpad bus). apollo's proven 5310 EFI sets
# force-polling here to smooth the DELL099F trackpad. VoodooI2C 2.9.1 on Sequoia
# runs interrupt mode but with high GPIO latency (controller busy ~1419ms ->
# laggy). force-polling is reversible; if it makes things worse just remove it.
I2C1_PATH = "PciRoot(0x0)/Pci(0x15,0x1)"

# Complete BCM4360 spoof so OCLP (stock, Broadcom-only patchset) DETECTS the
# AX201 as a Broadcom card and offers the legacy-WiFi root patch. IOName alone
# is NOT enough -> OCLP greys out / "no patches required". Only applied to the
# AirportItlwm (native) build; the itlwm build leaves the WiFi device plain.
BCM4360_SPOOF = {
    "IOName": "pci14e4,43a0",
    "device-id": bytes.fromhex("a0430000"),
    "vendor-id": bytes.fromhex("e4140000"),
    "compatible": "pci14e4,43a0",
    "name": "pci14e4,43a0",
    "model": "Broadcom BCM4360 802.11ac Wireless",
    "built-in": bytes.fromhex("01"),
}

# i5-10210U = Comet Lake U62 (CPUID 0x806EC); macOS has no native U62 power
# profile -> XCPM fails -> CPU stuck on bad P-states -> lag + odd fan + battery
# drain ALL cascade from this. Spoof U62->U42 so XCPM loads. Verified identical
# in apollo's working 5310 config and Dortania coffee-lake-plus.
CPUID1DATA = bytes.fromhex("ec060800" + "00" * 12)
CPUID1MASK = bytes.fromhex("ffffffff" + "00" * 12)

# SMCDellSensors = fan RPM + temp readout on Dell Latitude (SMM-gated; SMCSuperIO
# alone reads garbage). apollo ships it alongside the other SMC plugins, no
# conflict. Source kext lives in the VirtualSMC bundle in the download cache.
ADD_KEXTS = ("SMCDellSensors",)
OCK_DIR = os.path.join(REPO_ROOT, "OCK_Files")


def main():
    if not os.path.exists(CONFIG):
        raise SystemExit("config.plist not found at {} — run the build first".format(CONFIG))

    backup = CONFIG + ".orig"
    if not os.path.exists(backup):
        shutil.copy2(CONFIG, backup)
        print("backed up original ->", backup)

    with open(CONFIG, "rb") as f:
        c = plistlib.load(f)

    changes = []

    # 0. LauncherOption=Short so OpenCore registers its own UEFI boot entry in
    #    firmware NVRAM. Dell Latitude firmware often won't boot the bare
    #    \EFI\BOOT\BOOTX64.EFI fallback cleanly (falls through to ePSA
    #    Diagnostics); a real NVRAM entry fixes that.
    boot = c.setdefault("Misc", {}).setdefault("Boot", {})
    if boot.get("LauncherOption") != "Short":
        boot["LauncherOption"] = "Short"
        changes.append("Misc/Boot/LauncherOption -> Short (register UEFI boot entry on Dell)")

    # 1. iGPU framebuffer block
    dp = c.setdefault("DeviceProperties", {}).setdefault("Add", {})
    dp[IGPU_PATH] = dict(IGPU_BLOCK)
    changes.append("iGPU -> proven 5310 framebuffer block (device-id A53E0000 + connectors + backlight fix)")

    # 1b. Trackpad force-polling on I2C controller #1. The proven working
    #     baseline uses VoodooI2C's DEFAULT poll interval, so we only set the
    #     force-polling flag here and deliberately do NOT override
    #     polling-interval (overriding it to 2 ms caused the trackpad to
    #     stutter). The matching -vi2c-force-polling boot-arg is added in step 5.
    if dp.get(I2C1_PATH, {}).get("force-polling") != bytes.fromhex("01000000"):
        dp.setdefault(I2C1_PATH, {})["force-polling"] = bytes.fromhex("01000000")
        changes.append("I2C1 force-polling=01 (trackpad lag fix, default interval, reversible)")
    # Remove any previously-injected polling-interval override (legacy tune run).
    if "polling-interval" in dp.get(I2C1_PATH, {}):
        dp[I2C1_PATH].pop("polling-interval", None)
        changes.append("I2C1 polling-interval removed (default interval restored — fixes trackpad stutter)")

    # 1c. Complete BCM4360 spoof — ONLY for the AirportItlwm (native) build so
    #     stock OCLP detects a Broadcom card and offers the WiFi root patch.
    #     Idempotent: skip if the config is already in the post-OCLP state
    #     (no spoof keys, only built-in=01). The spoof is one-way: once OCLP
    #     has run and the user removed it, this script will NOT re-add it.
    is_native = any("AirportItlwm" in k.get("BundlePath", "") for k in c["Kernel"]["Add"])
    wifi_path = "PciRoot(0x0)/Pci(0x14,0x3)"
    if is_native:
        existing = dp.get(wifi_path, {})
        has_spoof = "device-id" in existing or "vendor-id" in existing
        is_post_oclp = existing.get("built-in") and not has_spoof
        if is_post_oclp:
            changes.append("WiFi: post-OCLP state detected (built-in only), leaving spoof removed")
        else:
            spoof = dict(BCM4360_SPOOF)
            dp[wifi_path] = spoof
            changes.append("WiFi BCM4360 spoof COMPLETE (device-id/vendor-id/model) for OCLP detection")

    # 2 & 4. remove kexts from disk + Kernel>Add
    add = c["Kernel"]["Add"]
    kept = []
    for entry in add:
        bp = entry.get("BundlePath", "")
        top = bp.split("/")[0]
        if top in REMOVE_KEXTS:
            changes.append("removed kext entry: {}".format(bp))
            continue
        # 3. disable PS2 mouse/trackpad plugins
        leaf = os.path.basename(bp)
        if leaf in DISABLE_PS2_PLUGINS and entry.get("Enabled"):
            entry["Enabled"] = False
            changes.append("disabled plugin: {}".format(bp))
        kept.append(entry)
    c["Kernel"]["Add"] = kept

    for k in REMOVE_KEXTS:
        kpath = os.path.join(KEXTS, k)
        if os.path.isdir(kpath):
            shutil.rmtree(kpath)
            changes.append("deleted {} from Kexts/".format(k))

    # 5. boot-args:
    #    - ensure -igfxblt present (apollo's proven 5310 EFI uses it; without it
    #      the panel backlight stays dim on Comet Lake). CONFIRMED working.
    #    - ADD -vi2c-force-polling: the proven working baseline (EFIdulu) drives
    #      the DELL099F I2C trackpad via force-polling at VoodooI2C's DEFAULT
    #      interval and the trackpad was smooth. Do NOT add a
    #      vi2c-force-poll-interval override: a 2 ms override made the trackpad
    #      stutter (this is what we are fixing). Reversible: if trackpad dies,
    #      drop the arg.
    #    - DROP -v and debug=0x100: development flags that slow boot and add
    #      console noise. keepsyms=1 is kept for panic decoding.
    nv = c["NVRAM"]["Add"][NVRAM_GUID]
    ba = nv.get("boot-args", "")
    drop = {"-v", "debug=0x100"}
    toks = [t for t in ba.split()
            if t not in drop and not t.startswith("vi2c-force-poll-interval")]
    if "-igfxblt" not in toks:
        toks.append("-igfxblt")
    if "-vi2c-force-polling" not in toks:
        toks.append("-vi2c-force-polling")
    new_ba = " ".join(toks)
    if new_ba != ba:
        nv["boot-args"] = new_ba
        changes.append("boot-args: {!r} -> {!r}".format(ba, new_ba))

    # 5b. Sleep: GPRW->XPRW rename + SSDT-GPRW (neuter USB GPE 0x6D / bridge 0x0D
    #     wake for Darwin). DSDT confirmed to use Method(GPRW,2). Rename alone
    #     would break Win/Linux, so SSDT-GPRW (defines GPRW calling XPRW) ships
    #     alongside. SSDT-GPRW.aml must be placed in ACPI/ (done below from /tmp
    #     or tools/ssdt/).
    acpi = c.setdefault("ACPI", {})
    patches = acpi.setdefault("Patch", [])
    if not any(p.get("Comment", "").startswith("GPRW to XPRW") for p in patches):
        patches.append({
            "Comment": "GPRW to XPRW - instant wake fix",
            "Enabled": True,
            "Find": bytes.fromhex("4750525702"),     # GPRW\x02
            "Replace": bytes.fromhex("5850525702"),  # XPRW\x02
            "Count": 0, "Limit": 0,
            "OEMTableId": b"", "TableLength": 0, "TableSignature": b"",
        })
        changes.append("ACPI Patch: GPRW->XPRW instant-wake fix")
    # ensure SSDT-GPRW in ACPI/Add
    adds = acpi.setdefault("Add", [])
    if not any(a.get("Path") == "SSDT-GPRW.aml" for a in adds):
        adds.append({"Comment": "SSDT-GPRW", "Enabled": True, "Path": "SSDT-GPRW.aml"})
        changes.append("ACPI Add: SSDT-GPRW.aml")
    # copy the compiled SSDT-GPRW.aml into the EFI ACPI dir
    ssdt_src_candidates = [
        os.path.join(REPO_ROOT, "tools", "ssdt", "SSDT-GPRW.aml"),
        "/tmp/SSDT-GPRW.aml",
    ]
    acpi_dir = os.path.join(OC, "ACPI")
    dst_ssdt = os.path.join(acpi_dir, "SSDT-GPRW.aml")
    if not os.path.exists(dst_ssdt):
        for s in ssdt_src_candidates:
            if os.path.exists(s):
                shutil.copy2(s, dst_ssdt)
                changes.append("copied SSDT-GPRW.aml into EFI/OC/ACPI")
                break

    # 6. CPUID U62->U42 spoof (THE fix for lag/fan/battery — XCPM power mgmt).
    em = c["Kernel"]["Emulate"]
    if em.get("Cpuid1Data") != CPUID1DATA:
        em["Cpuid1Data"] = CPUID1DATA
        em["Cpuid1Mask"] = CPUID1MASK
        changes.append("Kernel/Emulate Cpuid1Data -> ec060800... (U62->U42 XCPM spoof)")
    em["DummyPowerManagement"] = False

    # 7. SMCDellSensors for fan/temp readout. Copy from cache + add to Kernel>Add.
    add_list = c["Kernel"]["Add"]
    present = {os.path.basename(e.get("BundlePath", "")) for e in add_list}
    for name in ADD_KEXTS:
        kfile = name + ".kext"
        if kfile in present:
            continue
        # locate source in OCK_Files cache
        src = None
        for root, dirs, _ in os.walk(OCK_DIR):
            if kfile in dirs:
                src = os.path.join(root, kfile)
                break
        if not src:
            changes.append("WARN: {} not found in cache, skipped".format(kfile))
            continue
        dst = os.path.join(KEXTS, kfile)
        if not os.path.isdir(dst):
            shutil.copytree(src, dst)
        # build Kernel>Add entry (mirror an existing SMC plugin's structure)
        exe = os.path.join(dst, "Contents", "MacOS", name)
        add_list.append({
            "Arch": "Any",
            "BundlePath": kfile,
            "Comment": "",
            "Enabled": True,
            "ExecutablePath": "Contents/MacOS/{}".format(name) if os.path.exists(exe) else "",
            "MaxKernel": "",
            "MinKernel": "",
            "PlistPath": "Contents/Info.plist",
        })
        changes.append("added {} (fan/temp readout)".format(kfile))

    # 8. HibernateMode = Auto: on a laptop, full battery drain with Hibernate
    #    = None loses the in-RAM session. Auto writes a hibernate image at
    #    critical battery and resumes from it on next boot. No downside for
    #    a working EFI.
    if boot.get("HibernateMode") != "Auto":
        boot["HibernateMode"] = "Auto"
        changes.append("Misc/Boot/HibernateMode -> Auto (preserve session on battery drain)")

    # 9. VoodooI2CHID QuietTimeAfterTyping: drop from 500 ms default to
    #    TRACKPAD_QUIET_TIME_MS so the trackpad becomes responsive faster
    #    after a typing burst. The Precision Touchpad driver (which handles
    #    DELL099F, HID UsagePage 13 Usage 5) reads this property.
    vi2c_hid_info = os.path.join(KEXTS, "VoodooI2CHID.kext", "Contents", "Info.plist")
    if os.path.isfile(vi2c_hid_info):
        with open(vi2c_hid_info, "rb") as f:
            vi = plistlib.load(f)
        pers = vi.get("IOKitPersonalities", {})
        ptd = pers.get("VoodooI2CHIDDevice Precision Touchpad HID Event Driver")
        if ptd is not None and ptd.get("QuietTimeAfterTyping") != TRACKPAD_QUIET_TIME_MS:
            ptd["QuietTimeAfterTyping"] = TRACKPAD_QUIET_TIME_MS
            with open(vi2c_hid_info, "wb") as f:
                plistlib.dump(vi, f)
            changes.append(
                "VoodooI2CHID QuietTimeAfterTyping -> {} ms (faster post-typing resume)".format(
                    TRACKPAD_QUIET_TIME_MS
                )
            )

    with open(CONFIG, "wb") as f:
        plistlib.dump(c, f)

    print("\nApplied {} change(s):".format(len(changes)))
    for ch in changes:
        print("  -", ch)
    print("\nTuned config written:", CONFIG)


if __name__ == "__main__":
    main()
