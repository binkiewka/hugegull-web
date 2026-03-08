#!/usr/bin/env python3
"""
HugeGull Interactive Setup Wizard
Helps users configure HugeGull on first run
"""

from __future__ import annotations

import os
import sys
import subprocess
import random
from pathlib import Path
from datetime import datetime

# Import utils from same package
try:
    from utils import utils
except ImportError:
    # Fallback utils for when running as installed script
    class utils:
        @staticmethod
        def get_random_name() -> str:
            nouns = ["gull", "seagull", "bird", "wing", "flight", "sky", "cloud",
                     "ocean", "wave", "beach", "coast", "harbor", "dock", "pier"]
            return f"{random.choice(nouns)}_{random.randint(1000, 9999)}"

        @staticmethod
        def get_env(key: str, default: str = "") -> str:
            return os.environ.get(key, default)

# Handle tomllib for different Python versions
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None


class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'


def print_header(text: str) -> None:
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}  {text}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.END}\n")


def print_step(step: int, total: int, text: str) -> None:
    print(f"{Colors.CYAN}[Step {step}/{total}]{Colors.END} {text}")


def ask_yes_no(question: str, default: bool = True) -> bool:
    default_str = "Y/n" if default else "y/N"
    while True:
        response = input(f"{Colors.YELLOW}?{Colors.END} {question} [{default_str}]: ").strip().lower()
        if not response:
            return default
        if response in ('y', 'yes'):
            return True
        if response in ('n', 'no'):
            return False
        print(f"{Colors.RED}Please answer 'y' or 'n'{Colors.END}")


def ask_choice(question: str, options: list[str], default: int = 0) -> int:
    print(f"\n{Colors.BLUE}{question}{Colors.END}")
    for i, option in enumerate(options, 1):
        marker = " (default)" if i - 1 == default else ""
        print(f"  {i}. {option}{marker}")
    
    while True:
        response = input(f"{Colors.YELLOW}?{Colors.END} Select [1-{len(options)}]: ").strip()
        if not response:
            return default
        try:
            choice = int(response) - 1
            if 0 <= choice < len(options):
                return choice
        except ValueError:
            pass
        print(f"{Colors.RED}Please enter a number between 1 and {len(options)}{Colors.END}")


def ask_input(question: str, default: str = "") -> str:
    default_str = f" [{default}]" if default else ""
    response = input(f"{Colors.YELLOW}?{Colors.END} {question}{default_str}: ").strip()
    return response if response else default


def ask_number(question: str, default: float, min_val: float = None, max_val: float = None) -> float:
    while True:
        response = input(f"{Colors.YELLOW}?{Colors.END} {question} [{default}]: ").strip()
        if not response:
            return default
        try:
            value = float(response)
            if min_val is not None and value < min_val:
                print(f"{Colors.RED}Minimum value is {min_val}{Colors.END}")
                continue
            if max_val is not None and value > max_val:
                print(f"{Colors.RED}Maximum value is {max_val}{Colors.END}")
                continue
            return value
        except ValueError:
            print(f"{Colors.RED}Please enter a number{Colors.END}")


def check_ffmpeg() -> bool:
    """Check if ffmpeg is installed"""
    try:
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            print(f"{Colors.GREEN}✓{Colors.END} ffmpeg found: {version_line}")
            return True
    except FileNotFoundError:
        pass
    
    print(f"{Colors.RED}✗{Colors.END} ffmpeg not found")
    print(f"{Colors.YELLOW}  Please install ffmpeg:{Colors.END}")
    print(f"    Ubuntu/Debian: sudo apt install ffmpeg")
    print(f"    macOS: brew install ffmpeg")
    print(f"    Windows: Download from ffmpeg.org")
    return False


