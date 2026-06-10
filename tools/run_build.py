import os
import subprocess
import time
import sys
import re

# Regex to strip ANSI escape codes
ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
def strip_ansi(text):
    return ansi_escape.sub('', text)

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    report_path = os.path.join(base_dir, "SysReport", "Report.json")
    acpi_path = os.path.join(base_dir, "SysReport", "ACPI")
    
    print("Launching OpCore-Simplify interactive build...")
    print(f"Project directory: {base_dir}")
    print(f"Report path: {report_path}")
    print(f"ACPI path: {acpi_path}")
    
    process = subprocess.Popen(
        [sys.executable, "OpCore-Simplify.py"],
        cwd=base_dir,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    has_selected_report = False
    has_started_build = False
    has_finished_build = False
    buffer = ""
    
    while True:
        char = process.stdout.read(1)
        if not char:
            break
        
        sys.stdout.write(char)
        sys.stdout.flush()
        buffer += char
        
        clean_buf = strip_ansi(buffer)
        
        # Check for specific prompt matches in clean_buf
        is_prompt = False
        val_to_send = None
        
        if clean_buf.endswith("Select an option: "):
            is_prompt = True
            if not has_selected_report:
                val_to_send = "1"
                has_selected_report = True
            elif not has_started_build:
                val_to_send = "6"
                has_started_build = True
            else:
                val_to_send = "q"
        elif "Drag and drop your hardware report here" in clean_buf and clean_buf.endswith(": "):
            is_prompt = True
            val_to_send = report_path
        elif clean_buf.endswith("Press Enter to continue..."):
            is_prompt = True
            val_to_send = ""
        elif clean_buf.endswith("Press Enter to go back..."):
            is_prompt = True
            val_to_send = ""
        elif clean_buf.endswith("Press Enter to main menu..."):
            is_prompt = True
            val_to_send = ""
            has_finished_build = True
        elif clean_buf.strip().endswith("Press Enter to exit."):
            is_prompt = True
            val_to_send = ""
        elif "Please enter the macOS version you want to use" in clean_buf and (clean_buf.endswith(": ") or clean_buf.endswith("): ")):
            is_prompt = True
            val_to_send = "24"
        elif clean_buf.endswith("Please drag and drop ACPI Tables folder here: "):
            is_prompt = True
            val_to_send = acpi_path
        elif "Select kext for your Intel WiFi device" in clean_buf and clean_buf.endswith(": "):
            is_prompt = True
            val_to_send = ""
        elif "Do you want to force load" in clean_buf and clean_buf.endswith("No): "):
            is_prompt = True
            val_to_send = "yes"
        elif "continue with OpenCore Legacy Patcher? (yes/No): " in clean_buf:
            is_prompt = True
            val_to_send = "yes"
        elif "Would you like to scan for WiFi profiles? (Yes/no):" in clean_buf.strip():
            is_prompt = True
            val_to_send = "no"
        elif "Enter the ID of the codec layout you want to use" in clean_buf and (clean_buf.endswith(": ") or clean_buf.endswith("): ")):
            is_prompt = True
            val_to_send = "77"
            
        if is_prompt:
            print(f"\n[AUTOMATION] Sending prompt response: {repr(val_to_send)}")
            process.stdin.write(val_to_send + "\n")
            process.stdin.flush()
            buffer = ""
            
    process.wait()
    print("\nOpCore-Simplify automation complete!")

if __name__ == '__main__':
    main()
