#!/usr/bin/env python3
"""Audio Streamer - Stream audio files to AirPlay and Google Cast devices."""

import asyncio
import sys
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import pychromecast
import yaml
from pyatv import connect, pair, scan
from pyatv.const import DeviceState, Protocol

CONFIG_FILE = Path(__file__).parent / "config.yml"
AUDIO_DIR = Path(__file__).parent / "audio"


@dataclass
class UnifiedDevice:
    """Unified device representation for both AirPlay and Google Cast."""

    id: str
    name: str
    address: str
    protocol: str  # "airplay" or "googlecast"
    raw_device: object  # Original device object


class Streamer(ABC):
    """Abstract base class for streaming strategies."""

    @abstractmethod
    async def stream(self, device: UnifiedDevice, audio_file: Path) -> None:
        """Stream audio file to device."""
        pass

    @abstractmethod
    async def pair(self, device: UnifiedDevice) -> str | None:
        """Pair with device if needed. Returns credentials or None."""
        pass

    @abstractmethod
    def needs_pairing(self) -> bool:
        """Return True if this protocol requires pairing."""
        pass


class AirPlayStreamer(Streamer):
    """AirPlay streaming strategy for Apple devices."""

    def __init__(self, credentials: str | None = None):
        self.credentials = credentials

    def needs_pairing(self) -> bool:
        return True

    async def pair(self, device: UnifiedDevice) -> str | None:
        """Pair with an AirPlay device and return credentials."""
        raw_device = device.raw_device

        print(f"\n🔐 Pairing with {device.name}...")
        print("A PIN code will appear on your Apple TV/HomePod screen.\n")

        pairing = await pair(raw_device, Protocol.AirPlay, asyncio.get_event_loop())

        try:
            await pairing.begin()

            if pairing.device_provides_pin:
                pin = input("Enter the PIN code shown on your device: ").strip()
                pairing.pin(pin)
            else:
                print("Enter this PIN on your device: 1234")
                pairing.pin(1234)

            await pairing.finish()

            if pairing.has_paired:
                print("✅ Pairing successful!")
                for svc in raw_device.services:
                    if svc.protocol == Protocol.AirPlay:
                        return svc.credentials
            else:
                print("❌ Pairing failed.")
                return None

        except Exception as e:
            print(f"❌ Pairing error: {e}")
            return None
        finally:
            await pairing.close()

    async def stream(self, device: UnifiedDevice, audio_file: Path) -> None:
        """Stream audio file to AirPlay device."""
        raw_device = device.raw_device

        if not self.credentials:
            print("⚠️  No credentials found. Run with --pair to authenticate.")
            return

        # Set credentials on services
        for svc in raw_device.services:
            if svc.protocol in (Protocol.AirPlay, Protocol.RAOP):
                svc.credentials = self.credentials

        print(f"📡 Connecting to {device.name}...")

        atv = None
        try:
            atv = await connect(raw_device, asyncio.get_event_loop())

            print(f"🎵 Streaming: {audio_file.name}")
            await atv.stream.stream_file(str(audio_file))

            print("✅ Streaming started! Press Ctrl+C to stop.")

            start_time = time.time()
            while True:
                try:
                    playing = await atv.metadata.playing()
                    if playing.device_state == DeviceState.Idle:
                        break
                    elapsed = int(time.time() - start_time)
                    mins, secs = divmod(elapsed, 60)
                    print(f"\r⏱️  {mins:02d}:{secs:02d}", end="", flush=True)
                    await asyncio.sleep(1)
                except Exception:
                    await asyncio.sleep(1)

            print("\n✅ Playback completed.")

        except KeyboardInterrupt:
            print("\n⏹️  Stopped.")
        except Exception as e:
            print(f"❌ Streaming error: {e}")
        finally:
            if atv:
                atv.close()