def check_ytdlp() -> bool:
    """Check if yt-dlp is installed"""
    try:
        result = subprocess.run(["yt-dlp", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            version = result.stdout.strip()
            print(f"{Colors.GREEN}✓{Colors.END} yt-dlp found: v{version}")
            return True
    except FileNotFoundError:
        pass
    
    print(f"{Colors.RED}✗{Colors.END} yt-dlp not found (optional but recommended)")
    print(f"{Colors.YELLOW}  Install: pip install yt-dlp{Colors.END}")
    return False


def detect_gpu() -> str:
    """Try to detect available GPU"""
    gpus = []
    
    # Check for NVIDIA
    try:
        result = subprocess.run(["nvidia-smi"], capture_output=True, text=True)
        if result.returncode == 0:
            gpus.append("nvidia")
    except FileNotFoundError:
        pass
    
    # Check for AMD (linux)
    if os.path.exists("/dev/dri/renderD128"):
        gpus.append("amd")
    
    # Check for Intel (simplified check)
    try:
        result = subprocess.run(["vainfo"], capture_output=True, text=True)
        if result.returncode == 0 and "Intel" in result.stdout:
            gpus.append("intel")
    except FileNotFoundError:
        pass
    
    return gpus[0] if gpus else ""


def run_setup() -> None:
    """Run the interactive setup wizard"""
    print_header("🐦 HugeGull Setup Wizard")
    
    print(f"{Colors.CYAN}Welcome! This wizard will help you configure HugeGull.{Colors.END}\n")
    
    # Step 1: Check dependencies
    print_step(1, 5, "Checking dependencies...")
    ffmpeg_ok = check_ffmpeg()
    check_ytdlp()
    
    if not ffmpeg_ok:
        print(f"\n{Colors.RED}ffmpeg is required. Please install it and run setup again.{Colors.END}")
        sys.exit(1)
    
    input(f"\n{Colors.YELLOW}Press Enter to continue...{Colors.END}")
    
    # Step 2: Output directory
    print_step(2, 5, "Configure output location")
    
    default_path = os.path.expanduser("~/Videos/hugegull")
    output_path = ask_input("Where should videos be saved?", default_path)
    output_path = os.path.expanduser(output_path)
    
    # Create directory if it doesn't exist
    os.makedirs(output_path, exist_ok=True)
    print(f"{Colors.GREEN}✓{Colors.END} Directory ready: {output_path}")
    
    # Step 3: Default video settings
    print_step(3, 5, "Default video settings")
    
    duration = ask_number("Default video duration (seconds)", 45, 5, 300)
    fps = int(ask_number("Default FPS", 30, 15, 60))
    quality = int(ask_number("Default quality CRF (18-35, lower is better)", 28, 18, 35))
    
    # Step 4: GPU encoding
    print_step(4, 5, "GPU encoding setup")
    
    detected_gpu = detect_gpu()
    gpu_options = ["None (CPU only)", "NVIDIA (NVENC)", "AMD (VAAPI)", "Intel (Quick Sync)"]
    gpu_values = ["", "nvidia", "amd", "intel"]
    
    if detected_gpu:
        print(f"{Colors.GREEN}Detected GPU:{Colors.END} {detected_gpu.upper()}")
        default_gpu = gpu_values.index(detected_gpu) if detected_gpu in gpu_values else 0
    else:
        print(f"{Colors.YELLOW}No GPU detected or GPU tools not installed{Colors.END}")
        default_gpu = 0
    
    gpu_choice = ask_choice("Select GPU encoding:", gpu_options, default_gpu)
    gpu = gpu_values[gpu_choice]
    
    # Step 5: Advanced options
    print_step(5, 5, "Advanced options")
    
    enable_scene_detection = ask_yes_no("Enable scene detection by default?", False)
    skip_start = ask_number("Skip first N seconds (for intros)", 0, 0, 300)
    skip_end = ask_number("Skip last N seconds (for outros)", 0, 0, 300)
    
    # Generate config
    config_content = f'''# HugeGull Configuration
# Generated by setup wizard on {datetime.now().strftime("%Y-%m-%d %H:%M")}

# Output settings
path = "{output_path}"
duration = {duration}
fps = {fps}
crf = {quality}

# GPU encoding: "nvidia", "amd", "intel", or "" for CPU
gpu = "{gpu}"

# Clip duration range (seconds)
min_clip_duration = 3.0
avg_clip_duration = 6.0
max_clip_duration = 9.0

# Scene detection
scene_detection = {str(enable_scene_detection).lower()}
scene_threshold = 0.3

# Skip intros/outros (seconds)
skip_start = {skip_start}
skip_end = {skip_end}

# Fade between clips (seconds)
fade = 0.03
'''
    
    # Write config
    config_dir = os.path.expanduser("~/.config/hugegull")
    config_path = os.path.join(config_dir, "config.toml")
    
    os.makedirs(config_dir, exist_ok=True)
    
    with open(config_path, "w") as f:
        f.write(config_content)
    
    print_header("✅ Setup Complete!")
    
    print(f"{Colors.GREEN}Configuration saved to:{Colors.END} {config_path}")
    print(f"\n{Colors.CYAN}You can now use HugeGull:{Colors.END}")
    print(f"  CLI:   hugegull <url> [name]")
    print(f"  Web:   hugegull-web")
    print(f"\n{Colors.YELLOW}Edit {config_path} anytime to change settings.{Colors.END}")
    
    # Test run option
    if ask_yes_no("\nWould you like to test with the web UI now?", False):
        print(f"\n{Colors.CYAN}Starting web UI...{Colors.END}")
        os.system("hugegull-web")


def check_existing_config() -> bool:
    """Check if user already has a config"""
    config_path = os.path.expanduser("~/.config/hugegull/config.toml")
    if os.path.exists(config_path):
        print(f"{Colors.YELLOW}Existing configuration found at:{Colors.END} {config_path}")
        return ask_yes_no("Overwrite existing configuration?", False)
    return True


def main():
    # Check if we should run
    if len(sys.argv) > 1 and sys.argv[1] in ("--force", "-f"):
        pass  # Force run
    elif not check_existing_config():
        print(f"\n{Colors.CYAN}Keeping existing configuration.{Colors.END}")
        print(f"Run with --force to re-run setup.")
        sys.exit(0)
    
    try:
        run_setup()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Setup cancelled.{Colors.END}")
        sys.exit(1)


if __name__ == "__main__":
    main()
