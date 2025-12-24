#!/usr/bin/env python3
"""Audio Streamer - Stream audio files to AirPlay and Google Cast devices."""

import asyncio
import sys
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import lameenc
import pychromecast
import sounddevice as sd
import yaml
from aiohttp import web
from pyatv import connect, pair, scan
from pyatv.const import DeviceState, Protocol

CONFIG_FILE = Path(__file__).parent / "config.yml"
AUDIO_DIR = Path(__file__).parent / "audio"
RECORD_FILE = Path(__file__).parent / "audio" / "_recording.wav"
WEB_PORT = 8080


# ============================================================================
# Web GUI HTML Template
# ============================================================================

WEB_HTML = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>🚽 小尿尿提醒</title>
    <style>
        :root {
            --primary: #4f46e5;
            --primary-dark: #4338ca;
            --success: #22c55e;
            --danger: #ef4444;
            --warning: #f59e0b;
            --bg: #f8fafc;
            --card: #ffffff;
            --text: #1e293b;
            --text-muted: #64748b;
            --border: #e2e8f0;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            min-height: 100vh;
            padding: 16px;
            padding-bottom: 100px;
        }

        .container {
            max-width: 500px;
            margin: 0 auto;
        }

        header {
            text-align: center;
            padding: 20px 0;
        }

        header h1 {
            font-size: 28px;
            margin-bottom: 8px;
        }

        .status-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 6px 12px;
            background: var(--card);
            border-radius: 20px;
            font-size: 14px;
            color: var(--text-muted);
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }

        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--success);
        }

        .status-dot.offline { background: var(--danger); }
        .status-dot.busy { background: var(--warning); animation: pulse 1s infinite; }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        .card {
            background: var(--card);
            border-radius: 16px;
            padding: 20px;
            margin-bottom: 16px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }

        .card-title {
            font-size: 16px;
            font-weight: 600;
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .device-info {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px;
            background: var(--bg);
            border-radius: 12px;
        }

        .device-icon {
            font-size: 32px;
        }

        .device-details h3 {
            font-size: 16px;
            margin-bottom: 4px;
        }

        .device-details p {
            font-size: 12px;
            color: var(--text-muted);
        }

        .btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            padding: 14px 24px;
            border: none;
            border-radius: 12px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            width: 100%;
        }

        .btn:active {
            transform: scale(0.98);
        }

        .btn-primary {
            background: var(--primary);
            color: white;
        }

        .btn-primary:hover {
            background: var(--primary-dark);
        }

        .btn-success {
            background: var(--success);
            color: white;
        }

        .btn-danger {
            background: var(--danger);
            color: white;
        }

        .btn-outline {
            background: transparent;
            border: 2px solid var(--border);
            color: var(--text);
        }

        .btn-outline:hover {
            background: var(--bg);
        }

        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }

        .btn-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
        }

        .btn-large {
            padding: 20px;
            font-size: 18px;
        }

        .audio-list {
            display: flex;
            flex-direction: column;
            gap: 8px;
            max-height: 300px;
            overflow-y: auto;
        }

        .audio-item {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 12px;
            background: var(--bg);
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.2s;
        }

        .audio-item:hover {
            background: var(--border);
        }

        .audio-item.playing {
            background: #dbeafe;
            border: 2px solid var(--primary);
        }

        .audio-name {
            font-size: 14px;
            font-weight: 500;
            word-break: break-all;
        }

        .play-btn {
            width: 36px;
            height: 36px;
            border-radius: 50%;
            background: var(--primary);
            color: white;
            border: none;
            font-size: 14px;
            cursor: pointer;
            flex-shrink: 0;
        }

        .record-controls {
            display: flex;
            flex-direction: column;
            gap: 12px;
        }

        .duration-input {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .duration-input label {
            font-size: 14px;
            color: var(--text-muted);
        }

        .duration-input input {
            flex: 1;
            padding: 10px;
            border: 2px solid var(--border);
            border-radius: 8px;
            font-size: 16px;
            text-align: center;
        }

        .live-indicator {
            display: none;
            align-items: center;
            justify-content: center;
            gap: 8px;
            padding: 12px;
            background: #fee2e2;
            border-radius: 10px;
            color: var(--danger);
            font-weight: 600;
        }

        .live-indicator.active {
            display: flex;
        }

        .live-dot {
            width: 12px;
            height: 12px;
            background: var(--danger);
            border-radius: 50%;
            animation: pulse 1s infinite;
        }

        .timer {
            font-size: 24px;
            font-family: monospace;
        }

        .toast {
            position: fixed;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            padding: 12px 24px;
            background: var(--text);
            color: white;
            border-radius: 10px;
            font-size: 14px;
            z-index: 1000;
            opacity: 0;
            transition: opacity 0.3s;
        }

        .toast.show {
            opacity: 1;
        }

        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.5);
            z-index: 100;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }

        .modal.show {
            display: flex;
        }

        .modal-content {
            background: var(--card);
            border-radius: 16px;
            padding: 24px;
            width: 100%;
            max-width: 400px;
            max-height: 80vh;
            overflow-y: auto;
        }

        .modal-title {
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 16px;
        }

        .device-list {
            display: flex;
            flex-direction: column;
            gap: 8px;
            margin-bottom: 16px;
        }

        .device-option {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px;
            background: var(--bg);
            border-radius: 10px;
            cursor: pointer;
            border: 2px solid transparent;
            transition: all 0.2s;
        }

        .device-option:hover {
            border-color: var(--primary);
        }

        .device-option.selected {
            border-color: var(--primary);
            background: #eef2ff;
        }

        .loading {
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 40px;
        }

        .spinner {
            width: 40px;
            height: 40px;
            border: 4px solid var(--border);
            border-top-color: var(--primary);
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        .empty-state {
            text-align: center;
            padding: 40px 20px;
            color: var(--text-muted);
        }

        .empty-state-icon {
            font-size: 48px;
            margin-bottom: 12px;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🚽 小尿尿提醒</h1>
            <div class="status-badge" id="statusBadge">
                <span class="status-dot" id="statusDot"></span>
                <span id="statusText">連線中...</span>
            </div>
        </header>

        <!-- Device Card -->
        <div class="card">
            <div class="card-title">📱 播放裝置</div>
            <div class="device-info" id="deviceInfo">
                <span class="device-icon" id="deviceIcon">🔊</span>
                <div class="device-details">
                    <h3 id="deviceName">尚未設定</h3>
                    <p id="deviceAddress">請選擇裝置</p>
                </div>
            </div>
            <button class="btn btn-outline" style="margin-top: 12px;" onclick="openDeviceModal()">
                🔄 更換裝置
            </button>
        </div>

        <!-- Quick Actions -->
        <div class="card">
            <div class="card-title">⚡ 快速操作</div>
            <div class="btn-grid">
                <button class="btn btn-primary btn-large" onclick="startLive()" id="liveBtn">
                    🎙️ 即時廣播
                </button>
                <button class="btn btn-success btn-large" onclick="startRecord()" id="recordBtn">
                    ⏺️ 錄音播放
                </button>
            </div>

            <div class="live-indicator" id="liveIndicator">
                <span class="live-dot"></span>
                <span>廣播中</span>
                <span class="timer" id="liveTimer">00:00</span>
            </div>

            <div class="record-controls" id="recordControls" style="display: none; margin-top: 12px;">
                <div class="duration-input">
                    <label>錄音秒數:</label>
                    <input type="number" id="recordDuration" value="10" min="1" max="120">
                </div>
                <button class="btn btn-danger" onclick="confirmRecord()">開始錄音</button>
                <button class="btn btn-outline" onclick="cancelRecord()">取消</button>
            </div>
        </div>

        <!-- Audio Files -->
        <div class="card">
            <div class="card-title">🎵 音檔列表</div>
            <div class="audio-list" id="audioList">
                <div class="loading">
                    <div class="spinner"></div>
                </div>
            </div>
        </div>
    </div>

    <!-- Device Selection Modal -->
    <div class="modal" id="deviceModal">
        <div class="modal-content">
            <div class="modal-title">選擇播放裝置</div>
            <div class="device-list" id="deviceList">
                <div class="loading">
                    <div class="spinner"></div>
                </div>
            </div>
            <div class="btn-grid">
                <button class="btn btn-outline" onclick="closeDeviceModal()">取消</button>
                <button class="btn btn-primary" onclick="saveDevice()" id="saveDeviceBtn" disabled>確認</button>
            </div>
        </div>
    </div>

    <!-- Toast -->
    <div class="toast" id="toast"></div>

    <script>
        let currentDevice = null;
        let selectedDevice = null;
        let isLive = false;
        let liveStartTime = null;
        let liveTimerInterval = null;

        // Initialize
        document.addEventListener('DOMContentLoaded', () => {
            loadConfig();
            loadAudioFiles();
        });

        // Toast notification
        function showToast(message) {
            const toast = document.getElementById('toast');
            toast.textContent = message;
            toast.classList.add('show');
            setTimeout(() => toast.classList.remove('show'), 3000);
        }

        // Load current config
        async function loadConfig() {
            try {
                const res = await fetch('/api/config');
                const data = await res.json();

                if (data.device) {
                    currentDevice = data.device;
                    updateDeviceDisplay();
                    updateStatus('online', currentDevice.name);
                } else {
                    updateStatus('offline', '尚未設定裝置');
                }
            } catch (err) {
                updateStatus('offline', '連線失敗');
            }
        }

        // Update device display
        function updateDeviceDisplay() {
            if (currentDevice) {
                document.getElementById('deviceIcon').textContent =
                    currentDevice.protocol === 'airplay' ? '🍎' : '🔊';
                document.getElementById('deviceName').textContent = currentDevice.name;
                document.getElementById('deviceAddress').textContent =
                    `${currentDevice.protocol === 'airplay' ? 'AirPlay' : 'Google Cast'} • ${currentDevice.address}`;
            }
        }

        // Update status badge
        function updateStatus(status, text) {
            const dot = document.getElementById('statusDot');
            const statusText = document.getElementById('statusText');

            dot.className = 'status-dot';
            if (status === 'offline') dot.classList.add('offline');
            if (status === 'busy') dot.classList.add('busy');

            statusText.textContent = text;
        }

        // Load audio files
        async function loadAudioFiles() {
            try {
                const res = await fetch('/api/audio-files');
                const files = await res.json();

                const list = document.getElementById('audioList');

                if (files.length === 0) {
                    list.innerHTML = `
                        <div class="empty-state">
                            <div class="empty-state-icon">📂</div>
                            <p>沒有音檔</p>
                            <p style="font-size: 12px;">請將音檔放入 audio/ 資料夾</p>
                        </div>
                    `;
                    return;
                }

                list.innerHTML = files.map(file => `
                    <div class="audio-item" data-file="${file}">
                        <span class="audio-name">🎵 ${file}</span>
                        <button class="play-btn" onclick="playAudio('${file}')">▶</button>
                    </div>
                `).join('');
            } catch (err) {
                showToast('載入音檔失敗');
            }
        }

        // Play audio file
        async function playAudio(filename) {
            if (!currentDevice) {
                showToast('請先設定播放裝置');
                return;
            }

            showToast(`播放 ${filename}`);
            startTimer('播放中');
            updateStatus('busy', '📡 播放中 00:00');

            // Update status with elapsed time
            const playTimerInterval = setInterval(() => {
                updateStatus('busy', `📡 播放中 ${formatTime(elapsedSeconds)}`);
            }, 1000);

            try {
                const res = await fetch('/api/stream', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ filename })
                });

                const data = await res.json();

                if (data.success) {
                    showToast('✅ 播放完成！');
                } else {
                    showToast(data.error || '播放失敗');
                }
            } catch (err) {
                showToast('播放失敗');
            } finally {
                clearInterval(playTimerInterval);
                stopTimer();
                updateStatus('online', currentDevice.name);
            }
        }

        // Start live broadcast
        async function startLive() {
            if (!currentDevice) {
                showToast('請先設定播放裝置');
                return;
            }

            if (isLive) {
                // Stop live
                try {
                    await fetch('/api/live/stop', { method: 'POST' });
                    stopLiveUI();
                } catch (err) {
                    showToast('停止廣播失敗');
                }
                return;
            }

            // Start live
            updateStatus('busy', '啟動廣播中...');

            try {
                const res = await fetch('/api/live/start', { method: 'POST' });
                const data = await res.json();

                if (data.success) {
                    startLiveUI();
                } else {
                    showToast(data.error || '啟動失敗');
                    updateStatus('online', currentDevice.name);
                }
            } catch (err) {
                showToast('啟動廣播失敗');
                updateStatus('online', currentDevice.name);
            }
        }

        function startLiveUI() {
            isLive = true;
            liveStartTime = Date.now();

            document.getElementById('liveBtn').textContent = '⏹️ 停止廣播';
            document.getElementById('liveBtn').classList.remove('btn-primary');
            document.getElementById('liveBtn').classList.add('btn-danger');
            document.getElementById('liveIndicator').classList.add('active');
            document.getElementById('recordBtn').disabled = true;

            updateStatus('busy', '廣播中');

            liveTimerInterval = setInterval(() => {
                const elapsed = Math.floor((Date.now() - liveStartTime) / 1000);
                const mins = Math.floor(elapsed / 60).toString().padStart(2, '0');
                const secs = (elapsed % 60).toString().padStart(2, '0');
                document.getElementById('liveTimer').textContent = `${mins}:${secs}`;
            }, 1000);
        }

        function stopLiveUI() {
            isLive = false;
            clearInterval(liveTimerInterval);

            document.getElementById('liveBtn').textContent = '🎙️ 即時廣播';
            document.getElementById('liveBtn').classList.remove('btn-danger');
            document.getElementById('liveBtn').classList.add('btn-primary');
            document.getElementById('liveIndicator').classList.remove('active');
            document.getElementById('recordBtn').disabled = false;

            updateStatus('online', currentDevice.name);
            showToast('廣播已停止');
        }

        // Record
        function startRecord() {
            document.getElementById('recordControls').style.display = 'flex';
            document.getElementById('recordBtn').style.display = 'none';
        }

        function cancelRecord() {
            document.getElementById('recordControls').style.display = 'none';
            document.getElementById('recordBtn').style.display = '';
        }

        let timerInterval = null;
        let elapsedSeconds = 0;

        function startTimer(label) {
            elapsedSeconds = 0;
            document.getElementById('liveIndicator').classList.add('active');
            document.getElementById('liveIndicator').querySelector('span:nth-child(2)').textContent = label;
            document.getElementById('liveTimer').textContent = '00:00';
            document.getElementById('liveBtn').disabled = true;
            document.getElementById('recordBtn').disabled = true;

            timerInterval = setInterval(() => {
                elapsedSeconds++;
                document.getElementById('liveTimer').textContent = formatTime(elapsedSeconds);
            }, 1000);
        }

        function stopTimer() {
            if (timerInterval) {
                clearInterval(timerInterval);
                timerInterval = null;
            }
            document.getElementById('liveIndicator').classList.remove('active');
            document.getElementById('liveIndicator').querySelector('span:nth-child(2)').textContent = '廣播中';
            document.getElementById('liveBtn').disabled = false;
            document.getElementById('recordBtn').disabled = false;
        }

        function formatTime(seconds) {
            const mins = Math.floor(seconds / 60).toString().padStart(2, '0');
            const secs = (seconds % 60).toString().padStart(2, '0');
            return `${mins}:${secs}`;
        }

        async function confirmRecord() {
            if (!currentDevice) {
                showToast('請先設定播放裝置');
                return;
            }

            const duration = parseInt(document.getElementById('recordDuration').value) || 10;

            cancelRecord();
            showToast(`開始錄音 ${duration} 秒`);

            // Recording countdown phase
            let remaining = duration;
            document.getElementById('liveIndicator').classList.add('active');
            document.getElementById('liveIndicator').querySelector('span:nth-child(2)').textContent = '錄音中';
            document.getElementById('liveTimer').textContent = formatTime(remaining);
            document.getElementById('liveBtn').disabled = true;
            document.getElementById('recordBtn').disabled = true;
            updateStatus('busy', `🎙️ 錄音中 ${remaining} 秒`);

            // Countdown during recording
            const countdownInterval = setInterval(() => {
                remaining--;
                if (remaining > 0) {
                    document.getElementById('liveTimer').textContent = formatTime(remaining);
                    updateStatus('busy', `🎙️ 錄音中 ${remaining} 秒`);
                } else {
                    // Recording done, switch to playback mode
                    clearInterval(countdownInterval);
                    document.getElementById('liveIndicator').querySelector('span:nth-child(2)').textContent = '播放中';
                    updateStatus('busy', '📡 播放中...');
                    elapsedSeconds = 0;

                    // Start counting up for playback
                    timerInterval = setInterval(() => {
                        elapsedSeconds++;
                        document.getElementById('liveTimer').textContent = formatTime(elapsedSeconds);
                        updateStatus('busy', `📡 播放中 ${formatTime(elapsedSeconds)}`);
                    }, 1000);
                }
            }, 1000);

            try {
                const res = await fetch('/api/record', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ duration })
                });

                const data = await res.json();

                if (data.success) {
                    showToast('✅ 完成！可以繼續下一輪');
                    loadAudioFiles();
                } else {
                    showToast(data.error || '錄音失敗');
                }
            } catch (err) {
                showToast('錄音失敗');
            } finally {
                clearInterval(countdownInterval);
                stopTimer();
                updateStatus('online', currentDevice.name);
            }
        }

        // Device modal
        async function openDeviceModal() {
            document.getElementById('deviceModal').classList.add('show');
            document.getElementById('deviceList').innerHTML = `
                <div class="loading">
                    <div class="spinner"></div>
                </div>
            `;
            document.getElementById('saveDeviceBtn').disabled = true;
            selectedDevice = null;

            try {
                const res = await fetch('/api/devices');
                const devices = await res.json();

                if (devices.length === 0) {
                    document.getElementById('deviceList').innerHTML = `
                        <div class="empty-state">
                            <div class="empty-state-icon">📡</div>
                            <p>找不到裝置</p>
                            <p style="font-size: 12px;">請確認裝置已開啟</p>
                        </div>
                    `;
                    return;
                }

                document.getElementById('deviceList').innerHTML = devices.map((device, idx) => `
                    <div class="device-option" data-idx="${idx}" onclick="selectDevice(${idx}, this)">
                        <span style="font-size: 24px;">${device.protocol === 'airplay' ? '🍎' : '🔊'}</span>
                        <div>
                            <div style="font-weight: 600;">${device.name}</div>
                            <div style="font-size: 12px; color: var(--text-muted);">
                                ${device.protocol === 'airplay' ? 'AirPlay' : 'Google Cast'} • ${device.address}
                            </div>
                        </div>
                    </div>
                `).join('');

                window._devices = devices;
            } catch (err) {
                document.getElementById('deviceList').innerHTML = `
                    <div class="empty-state">
                        <div class="empty-state-icon">❌</div>
                        <p>掃描失敗</p>
                    </div>
                `;
            }
        }

        function selectDevice(idx, el) {
            document.querySelectorAll('.device-option').forEach(e => e.classList.remove('selected'));
            el.classList.add('selected');
            selectedDevice = window._devices[idx];
            document.getElementById('saveDeviceBtn').disabled = false;
        }

        async function saveDevice() {
            if (!selectedDevice) return;

            try {
                const res = await fetch('/api/config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(selectedDevice)
                });

                const data = await res.json();

                if (data.success) {
                    currentDevice = selectedDevice;
                    updateDeviceDisplay();
                    updateStatus('online', currentDevice.name);
                    showToast('裝置已儲存');
                    closeDeviceModal();
                } else {
                    showToast(data.error || '儲存失敗');
                }
            } catch (err) {
                showToast('儲存失敗');
            }
        }

        function closeDeviceModal() {
            document.getElementById('deviceModal').classList.remove('show');
        }

        // Close modal on backdrop click
        document.getElementById('deviceModal').addEventListener('click', (e) => {
            if (e.target === document.getElementById('deviceModal')) {
                closeDeviceModal();
            }
        });
    </script>