class GoogleCastStreamer(Streamer):
    """Google Cast streaming strategy for Chromecast/Nest devices."""

    def needs_pairing(self) -> bool:
        return False

    async def pair(self, device: UnifiedDevice) -> str | None:
        """Google Cast doesn't require pairing."""
        print("ℹ️  Google Cast devices don't require pairing.")
        return "no-credentials-needed"

    async def stream(self, device: UnifiedDevice, audio_file: Path) -> None:
        """Stream audio file to Google Cast device."""
        # pychromecast is synchronous, run in executor
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._stream_sync, device, audio_file)

    def _stream_sync(self, device: UnifiedDevice, audio_file: Path) -> None:
        """Synchronous streaming implementation for Google Cast."""
        import http.server
        import threading
        import urllib.parse

        print(f"📡 Connecting to {device.name}...")

        cast = None
        browser = None
        server = None
        stop_event = threading.Event()

        def cleanup():
            """Clean up resources."""
            stop_event.set()
            if server:
                try:
                    server.shutdown()
                except Exception:
                    pass
            if browser:
                try:
                    browser.stop_discovery()
                except Exception:
                    pass

        try:
            # Connect to the Chromecast
            chromecasts, browser = pychromecast.get_listed_chromecasts(
                friendly_names=[device.name]
            )

            if not chromecasts:
                print(f"❌ Device '{device.name}' not found.")
                return

            cast = chromecasts[0]
            cast.wait()

            print(f"🎵 Streaming: {audio_file.name}")

            # Get local IP for serving the file
            local_ip = self._get_local_ip()
            if not local_ip:
                print("❌ Could not determine local IP address.")
                return

            # Start a simple HTTP server to serve the audio file
            port = 8765
            audio_dir = audio_file.parent.resolve()

            class Handler(http.server.SimpleHTTPRequestHandler):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, directory=str(audio_dir), **kwargs)

                def log_message(self, format, *args):
                    pass  # Suppress logging

            server = http.server.HTTPServer(("0.0.0.0", port), Handler)
            server.timeout = 1  # Allow checking stop_event

            def serve():
                while not stop_event.is_set():
                    server.handle_request()

            server_thread = threading.Thread(target=serve)
            server_thread.daemon = True
            server_thread.start()

            # Give server time to start
            time.sleep(0.5)

            # Determine content type
            suffix = audio_file.suffix.lower()
            content_types = {
                ".mp3": "audio/mpeg",
                ".m4a": "audio/mp4",
                ".wav": "audio/wav",
                ".flac": "audio/flac",
                ".aac": "audio/aac",
            }
            content_type = content_types.get(suffix, "audio/mpeg")

            # Play the audio - URL encode the filename
            encoded_name = urllib.parse.quote(audio_file.name)
            media_url = f"http://{local_ip}:{port}/{encoded_name}"

            mc = cast.media_controller
            mc.play_media(media_url, content_type)
            mc.block_until_active(timeout=10)

            print("✅ Streaming started! Press Ctrl+C to stop.")

            # Wait for playback to complete
            start_time = time.time()
            while not stop_event.is_set():
                time.sleep(1)
                elapsed = int(time.time() - start_time)
                mins, secs = divmod(elapsed, 60)
                print(f"\r⏱️  {mins:02d}:{secs:02d}", end="", flush=True)
                if mc.status.player_state not in ("PLAYING", "BUFFERING", "IDLE"):
                    break
                if (
                    mc.status.player_state == "IDLE"
                    and mc.status.idle_reason == "FINISHED"
                ):
                    break

            print("\n✅ Playback completed.")

        except KeyboardInterrupt:
            print("\n⏹️  Stopped.")
            if cast:
                try:
                    cast.media_controller.stop()
                except Exception:
                    pass
        except Exception as e:
            print(f"❌ Streaming error: {e}")
        finally:
            cleanup()

    def _get_local_ip(self) -> str | None:
        """Get the local IP address."""
        import socket

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return None


def get_streamer(protocol: str, credentials: str | None = None) -> Streamer:
    """Factory function to get the appropriate streamer."""
    if protocol == "airplay":
        return AirPlayStreamer(credentials)
    elif protocol == "googlecast":
        return GoogleCastStreamer()
    else:
        raise ValueError(f"Unknown protocol: {protocol}")


