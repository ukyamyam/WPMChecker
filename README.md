# WPMChecker

WPMChecker is a Windows-focused realtime WPM (Words Per Minute) overlay for English learners. It listens to either the microphone or the PC's current default playback device via WASAPI loopback, recognizes English speech with `faster-whisper`, calculates WPM on the Python side, and sends display-only updates to a small Electron window over WebSocket.

## Architecture

WPMChecker intentionally uses two processes:

- **Python backend**: audio capture → VAD → faster-whisper → word timestamp stream → WPM calculation → WebSocket broadcast.
- **Electron frontend**: a thin always-on-top window that only renders the latest WebSocket payload and forwards menu commands.

All recognition, deduplication, source switching, and WPM math live in Python. Electron is deliberately small so the audio/Whisper path can be developed and verified independently first.

## Current stage layout

- `backend/wpmchecker/audio.py`: microphone/system capture abstraction.
- `backend/wpmchecker/vad.py`: WebRTC VAD segmenter.
- `backend/wpmchecker/whispering.py`: `faster-whisper` wrapper and mock recognizer for UI tests.
- `backend/wpmchecker/wpm.py`: effective/elapsed WPM calculation and speed zones.
- `backend/wpmchecker/server.py`: WebSocket backend and runtime commands.
- `web/probe.html`: simple browser client for stage 4 verification.
- `electron/`: final small overlay window.

## Requirements

### Windows runtime

- Windows 10/11.
- Python 3.10+.
- Node.js 20+ for Electron.
- CPU is supported; GPU is optional and auto-detected by CTranslate2/faster-whisper.

### Python dependencies

Installed by `pip install -e .`:

- `faster-whisper`
- `numpy`
- `webrtcvad-wheels`
- `websockets`
- `soundcard` on Windows
- `pyaudiowpatch` on Windows

`faster-whisper` downloads the selected model on first use. The backend prints a model loading message; Hugging Face / faster-whisper show download progress through their cache tooling. Default model is `base`; `small` is also recommended. The default compute type is `int8` for CPU-friendly operation.

## Setup

```powershell
# Clone
gh repo clone ukyamyam/WPMChecker
cd WPMChecker

# Python backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

# Electron frontend
cd electron
npm install
cd ..
```

On Linux/macOS development machines, system loopback is not enabled by this app. Use `--backend synthetic` to test the pipeline and UI without Windows audio.

## Stage-by-stage verification

Run every command from the repository root with the Python virtualenv activated.

### 1. Verify default playback loopback or microphone levels

```powershell
# System audio from current default Windows playback device
wpmchecker --source system level

# Microphone
wpmchecker --source mic level
```

You should see `level=...` values and bars change while YouTube, a podcast, AirPods output, or microphone speech is active.

Backend selection:

```powershell
wpmchecker --source system --backend soundcard level
wpmchecker --source system --backend pyaudiowpatch level
```

The default `--backend auto` tries `soundcard` first and falls back to `pyaudiowpatch`. The implementation re-resolves the default device periodically. If AirPods or another Bluetooth output becomes the OS default device, the capture reconnects to follow it instead of staying attached to an old endpoint.

### 2. Verify VAD + faster-whisper word timestamps

```powershell
wpmchecker --source system --model base words
```

Expected console output:

```text
12345.67-12345.89 hello
12346.02-12346.30 world
```

For UI/pipeline testing without downloading a model:

```powershell
wpmchecker --backend synthetic --mock-whisper words
```

### 3. Verify console WPM

```powershell
wpmchecker --source system --model base --mode effective --window 5 wpm
```

Modes:

- `effective`: default. `words / VAD speech seconds * 60`. Silence is excluded from the denominator.
- `elapsed`: `words / window seconds * 60`. Silence is included.

If no speech is detected for 3 seconds, the display becomes `--`.

### 4. Verify WebSocket + browser page

```powershell
wpmchecker --source system --model base serve
```

Open `web/probe.html` in a browser. It connects to `ws://127.0.0.1:8765` and displays WPM, mode, source, zone, and level.

For a no-audio/no-model demo:

```powershell
wpmchecker --backend synthetic --mock-whisper serve
```

### 5. Run the Electron overlay

Keep the backend running:

```powershell
wpmchecker --source system --model base serve
```

Then in another terminal:

```powershell
cd electron
npm start
```

The overlay is frameless, small, draggable, transparent, and always on top. Right-click it for:

- Input source: System audio / Microphone.
- WPM mode: Effective speech WPM / Elapsed-time WPM.
- Window seconds: 3 / 5 / 7 / 10.
- Quit.

## WPM definition and speed zones

Default WPM is **effective speech WPM**:

```text
WPM = words_in_recent_window / VAD_speech_seconds_in_recent_window * 60
```

This avoids unrealistic drops when a speaker pauses. `elapsed` mode is available when you explicitly want silence included.

Speed zones:

- `< 120`: slow, blue.
- `120–179`: natural, green.
- `180–239`: fast, yellow.
- `>= 240`: very fast, red.

An EMA with alpha `0.3` smooths the display so individual recognition bursts do not make the number jump excessively.

## Recognition/chunking strategy

The backend receives 30 ms mono chunks, runs WebRTC VAD, and closes an utterance after a trailing silence window. Each utterance segment goes to `faster-whisper` with `word_timestamps=True`. Returned words are stored as:

```python
(word, start_time, end_time)
```

When a future sliding-window recognizer is enabled, overlapping chunks can produce duplicate words. `WordDeduplicator` already prevents double counts by comparing normalized word text and near-identical timestamps while allowing genuine repeated words with different timestamps.

## Troubleshooting loopback silence

If system audio is silent:

1. Confirm the browser/player is audible through Windows.
2. Open Windows **Settings → System → Sound → Output** and check the selected default output device.
3. If using AirPods/Bluetooth, make sure they are the active output device, not just connected.
4. Run:
   ```powershell
   wpmchecker --source system --backend soundcard level
   wpmchecker --source system --backend pyaudiowpatch level
   ```
   Use whichever backend shows levels.
5. Toggle to microphone from the overlay context menu to confirm the backend is alive.
6. Restart the backend after changing audio drivers if both loopback backends remain silent.

## Tests

```bash
python -m pytest -q
```

The automated tests cover WPM math, speech idle behavior, zones, word counting, and overlap deduplication. Hardware audio and Whisper accuracy require manual stage checks on Windows.
