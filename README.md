# Urination Reminder

定時提醒小孩去上廁所的音訊播放器，支援 AirPlay 和 Google Cast。

## 緣起

女兒晚上在房間裡玩得太專心，常常忘記定時去上廁所。

於是在她房間放了一個 Google Nest Mini，透過 Mac Mini 定時播放提醒音效，讓她記得去尿尿。

## Supported devices

| Protocol       | Devices               | Pairing             |
| -------------- | --------------------- | ------------------- |
| 🍎 AirPlay     | Apple TV, HomePod     | Required (`--pair`) |
| 🔊 Google Cast | Chromecast, Nest Mini | Not needed          |

## Installation

```bash
# Clone and setup
git clone <repo-url>
cd urination

# Install dependencies
uv sync
```

## Usage

### Commands

```bash
uv run python main.py              # Stream audio (setup if needed)
uv run python main.py --setup      # Force device re-selection
uv run python main.py --pair       # Pair with device (AirPlay only)
uv run python main.py --list       # List available devices
uv run python main.py --live       # Live broadcast from microphone
uv run python main.py --record     # Record from mic and stream (10s default)
uv run python main.py --record 30  # Record for 30 seconds
uv run python main.py <file.mp3>   # Stream specific file
uv run python main.py --help       # Show help
```

### Makefile shortcuts

```bash
make live     # Start live broadcast from microphone
make record   # Record 10s from mic and stream
make audio    # Stream audio file (interactive selection)
make config   # Setup/configure device
make pair     # Pair with AirPlay device
make list     # List available devices
```

### First-time setup

#### For Google Cast (Chromecast, Nest Mini)

```bash
uv run python main.py --setup      # Select your Google Cast device
uv run python main.py              # Stream audio (no pairing needed!)
```

#### For AirPlay (Apple TV, HomePod)

```bash
uv run python main.py --setup      # Select your AirPlay device
uv run python main.py --pair       # Enter PIN shown on device
uv run python main.py              # Stream audio
```

### Audio files

Place audio files in the `./audio/` directory. Supported formats:

- MP3, M4A, WAV, FLAC, AAC

### Record and stream

Record audio from your microphone and stream it to the device:

```bash
# Record 10 seconds (default) and stream
uv run python main.py --record

# Record 30 seconds and stream
uv run python main.py --record 30
```

The recording shows a countdown timer and saves to `audio/_recording.wav` before streaming.

### Live broadcast

Stream your microphone in real-time to the device (like a PA system):

```bash
uv run python main.py --live
# or
make live
```

**How it works:**

1. Captures audio from your microphone
2. Encodes to MP3 in real-time using `lameenc`
3. Serves via HTTP chunked transfer encoding
4. Device plays the live stream (~2-3 seconds latency)

Press `Ctrl+C` to stop broadcasting.

## Crontab setup

For scheduled playback, add to crontab:

```bash
crontab -e
```

### Examples

```cron
# Every day 6 PM - 10 PM, every hour (18:00, 19:00, 20:00, 21:00, 22:00)
0 18-22 * * * cd /Users/htlin/urination && .venv/bin/python main.py

# Every 30 minutes from 7 PM to 9 PM
0,30 19-21 * * * cd /Users/htlin/urination && .venv/bin/python main.py

# Weekdays only, 8 PM
0 20 * * 1-5 cd /Users/htlin/urination && .venv/bin/python main.py
```

### Important notes for crontab

1. **Use absolute paths** - crontab runs in a minimal environment
2. **Use venv python directly** - avoid `uv run` in crontab
3. **Ensure device is configured first** - run `uv run python main.py --setup` manually before scheduling
4. **Network required** - both protocols need local network access

### Verify setup

```bash
# Check crontab entries
crontab -l

# Test the command manually first
cd /Users/htlin/urination && .venv/bin/python main.py audio/test.mp3
```

### Logging (optional)

Add logging to debug crontab issues:

```cron
0 7 * * * cd /Users/htlin/urination && .venv/bin/python main.py >> /tmp/streamer.log 2>&1
```

## Configuration

After first run, device config is saved to `config.yml`:

```yaml
device:
  id: "device-uuid-or-mac-address"
  name: "Living Room Speaker"
  address: "192.168.1.100"
  protocol: "googlecast" # or "airplay"
  credentials: "..." # AirPlay only
```

To change device, run `uv run python main.py --setup`.

## Architecture

Uses **Strategy Pattern** for multi-protocol support:

```
Streamer (ABC)
├── AirPlayStreamer    # Apple devices via pyatv
└── GoogleCastStreamer # Google devices via pychromecast

LiveBroadcaster        # Real-time microphone streaming
├── HTTP Server (aiohttp) with chunked transfer
├── MP3 Encoder (lameenc) for real-time encoding
└── Audio Capture (sounddevice) from microphone
```

## Project structure

```
urination/
├── main.py          # Main script with strategy pattern
├── Makefile         # Convenient shortcuts
├── config.yml       # Device config (generated)
├── audio/           # Audio files directory
│   └── .gitkeep
├── pyproject.toml   # Dependencies
└── README.md
```

## Troubleshooting

### No devices found

- Ensure device is on the same network
- Check if device is powered on and not in sleep mode
- Try increasing scan timeout

### AirPlay authentication error (470)

- Run `uv run python main.py --pair` to authenticate
- Enter the PIN shown on your Apple TV/HomePod

### Google Cast not playing audio

- Ensure your Mac can reach the device (same network segment)
- Check if port 8765 is available (used for local HTTP server)

### Crontab not working

- Use absolute paths
- Check logs: `tail -f /tmp/streamer.log`
- Verify network is available at scheduled time
- macOS may require granting cron network access in System Preferences > Privacy & Security

### Permission issues on macOS

```bash
# Grant Terminal/iTerm full disk access if needed
# System Preferences > Privacy & Security > Full Disk Access
```