</body>
</html>
"""


def record_audio(duration: int = 10, sample_rate: int = 44100) -> Path:
    """Record audio from microphone and save to file."""
    import soundfile as sf

    print(f"🎙️  Recording for {duration} seconds... (Press Ctrl+C to stop early)")

    try:
        # Record audio
        recording = sd.rec(
            int(duration * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype="int16",
        )

        # Show countdown
        for i in range(duration, 0, -1):
            print(f"\r⏱️  {i:02d}s remaining", end="", flush=True)
            sd.sleep(1000)

        sd.wait()  # Wait for recording to finish
        print("\r✅ Recording completed!    ")

        # Save to file
        RECORD_FILE.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(RECORD_FILE), recording, sample_rate)

        return RECORD_FILE

    except KeyboardInterrupt:
        sd.stop()
        print("\n⏹️  Recording stopped early.")

        # Save what we have
        RECORD_FILE.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(RECORD_FILE), recording, sample_rate)

        return RECORD_FILE


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
            audio_dir = audio_file.parent.resolve()

            class Handler(http.server.SimpleHTTPRequestHandler):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, directory=str(audio_dir), **kwargs)

                def log_message(self, format, *args):
                    pass  # Suppress logging

            # Create server with SO_REUSEADDR to avoid "Address already in use"
            class ReuseAddrHTTPServer(http.server.HTTPServer):
                allow_reuse_address = True

            # Try to find an available port
            port = 8765
            server = None
            for p in range(8765, 8775):
                try:
                    server = ReuseAddrHTTPServer(("0.0.0.0", p), Handler)
                    port = p
                    break
                except OSError:
                    continue

            if server is None:
                print("❌ Could not find an available port for HTTP server.")
                return

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
            started_playing = False
            while not stop_event.is_set():
                time.sleep(1)
                elapsed = int(time.time() - start_time)
                mins, secs = divmod(elapsed, 60)
                print(f"\r⏱️  {mins:02d}:{secs:02d}", end="", flush=True)

                state = mc.status.player_state
                if state == "PLAYING":
                    started_playing = True
                elif started_playing and state == "IDLE":
                    # Finished playing
                    break
                elif state not in ("PLAYING", "BUFFERING", "IDLE", "UNKNOWN"):
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


class LiveBroadcaster:
    """Real-time audio broadcasting from microphone via HTTP chunked MP3 stream."""

    def __init__(
        self,
        sample_rate: int = 44100,
        channels: int = 1,
        bitrate: int = 128,
        chunk_ms: int = 100,
        port: int = 8765,
    ):
        self.sample_rate = sample_rate
        self.channels = channels
        self.bitrate = bitrate
        self.chunk_ms = chunk_ms
        self.port = port
        self.broadcasting = False
        self._app: web.Application | None = None
        self._runner: web.AppRunner | None = None
        self._encoder: lameenc.Encoder | None = None
        self._audio_queue: asyncio.Queue | None = None

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

    def _setup_encoder(self) -> lameenc.Encoder:
        """Setup MP3 encoder."""
        encoder = lameenc.Encoder()
        encoder.set_bit_rate(self.bitrate)
        encoder.set_in_sample_rate(self.sample_rate)
        encoder.set_channels(self.channels)
        encoder.set_quality(2)  # 2=highest quality, 7=fastest
        return encoder

    async def _audio_capture_task(self) -> None:
        """Capture audio from microphone and put into queue."""
        chunk_size = int(self.sample_rate * self.chunk_ms / 1000)
        loop = asyncio.get_event_loop()

        def audio_callback(indata, frames, time_info, status):
            if status:
                print(f"⚠️  Audio status: {status}")
            if self.broadcasting and self._audio_queue:
                # Convert to bytes and encode to MP3
                pcm_data = indata.tobytes()
                mp3_chunk = self._encoder.encode(pcm_data)
                if mp3_chunk:
                    loop.call_soon_threadsafe(self._audio_queue.put_nowait, mp3_chunk)

        with sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="int16",
            blocksize=chunk_size,
            callback=audio_callback,
        ):
            while self.broadcasting:
                await asyncio.sleep(0.1)

    async def _stream_handler(self, request: web.Request) -> web.StreamResponse:
        """Handle HTTP request for live MP3 stream."""
        response = web.StreamResponse()
        response.content_type = "audio/mpeg"
        response.headers["Cache-Control"] = "no-cache"
        response.headers["Connection"] = "keep-alive"
        response.headers["Transfer-Encoding"] = "chunked"
        await response.prepare(request)

        print("📡 Client connected to live stream")

        try:
            while self.broadcasting:
                try:
                    # Wait for audio data with timeout
                    mp3_chunk = await asyncio.wait_for(
                        self._audio_queue.get(), timeout=1.0
                    )
                    await response.write(mp3_chunk)
                except asyncio.TimeoutError:
                    continue
                except ConnectionResetError:
                    break
        except Exception as e:
            print(f"⚠️  Stream error: {e}")
        finally:
            print("📴 Client disconnected")

        return response

    async def start_server(self) -> str:
        """Start the HTTP streaming server. Returns the stream URL."""
        self._encoder = self._setup_encoder()
        self._audio_queue = asyncio.Queue(maxsize=100)

        self._app = web.Application()
        self._app.router.add_get("/live.mp3", self._stream_handler)

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()

        # Try to find an available port
        local_ip = self._get_local_ip()
        for port in range(self.port, self.port + 10):
            try:
                site = web.TCPSite(self._runner, "0.0.0.0", port)
                await site.start()
                self.port = port
                stream_url = f"http://{local_ip}:{port}/live.mp3"
                return stream_url
            except OSError:
                continue

        raise OSError("Could not find an available port for live broadcast")

    async def stop_server(self) -> None:
        """Stop the HTTP streaming server."""
        self.broadcasting = False
        if self._encoder:
            # Flush remaining data
            self._encoder.flush()
        if self._runner:
            await self._runner.cleanup()

    async def broadcast(
        self, device: UnifiedDevice, credentials: str | None = None
    ) -> None:
        """Start live broadcasting to a device."""
        print(f"🎙️  Starting live broadcast to {device.name}...")

        # Start HTTP server
        stream_url = await self.start_server()
        print(f"📡 Stream URL: {stream_url}")

        self.broadcasting = True

        # Start audio capture in background
        capture_task = asyncio.create_task(self._audio_capture_task())

        # Give server time to start
        await asyncio.sleep(0.5)

        try:
            if device.protocol == "airplay":
                await self._broadcast_airplay(device, stream_url, credentials)
            else:
                await self._broadcast_googlecast(device, stream_url)
        finally:
            self.broadcasting = False
            capture_task.cancel()
            try:
                await capture_task
            except asyncio.CancelledError:
                pass
            await self.stop_server()

    async def _broadcast_airplay(
        self, device: UnifiedDevice, stream_url: str, credentials: str | None
    ) -> None:
        """Broadcast to AirPlay device."""
        raw_device = device.raw_device

        if not credentials:
            print("⚠️  No credentials found. Run with --pair to authenticate.")
            return

        # Set credentials on services
        for svc in raw_device.services:
            if svc.protocol in (Protocol.AirPlay, Protocol.RAOP):
                svc.credentials = credentials

        print(f"📡 Connecting to {device.name}...")
        atv = await connect(raw_device, asyncio.get_event_loop())

        try:
            print("🎵 Starting live stream...")
            await atv.stream.stream_file(stream_url)

            print("✅ Live broadcast started! Press Ctrl+C to stop.")
            start_time = time.time()

            while self.broadcasting:
                elapsed = int(time.time() - start_time)
                mins, secs = divmod(elapsed, 60)
                print(f"\r🔴 LIVE {mins:02d}:{secs:02d}", end="", flush=True)
                await asyncio.sleep(1)

        except KeyboardInterrupt:
            print("\n⏹️  Broadcast stopped.")
        finally:
            atv.close()

    async def _broadcast_googlecast(
        self, device: UnifiedDevice, stream_url: str
    ) -> None:
        """Broadcast to Google Cast device."""
        loop = asyncio.get_event_loop()

        def play_stream():
            chromecasts, browser = pychromecast.get_listed_chromecasts(
                friendly_names=[device.name]
            )
            if not chromecasts:
                print(f"❌ Device '{device.name}' not found.")
                return None
            cast = chromecasts[0]
            cast.wait()
            mc = cast.media_controller
            mc.play_media(stream_url, "audio/mpeg")
            mc.block_until_active(timeout=10)
            browser.stop_discovery()
            return cast

        print(f"📡 Connecting to {device.name}...")
        cast = await loop.run_in_executor(None, play_stream)

        if not cast:
            return

        try:
            print("✅ Live broadcast started! Press Ctrl+C to stop.")
            start_time = time.time()

            while self.broadcasting:
                elapsed = int(time.time() - start_time)
                mins, secs = divmod(elapsed, 60)
                print(f"\r🔴 LIVE {mins:02d}:{secs:02d}", end="", flush=True)
                await asyncio.sleep(1)

        except KeyboardInterrupt:
            print("\n⏹️  Broadcast stopped.")
        finally:
            try:
                cast.media_controller.stop()
            except Exception:
                pass


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


# ============================================================================
# Web Server
# ============================================================================


class WebServer:
    """Web GUI server for controlling the audio streamer."""

    def __init__(self, port: int = WEB_PORT):
        self.port = port
        self.app = web.Application()
        self.runner: web.AppRunner | None = None
        self.live_broadcaster: LiveBroadcaster | None = None
        self.live_task: asyncio.Task | None = None
        self._setup_routes()

    def _setup_routes(self):
        """Setup API routes."""
        self.app.router.add_get("/", self._handle_index)
        self.app.router.add_get("/api/config", self._handle_get_config)
        self.app.router.add_post("/api/config", self._handle_save_config)
        self.app.router.add_get("/api/devices", self._handle_discover_devices)
        self.app.router.add_get("/api/audio-files", self._handle_list_audio)
        self.app.router.add_post("/api/stream", self._handle_stream)
        self.app.router.add_post("/api/record", self._handle_record)
        self.app.router.add_post("/api/live/start", self._handle_live_start)
        self.app.router.add_post("/api/live/stop", self._handle_live_stop)

    def _get_local_ip(self) -> str:
        """Get local IP address."""
        import socket

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "localhost"

    async def _handle_index(self, request: web.Request) -> web.Response:
        """Serve the main HTML page."""
        return web.Response(text=WEB_HTML, content_type="text/html")

    async def _handle_get_config(self, request: web.Request) -> web.Response:
        """Get current device configuration."""
        config = load_config()
        if config:
            return web.json_response(config)
        return web.json_response({})

    async def _handle_save_config(self, request: web.Request) -> web.Response:
        """Save device configuration."""
        try:
            data = await request.json()
            save_config(
                device_id=data.get("id", ""),
                device_name=data.get("name", ""),
                device_address=data.get("address", ""),
                protocol=data.get("protocol", "googlecast"),
                credentials=data.get("credentials"),
            )
            return web.json_response({"success": True})
        except Exception as e:
            return web.json_response({"success": False, "error": str(e)})

    async def _handle_discover_devices(self, request: web.Request) -> web.Response:
        """Discover available devices."""
        try:
            devices = await discover_all_devices(timeout=5)
            device_list = [
                {
                    "id": d.id,
                    "name": d.name,
                    "address": d.address,
                    "protocol": d.protocol,
                }
                for d in devices
            ]
            return web.json_response(device_list)
        except Exception:
            return web.json_response([])

    async def _handle_list_audio(self, request: web.Request) -> web.Response:
        """List available audio files."""
        files = list_audio_files()
        # Filter out hidden files and recording file
        file_names = [
            f.name
            for f in files
            if not f.name.startswith("_") and not f.name.startswith(".")
        ]
        return web.json_response(file_names)

    async def _handle_stream(self, request: web.Request) -> web.Response:
        """Stream an audio file to the configured device."""
        try:
            data = await request.json()
            filename = data.get("filename")

            if not filename:
                return web.json_response({"success": False, "error": "No filename"})

            audio_file = AUDIO_DIR / filename
            if not audio_file.exists():
                return web.json_response({"success": False, "error": "File not found"})

            config = load_config()
            if not config:
                return web.json_response(
                    {"success": False, "error": "No device configured"}
                )

            # Run streaming in background
            await stream_audio(config, audio_file)
            return web.json_response({"success": True})

        except Exception as e:
            return web.json_response({"success": False, "error": str(e)})

    async def _handle_record(self, request: web.Request) -> web.Response:
        """Record audio and stream it."""
        try:
            data = await request.json()
            duration = data.get("duration", 10)

            config = load_config()
            if not config:
                return web.json_response(
                    {"success": False, "error": "No device configured"}
                )

            # Run in executor since record_audio is blocking
            loop = asyncio.get_event_loop()
            audio_file = await loop.run_in_executor(None, record_audio, duration)

            # Stream the recording
            await stream_audio(config, audio_file)
            return web.json_response({"success": True})

        except Exception as e:
            return web.json_response({"success": False, "error": str(e)})

    async def _handle_live_start(self, request: web.Request) -> web.Response:
        """Start live broadcast."""
        try:
            if self.live_broadcaster and self.live_broadcaster.broadcasting:
                return web.json_response(
                    {"success": False, "error": "Already broadcasting"}
                )

            config = load_config()
            if not config:
                return web.json_response(
                    {"success": False, "error": "No device configured"}
                )

            device_id = config["device"]["id"]
            device_name = config["device"]["name"]
            protocol = config["device"].get("protocol", "airplay")
            credentials = config["device"].get("credentials")

            device = await find_device_by_id(device_id, protocol)
            if not device:
                device = await find_device_by_id(device_name, protocol)

            if not device:
                return web.json_response(
                    {"success": False, "error": "Device not found"}
                )

            if protocol == "airplay" and not credentials:
                return web.json_response({"success": False, "error": "No credentials"})

            # Start broadcaster in background task
            self.live_broadcaster = LiveBroadcaster(
                port=8766
            )  # Different port than web

            async def run_broadcast():
                try:
                    await self.live_broadcaster.broadcast(device, credentials)
                except Exception as e:
                    print(f"❌ Broadcast error: {e}")

            self.live_task = asyncio.create_task(run_broadcast())

            # Wait a bit for it to start
            await asyncio.sleep(1)

            if self.live_broadcaster.broadcasting:
                return web.json_response({"success": True})
            else:
                return web.json_response({"success": False, "error": "Failed to start"})

        except Exception as e:
            return web.json_response({"success": False, "error": str(e)})

    async def _handle_live_stop(self, request: web.Request) -> web.Response:
        """Stop live broadcast."""
        try:
            if self.live_broadcaster:
                self.live_broadcaster.broadcasting = False
                if self.live_task:
                    self.live_task.cancel()
                    try:
                        await self.live_task
                    except asyncio.CancelledError:
                        pass
                self.live_broadcaster = None
                self.live_task = None

            return web.json_response({"success": True})
        except Exception as e:
            return web.json_response({"success": False, "error": str(e)})

    async def start(self):
        """Start the web server."""
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()

        site = web.TCPSite(self.runner, "0.0.0.0", self.port)
        await site.start()

        local_ip = self._get_local_ip()
        print(f"""
