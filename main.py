#!/usr/bin/env python3
"""AirPlay Audio Streamer - Stream audio files to AirPlay devices."""

import asyncio
import sys
from pathlib import Path

import yaml
from pyatv import scan, connect
from pyatv.const import DeviceState, Protocol

CONFIG_FILE = Path(__file__).parent / "config.yml"
AUDIO_DIR = Path(__file__).parent / "audio"


def load_config() -> dict | None:
    """Load saved device configuration."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return yaml.safe_load(f)
    return None


def save_config(device_id: str, device_name: str, device_address: str) -> None:
    """Save device configuration."""
    config = {
        "device": {
            "id": device_id,
            "name": device_name,
            "address": device_address,
        }
    }
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
    print(f"✅ Configuration saved to {CONFIG_FILE}")


async def discover_devices(timeout: int = 5) -> list:
    """Discover AirPlay devices on the network."""
    print(f"🔍 Scanning for AirPlay devices ({timeout}s)...")
    devices = await scan(asyncio.get_event_loop(), timeout=timeout)

    # Filter for devices with AirPlay support
    airplay_devices = [d for d in devices if Protocol.AirPlay in d.services]
    return airplay_devices


def interactive_select(devices: list) -> tuple[str, str, str] | None:
    """Interactively select a device from the list."""
    if not devices:
        print("❌ No AirPlay devices found.")
        return None

    print("\n📱 Available AirPlay devices:\n")
    for i, device in enumerate(devices, 1):
        print(f"  [{i}] {device.name}")
        print(f"      Address: {device.address}")
        print(f"      ID: {device.identifier}")
        print()

    while True:
        try:
            choice = input("Select device number (or 'q' to quit): ").strip()
            if choice.lower() == "q":
                return None

            idx = int(choice) - 1
            if 0 <= idx < len(devices):
                selected = devices[idx]
                return (
                    str(selected.identifier),
                    selected.name,
                    str(selected.address),
                )
            print("❌ Invalid selection. Try again.")
        except ValueError:
            print("❌ Please enter a number.")


async def find_device_by_id(device_id: str, timeout: int = 5):
    """Find a specific device by its identifier."""
    devices = await discover_devices(timeout)
    for device in devices:
        if str(device.identifier) == device_id:
            return device
    return None


async def stream_audio(device_config: dict, audio_file: Path) -> None:
    """Stream audio file to the configured AirPlay device."""
    if not audio_file.exists():
        print(f"❌ Audio file not found: {audio_file}")
        return

    device_id = device_config["device"]["id"]
    device_name = device_config["device"]["name"]

    print(f"🔍 Looking for device: {device_name}...")

    # Find the device
    device = await find_device_by_id(device_id)
    if not device:
        print(f"❌ Device '{device_name}' not found. Run with --setup to reconfigure.")
        return

    print(f"📡 Connecting to {device.name}...")

    atv = None
    try:
        atv = await connect(device, asyncio.get_event_loop())

        print(f"🎵 Streaming: {audio_file.name}")

        # Stream the audio file
        await atv.stream.stream_file(str(audio_file))

        print("✅ Streaming started! Press Ctrl+C to stop.")

        # Wait for playback to complete
        while True:
            try:
                playing = await atv.metadata.playing()
                if playing.device_state == DeviceState.Idle:
                    break
                await asyncio.sleep(1)
            except Exception:
                await asyncio.sleep(1)

        print("✅ Playback completed.")

    except KeyboardInterrupt:
        print("\n⏹️  Stopped.")
    except Exception as e:
        print(f"❌ Streaming error: {e}")
    finally:
        if atv:
            atv.close()


async def setup_device() -> dict | None:
    """Run the interactive device setup."""
    devices = await discover_devices()
    selection = interactive_select(devices)

    if selection:
        device_id, device_name, device_address = selection
        save_config(device_id, device_name, device_address)
        return load_config()
    return None


def list_audio_files() -> list[Path]:
    """List available audio files."""
    if not AUDIO_DIR.exists():
        return []
    extensions = ["*.mp3", "*.m4a", "*.wav", "*.flac", "*.aac"]
    files = []
    for ext in extensions:
        files.extend(AUDIO_DIR.glob(ext))
    return sorted(files, key=lambda x: x.name)


def select_audio_file(files: list[Path]) -> Path | None:
    """Select an audio file to play."""
    if not files:
        print("❌ No audio files found in ./audio/")
        return None

    if len(files) == 1:
        return files[0]

    print("\n🎵 Available audio files:\n")
    for i, f in enumerate(files, 1):
        print(f"  [{i}] {f.name}")
    print()

    while True:
        try:
            choice = input("Select file number (or 'q' to quit): ").strip()
            if choice.lower() == "q":
                return None

            idx = int(choice) - 1
            if 0 <= idx < len(files):
                return files[idx]
            print("❌ Invalid selection. Try again.")
        except ValueError:
            print("❌ Please enter a number.")


def print_usage():
    """Print usage information."""
    print("""
AirPlay Audio Streamer
━━━━━━━━━━━━━━━━━━━━━━

Usage:
  python main.py              # Stream audio (setup if needed)
  python main.py --setup      # Force device setup
  python main.py --list       # List available devices
  python main.py <file.mp3>   # Stream specific file

Audio files should be placed in the ./audio/ directory.
""")


async def main():
    args = sys.argv[1:]

    # Handle --help
    if "--help" in args or "-h" in args:
        print_usage()
        return

    # Handle --list
    if "--list" in args:
        devices = await discover_devices()
        if not devices:
            print("❌ No AirPlay devices found.")
        else:
            print(f"\n📱 Found {len(devices)} AirPlay device(s):\n")
            for device in devices:
                print(f"  • {device.name}")
                print(f"    Address: {device.address}")
                print(f"    ID: {device.identifier}")
                print()
        return

    # Handle --setup
    if "--setup" in args:
        await setup_device()
        return

    # Load or create config
    config = load_config()
    if not config:
        print("⚙️  First time setup - please select an AirPlay device:\n")
        config = await setup_device()
        if not config:
            print("Setup cancelled.")
            return

    # Determine audio file to play
    audio_file = None

    # Check if a specific file was provided
    for arg in args:
        if not arg.startswith("--"):
            path = Path(arg)
            if path.exists():
                audio_file = path
            elif (AUDIO_DIR / arg).exists():
                audio_file = AUDIO_DIR / arg
            break

    # If no file specified, let user select
    if not audio_file:
        files = list_audio_files()
        audio_file = select_audio_file(files)
        if not audio_file:
            return

    # Stream the audio
    await stream_audio(config, audio_file)


if __name__ == "__main__":
    asyncio.run(main())
