'use strict';

const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const SERVICE_ARGS = ['--source', 'system', '--model', 'base', 'serve'];

function createBackendSpec({
  isPackaged,
  resourcesPath,
  appPath,
  platform = process.platform,
  existsSync = fs.existsSync,
  env = process.env
}) {
  if (isPackaged) {
    const backendDir = path.join(resourcesPath, 'backend');
    return {
      command: path.join(backendDir, 'wpmchecker-backend.exe'),
      args: [...SERVICE_ARGS],
      cwd: backendDir
    };
  }

  const projectRoot = path.dirname(appPath);
  const launcher = platform === 'win32'
    ? path.join(projectRoot, '.venv', 'Scripts', 'wpmchecker.exe')
    : path.join(projectRoot, '.venv', 'bin', 'wpmchecker');

  if (existsSync(launcher)) {
    return { command: launcher, args: [...SERVICE_ARGS], cwd: projectRoot };
  }

  return {
    command: env.PYTHON || (platform === 'win32' ? 'python.exe' : 'python3'),
    args: ['-m', 'wpmchecker', ...SERVICE_ARGS],
    cwd: projectRoot
  };
}

function startBackend(spec, { spawnImpl = spawn, onError = console.error } = {}) {
  const child = spawnImpl(spec.command, spec.args, {
    cwd: spec.cwd,
    windowsHide: true,
    stdio: 'ignore'
  });
  child.on('error', onError);
  return child;
}

function stopBackend(child) {
  if (child && !child.killed) child.kill();
}

module.exports = { SERVICE_ARGS, createBackendSpec, startBackend, stopBackend };