🌐 Web GUI Started!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  📱 From phone:  http://{local_ip}:{self.port}
  💻 From this computer:  http://localhost:{self.port}

Press Ctrl+C to stop.
""")

    async def stop(self):
        """Stop the web server."""
        if self.live_broadcaster:
            self.live_broadcaster.broadcasting = False
        if self.live_task:
            self.live_task.cancel()
        if self.runner:
            await self.runner.cleanup()


async def run_web_server():
    """Run the web server."""
    import os
    import signal

    server = WebServer()
    await server.start()

    # Force exit on Ctrl+C
    def force_exit(sig, frame):
        print("\n⏹️  Server stopped.")
        os._exit(0)

    signal.signal(signal.SIGINT, force_exit)
    signal.signal(signal.SIGTERM, force_exit)

    # Keep running forever
    while True:
        await asyncio.sleep(3600)


def print_usage():
    """Print usage information."""
    print("""
Audio Streamer (AirPlay + Google Cast)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Usage:
  python main.py              # Stream audio (setup if needed)
  python main.py --web        # Start web GUI (access from phone!)
  python main.py --setup      # Force device setup
  python main.py --pair       # Pair with device (AirPlay only)
  python main.py --list       # List available devices
  python main.py --live       # Live broadcast from microphone
  python main.py --record     # Record from mic and stream (default 10s)
  python main.py --record 30  # Record for 30 seconds
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

    # Handle --web
    if "--web" in args:
        await run_web_server()
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

    # Handle --record
    if "--record" in args:
        config = load_config()
        if not config:
            print("⚙️  No device configured. Running setup first...\n")
            config = await setup_device()
            if not config:
                print("Setup cancelled.")
                return

        # Get duration from args (default 10 seconds)
        duration = 10
        record_idx = args.index("--record")
        if record_idx + 1 < len(args):
            try:
                duration = int(args[record_idx + 1])
            except ValueError:
                pass

        # Record audio
        audio_file = record_audio(duration)

        # Stream the recording
        await stream_audio(config, audio_file)
        return

    # Handle --live
    if "--live" in args:
        config = load_config()
        if not config:
            print("⚙️  No device configured. Running setup first...\n")
            config = await setup_device()
            if not config:
                print("Setup cancelled.")
                return

        device_id = config["device"]["id"]
        device_name = config["device"]["name"]
        protocol = config["device"].get("protocol", "airplay")
        credentials = config["device"].get("credentials")

        print(f"🔍 Looking for device: {device_name}...")

        device = await find_device_by_id(device_id, protocol)
        if not device:
            device = await find_device_by_id(device_name, protocol)

        if not device:
            print(
                f"❌ Device '{device_name}' not found. Run with --setup to reconfigure."
            )
            return

        if protocol == "airplay" and not credentials:
            print("⚠️  No credentials found. Run with --pair to authenticate.")
            return

        broadcaster = LiveBroadcaster()
        await broadcaster.broadcast(device, credentials)
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
