# WPMChecker

WPMChecker is a Windows 10/11 realtime WPM (Words Per Minute) overlay for English learners. It listens to the microphone or the current Windows playback device, recognizes English speech locally with `faster-whisper`, calculates WPM, and displays it in a small always-on-top window.

## Install on Windows

No Python or Node.js installation is required for the packaged app.

1. Open [GitHub Releases](https://github.com/ukyamyam/WPMChecker/releases).
2. Download one of these files:
   - `WPMChecker-Setup-<version>-x64.exe` — normal installer; recommended.
   - `WPMChecker-Portable-<version>-x64.exe` — portable version with no installation.
3. Run the downloaded file.
4. Verify the file against `SHA256SUMS.txt` on the same release page.
5. The current community build is not Authenticode-signed. If Windows SmartScreen appears, proceed only when the file came from the official `ukyamyam/WPMChecker` release and its SHA-256 matches; otherwise delete it.

The Electron window starts and stops its bundled Python backend automatically. You do not need to open a terminal or install the source dependencies.

### First launch

The packaged application includes Python, audio libraries, Whisper runtime, and the desktop UI. The Whisper `base` speech model is downloaded on first launch and cached for later launches, so the first start requires an internet connection and may take a few minutes. Subsequent launches use the local cache.

Windows may ask for microphone permission. Allow it if you want to use microphone input. System-audio mode captures the current default Windows playback device through WASAPI loopback.

### Using the overlay

Right-click the overlay to change:

- **Input Source** — System audio or Microphone.
- **WPM Mode** — Effective speech WPM or Elapsed-time WPM.
- **Window Seconds** — 3, 5, 7, or 10 seconds.
- **Quit** — closes both the overlay and bundled backend.

The dot in the upper-right turns green after the local backend connects.

## Architecture

WPMChecker uses two bundled processes:

- **Python backend**: audio capture → VAD → faster-whisper → word timestamps → WPM calculation → local WebSocket.
- **Electron frontend**: always-on-top overlay, controls, and WPM display.

The processes communicate only over `ws://127.0.0.1:8765`. On every launch, Electron generates a random authentication token and requires it for WebSocket data and commands. The packaged Electron app launches `resources/backend/wpmchecker-backend.exe`, enforces a single running application instance, and terminates the complete backend process tree when the app exits.

`web/probe.html` remains available as a development-only browser client.

## Build from source

### Requirements

- Windows 10/11.
- Python 3.10+; Python 3.11 is used for release builds.
- Node.js 20+.
- CPU is supported; a compatible GPU is optional and auto-detected by CTranslate2/faster-whisper.

### Development setup

```powershell
git clone https://github.com/ukyamyam/WPMChecker.git
cd WPMChecker

py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev,build]"

cd electron
npm install
cd ..
```

Start the desktop application from the repository root:

```powershell
cd electron
npm start
```

Development mode automatically finds `.venv\Scripts\wpmchecker.exe` and launches the backend. On Linux/macOS, audio capture falls back to synthetic input because Windows WASAPI loopback is unavailable.

## Stage-by-stage backend verification

Run these commands from the repository root.

### 1. Check audio levels

```powershell
# Current default Windows playback device
.\.venv\Scripts\wpmchecker.exe --source system level

# Microphone
.\.venv\Scripts\wpmchecker.exe --source mic level
```

Backend-specific diagnostics:

```powershell
.\.venv\Scripts\wpmchecker.exe --source system --backend soundcard level
.\.venv\Scripts\wpmchecker.exe --source system --backend pyaudiowpatch level
```

The default `--backend auto` tries `soundcard` first and then `pyaudiowpatch`. WPMChecker periodically re-resolves the default device so switching to AirPods or another output can be followed automatically.

### 2. Check VAD and Whisper words

```powershell
.\.venv\Scripts\wpmchecker.exe --source system --model base words
```

Expected output resembles:

```text
12345.67-12345.89 hello
12346.02-12346.30 world
```

No-audio/no-model test:

```powershell
.\.venv\Scripts\wpmchecker.exe --backend synthetic --mock-whisper words
```

### 3. Check console WPM

```powershell
.\.venv\Scripts\wpmchecker.exe --source system --model base --mode effective --window 5 wpm
```

### 4. Check WebSocket and browser probe

```powershell
.\.venv\Scripts\wpmchecker.exe --source system --model base serve
```

Open `web/probe.html` in a browser. It connects to `ws://127.0.0.1:8765`.

For a deterministic smoke test:

```powershell
.\.venv\Scripts\wpmchecker.exe --backend synthetic --mock-whisper serve
```

## Build Windows packages locally

```powershell
# Repository root
.\.venv\Scripts\pyinstaller.exe --noconfirm --clean packaging/wpmchecker-backend.spec

cd electron
npm ci
npm test
npm run build:win
```

Outputs are written to `release/`:

- `WPMChecker-Setup-<version>-x64.exe`
- `WPMChecker-Portable-<version>-x64.exe`
- `SHA256SUMS.txt`

The GitHub Actions workflow `.github/workflows/windows-build.yml` performs the same build on `windows-latest`, smoke-tests the frozen backend and process-tree cleanup, uploads workflow artifacts, and attaches the executables and checksums to releases for `v*` tags. Build jobs have read-only repository permission; write permission exists only in the tag-only publishing job.

### Release procedure

Keep the version identical in `pyproject.toml`, `backend/wpmchecker/__init__.py`, and `electron/package.json` (including its lockfile), then verify and tag:

```powershell
python packaging/check_release_version.py vX.Y.Z
git tag -a vX.Y.Z -m "WPMChecker X.Y.Z"
git push origin vX.Y.Z
```

The release workflow rejects a tag that does not match the application versions.

## WPM calculation

Default mode is **effective speech WPM**:

```text
WPM = words_in_recent_window / VAD_speech_seconds_in_recent_window * 60
```

This excludes pauses. `elapsed` mode includes silence. If no speech is detected for three seconds, the display becomes `--`.

Speed zones:

- `< 120`: slow, blue.
- `120–179`: natural, green.
- `180–239`: fast, yellow.
- `>= 240`: very fast, red.

An EMA with alpha `0.3` smooths the display.

## Troubleshooting

### Overlay says `backend offline`

- Wait for the first-run Whisper model download to finish.
- Ensure another WPMChecker/backend process is not already using port `8765`.
- Close and reopen WPMChecker.

### System audio is silent

1. Confirm audio is playing through the expected Windows output device.
2. Open **Settings → System → Sound → Output** and verify the default output.
3. If using AirPods/Bluetooth, make sure they are the active output device.
4. Use the backend-specific level commands above to determine whether `soundcard` or `pyaudiowpatch` works on the machine.
5. Switch to microphone from the overlay menu to confirm the pipeline is running.

### Microphone is silent

Open **Settings → Privacy & security → Microphone** and allow desktop applications to access the microphone.

## Tests

```bash
python -m pytest -q
cd electron
npm ci
npm audit
npm test
```

Automated tests cover WPM math, speech idle behavior, zones, deduplication, CLI entrypoint behavior, packaged backend path resolution, process lifecycle, and package configuration. Windows audio hardware and recognition accuracy still require a target-device check.