def load_config() -> dict | None:
    """Load saved device configuration."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return yaml.safe_load(f)
    return None


def save_config(
    device_id: str,
    device_name: str,
    device_address: str,
    protocol: str,
    credentials: str | None = None,
) -> None:
    """Save device configuration."""
    config = {
        "device": {
            "id": device_id,
            "name": device_name,
            "address": device_address,
            "protocol": protocol,
        }
    }
    if credentials:
        config["device"]["credentials"] = credentials
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
    print(f"✅ Configuration saved to {CONFIG_FILE}")


async def discover_airplay_devices(timeout: int = 5) -> list[UnifiedDevice]:
    """Discover AirPlay devices on the network."""
    devices = await scan(asyncio.get_event_loop(), timeout=timeout)

    unified = []
    for d in devices:
        if any(svc.protocol == Protocol.AirPlay for svc in d.services):
            unified.append(
                UnifiedDevice(
                    id=str(d.identifier),
                    name=d.name,
                    address=str(d.address),
                    protocol="airplay",
                    raw_device=d,
                )
            )
    return unified


def discover_googlecast_devices(timeout: int = 5) -> list[UnifiedDevice]:
    """Discover Google Cast devices on the network."""
    devices = []

    chromecasts, browser = pychromecast.get_chromecasts(timeout=timeout)

    for cc in chromecasts:
        devices.append(
            UnifiedDevice(
                id=cc.uuid.hex if cc.uuid else cc.name,
                name=cc.name,
                address=cc.cast_info.host,
                protocol="googlecast",
                raw_device=cc,
            )
        )

    browser.stop_discovery()
    return devices


async def discover_all_devices(timeout: int = 5) -> list[UnifiedDevice]:
    """Discover all streaming devices (AirPlay + Google Cast)."""
    print(f"🔍 Scanning for devices ({timeout}s)...")

    # Run both discoveries
    loop = asyncio.get_event_loop()

    airplay_task = discover_airplay_devices(timeout)
    googlecast_future = loop.run_in_executor(None, discover_googlecast_devices, timeout)

    airplay_devices = await airplay_task
    googlecast_devices = await googlecast_future

    all_devices = airplay_devices + googlecast_devices
    return all_devices


def interactive_select(devices: list[UnifiedDevice]) -> UnifiedDevice | None:
    """Interactively select a device from the list."""
    if not devices:
        print("❌ No devices found.")
        return None

    print("\n📱 Available devices:\n")
    for i, device in enumerate(devices, 1):
        protocol_icon = "🍎" if device.protocol == "airplay" else "🔊"
        protocol_name = "AirPlay" if device.protocol == "airplay" else "Google Cast"
        print(f"  [{i}] {protocol_icon} {device.name} ({protocol_name})")
        print(f"      Address: {device.address}")
        print()

    while True:
        try:
            choice = input("Select device number (or 'q' to quit): ").strip()
            if choice.lower() == "q":
                return None

            idx = int(choice) - 1
            if 0 <= idx < len(devices):
                return devices[idx]
            print("❌ Invalid selection. Try again.")
        except ValueError:
            print("❌ Please enter a number.")


async def find_device_by_id(
    device_id: str, protocol: str, timeout: int = 5
) -> UnifiedDevice | None:
    """Find a specific device by its identifier."""
    if protocol == "airplay":
        devices = await discover_airplay_devices(timeout)
    else:
        loop = asyncio.get_event_loop()
        devices = await loop.run_in_executor(None, discover_googlecast_devices, timeout)

    for device in devices:
        if device.id == device_id or device.name == device_id:
            return device
    return None


async def setup_device() -> dict | None:
    """Run the interactive device setup."""
    devices = await discover_all_devices()
    selected = interactive_select(devices)

    if selected:
        save_config(
            selected.id,
            selected.name,
            selected.address,
            selected.protocol,
        )
        return load_config()
    return None


async def stream_audio(device_config: dict, audio_file: Path) -> None:
    """Stream audio file to the configured device."""
    if not audio_file.exists():
        print(f"❌ Audio file not found: {audio_file}")
        return

    device_id = device_config["device"]["id"]
    device_name = device_config["device"]["name"]
    protocol = device_config["device"].get("protocol", "airplay")
    credentials = device_config["device"].get("credentials")

    print(f"🔍 Looking for device: {device_name}...")

    device = await find_device_by_id(device_id, protocol)
    if not device:
        # Try by name as fallback
        device = await find_device_by_id(device_name, protocol)

    if not device:
        print(f"❌ Device '{device_name}' not found. Run with --setup to reconfigure.")
        return

    streamer = get_streamer(protocol, credentials)

    if streamer.needs_pairing() and not credentials:
        print("⚠️  No credentials found. Run with --pair to authenticate.")
        return

    await streamer.stream(device, audio_file)


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
Audio Streamer (AirPlay + Google Cast)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Usage:
  python main.py              # Stream audio (setup if needed)
  python main.py --setup      # Force device setup
  python main.py --pair       # Pair with device (AirPlay only)
  python main.py --list       # List available devices
  python main.py <file.mp3>   # Stream specific file

Supported devices:
  🍎 AirPlay   - Apple TV, HomePod (requires --pair)
  🔊 Google Cast - Chromecast, Nest Mini (no pairing needed)

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
        devices = await discover_all_devices()
        if not devices:
            print("❌ No devices found.")
        else:
            print(f"\n📱 Found {len(devices)} device(s):\n")
            for device in devices:
                protocol_icon = "🍎" if device.protocol == "airplay" else "🔊"
                protocol_name = (
                    "AirPlay" if device.protocol == "airplay" else "Google Cast"
                )
                print(f"  {protocol_icon} {device.name} ({protocol_name})")
                print(f"    Address: {device.address}")
                print(f"    ID: {device.id}")
                print()
        return

    # Handle --setup
    if "--setup" in args:
        await setup_device()
        return

    # Handle --pair
    if "--pair" in args:
        config = load_config()
        if not config:
            print("⚙️  No device configured. Running setup first...\n")
            config = await setup_device()
            if not config:
                print("Setup cancelled.")
                return

        protocol = config["device"].get("protocol", "airplay")
        if protocol != "airplay":
            print("ℹ️  Google Cast devices don't require pairing.")
            return

        device_id = config["device"]["id"]
        device = await find_device_by_id(device_id, protocol)
        if not device:
            print("❌ Device not found. Run --setup to reconfigure.")
            return

        streamer = get_streamer(protocol)
        credentials = await streamer.pair(device)
        if credentials:
            save_config(
                config["device"]["id"],
                config["device"]["name"],
                config["device"]["address"],
                config["device"]["protocol"],
                credentials,
            )
        return

    # Load or create config
    config = load_config()
    if not config:
        print("⚙️  First time setup - please select a device:\n")
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
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️  Stopped.")
        # Suppress threading shutdown errors
        import os

        os._exit(0)
