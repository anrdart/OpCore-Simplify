#!/usr/bin/env python3
"""
Non-interactive build driver for the Latitude 5310 EFI.

Replicates OpCore-Simplify.py OCPE.main() option-1 (select report) + option-6
(build) exactly, but feeds canned answers so it runs headless on Linux:
  * macOS version -> Sequoia (Darwin 24)
  * Intel WiFi kext -> itlwm (recommended/stable on Sequoia; AirportItlwm dead)
  * audio codec layout -> 77 (Dell Latitude 5290 ALC295 match)
  * WiFi profile scan -> no
  * force-load unsupported kexts -> no

Run from repo root:  python3 tools/build_latitude5310.py
Output: Results/EFI/
"""
import os
import sys
import io
import contextlib

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, REPO_ROOT)
os.chdir(REPO_ROOT)

from Scripts import utils  # noqa: E402


def build_ocpe():
    """Reconstruct the OCPE object from OpCore-Simplify.py without importing it
    (hyphenated filename, and its module runs the updater at import time)."""
    import types
    src_path = os.path.join(REPO_ROOT, "OpCore-Simplify.py")
    with open(src_path) as f:
        src = f.read()
    # Drop the __main__ block so importing doesn't launch the interactive loop.
    marker = "if __name__ == '__main__':"
    if marker in src:
        src = src.split(marker)[0]
    mod = types.ModuleType("ocpe_mod")
    mod.__file__ = src_path
    sys.modules["ocpe_mod"] = mod
    exec(compile(src, src_path, "exec"), mod.__dict__)
    return mod.OCPE()


MACOS_VERSION = "24.0.0"   # Sequoia
WIFI_CHOICE = "1"          # 2=itlwm+HeliPort (works WITHOUT internet/OCLP); 1=AirportItlwm (native menu, needs OCLP)
AUDIO_LAYOUT = "77"        # ALC295 Dell Latitude 5290


def make_responder(verbose=False):
    """Return a request_input replacement that answers prompts deterministically."""
    def responder(prompt="", *args, **kwargs):
        p = (prompt or "").lower()
        if "codec layout" in p:
            ans = AUDIO_LAYOUT
        elif "wifi profile" in p or "scan for wifi" in p or "would you like to scan" in p:
            ans = "no"
        elif "force load" in p:
            ans = "no"
        elif "intel wifi" in p or "select kext for your intel" in p:
            ans = WIFI_CHOICE
        elif "build efi for uefi" in p:
            ans = "yes"
        else:
            ans = ""  # Press-Enter / accept-default prompts
        if verbose and prompt:
            sys.stderr.write("[auto] {!r} -> {!r}\n".format(prompt[:70], ans))
        return ans
    return responder


def main():
    # Monkeypatch ALL request_input across the codebase (every module made its
    # own Utils() instance, but they share the class method).
    utils.Utils.request_input = staticmethod(make_responder(verbose=True))
    # Don't actually pop a file manager open at the end.
    utils.Utils.open_folder = lambda self, *a, **k: None

    # OpCore-Simplify.py has a hyphen (not importable) and runs an updater at
    # import-time, so we reconstruct OCPE here from the same Scripts modules.
    ocpe = build_ocpe()

    report_path = os.path.join(REPO_ROOT, "SysReport", "Report.json")
    acpi_dir = os.path.join(REPO_ROOT, "SysReport", "ACPI")

    print(">>> Loading hardware report:", report_path)
    hardware_report = ocpe.u.read_file(report_path)

    print(">>> Checking compatibility...")
    hardware_report, native_macos_version, ocl_patched_macos_version = \
        ocpe.c.check_compatibility(hardware_report)
    print("    native range:", native_macos_version, "| oclp:", ocl_patched_macos_version)

    macos_version = MACOS_VERSION
    print(">>> Target macOS:", macos_version)

    print(">>> Hardware customization...")
    customized_hardware, disabled_devices, needs_oclp = \
        ocpe.h.hardware_customization(hardware_report, macos_version)
    print("    needs_oclp:", needs_oclp, "| disabled:", list(disabled_devices.keys()))

    smbios_model = ocpe.s.select_smbios_model(customized_hardware, macos_version)
    print(">>> SMBIOS:", smbios_model)

    print(">>> Loading ACPI tables from", acpi_dir)
    ocpe.ac.read_acpi_tables(acpi_dir)
    if not ocpe.ac.ensure_dsdt():
        ocpe.ac.select_acpi_tables()

    print(">>> Selecting ACPI patches...")
    ocpe.ac.select_acpi_patches(customized_hardware, disabled_devices)
    checked_patches = [p.name for p in ocpe.ac.patches if p.checked]
    print("    ACPI patches:", checked_patches)

    print(">>> Selecting kexts...")
    needs_oclp = ocpe.k.select_required_kexts(
        customized_hardware, macos_version, needs_oclp, ocpe.ac.patches)
    ocpe.s.smbios_specific_options(
        customized_hardware, smbios_model, macos_version, ocpe.ac.patches, ocpe.k)
    checked_kexts = [kx.name for kx in ocpe.k.kexts if kx.checked]
    print("    kexts:", checked_kexts)

    print(">>> Downloading OpenCorePkg + kexts (needs internet)...")
    ocpe.o.gather_bootloader_kexts(ocpe.k.kexts, macos_version)

    print(">>> Building EFI...")
    ocpe.build_opencore_efi(
        customized_hardware, disabled_devices, smbios_model, macos_version, needs_oclp)

    print(">>> DONE. EFI at:", ocpe.result_dir)


if __name__ == "__main__":
    main()
