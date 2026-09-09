# Windows All-in-One App Implementation Plan

> **For Hermes:** Use test-driven development and execute this plan task-by-task.

**Goal:** Ship WPMChecker as a Windows installer that launches the Python speech backend and Electron overlay together without requiring users to install Python or Node.js.

**Architecture:** PyInstaller builds `wpmchecker-backend.exe`. electron-builder packages the Electron shell and embeds that backend under `resources/backend`. Electron resolves the development or packaged backend command, starts it before opening the window, and terminates it when the app exits. GitHub Actions builds on Windows and publishes a downloadable installer artifact/release.

**Tech Stack:** Python 3.11, PyInstaller, Electron, Node.js test runner, electron-builder/NSIS, GitHub Actions.

---

### Task 1: Add a testable backend launcher

**Files:**
- Create: `electron/backend-process.js`
- Create: `electron/test/backend-process.test.js`
- Modify: `electron/main.js`
- Modify: `electron/package.json`

1. Write Node tests for packaged path resolution, development fallback, spawn arguments, and safe shutdown.
2. Run `npm test` and verify RED because the module does not exist.
3. Implement the minimal launcher and connect it to Electron lifecycle events.
4. Run `npm test` and verify GREEN.

### Task 2: Package the Python backend

**Files:**
- Create: `packaging/wpmchecker-backend.spec`
- Modify: `pyproject.toml`
- Modify: `electron/package.json`

1. Add PyInstaller as a build-only dependency.
2. Define a Windows one-file console-free backend build that collects `faster_whisper`, `ctranslate2`, `soundcard`, `pyaudiowpatch`, and WebRTC VAD runtime data/binaries.
3. Configure electron-builder to embed `dist/wpmchecker-backend.exe` as an extra resource and generate an NSIS installer plus portable executable.
4. Verify package configuration syntax locally.

### Task 3: Add Windows CI and release automation

**Files:**
- Create: `.github/workflows/windows-build.yml`

1. Run Python tests and Node tests on `windows-latest`.
2. Build the Python executable and Electron installer.
3. Smoke-test backend startup with synthetic audio and mock Whisper.
4. Upload installer/portable artifacts on pushes and attach them to GitHub Releases on version tags.

### Task 4: Document installation and operation

**Files:**
- Modify: `README.md`

1. Put the downloadable installer workflow first.
2. Explain first-run Whisper model download, Windows microphone permissions, system/mic switching, and source-build fallback.
3. Document release/tagging workflow.

### Task 5: Verify and publish

1. Run Python and Node tests locally.
2. Push feature branch, inspect GitHub Actions output, and fix failures.
3. Merge to `main` after green checks.
4. Change repository visibility to public.
5. Tag `v0.2.0`, wait for the release build, and verify downloadable Windows assets exist.
