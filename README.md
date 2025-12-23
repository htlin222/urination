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
uv run python main.py <file.mp3>   # Stream specific file
uv run python main.py --help       # Show help
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
├── AirPlayStreamer   # Apple devices via pyatv
└── GoogleCastStreamer # Google devices via pychromecast
```

## Project structure

```
urination/
├── main.py          # Main script with strategy pattern
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
