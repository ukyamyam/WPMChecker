'use strict';

const { spawn, spawnSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const SERVICE_ARGS = ['--source', 'system', '--model', 'base'];
const stoppedChildren = new WeakSet();

function buildServiceArgs(authToken) {
  const args = [...SERVICE_ARGS];
  if (authToken) args.push('--auth-token', authToken);
  args.push('serve');
  return args;
}

function createBackendSpec({
  isPackaged,
  resourcesPath,
  appPath,
  authToken,
  platform = process.platform,
  existsSync = fs.existsSync,
  env = process.env
}) {
  const args = buildServiceArgs(authToken);
  if (isPackaged) {
    const backendDir = path.join(resourcesPath, 'backend');
    return {
      command: path.join(backendDir, 'wpmchecker-backend.exe'),
      args,
      cwd: backendDir
    };
  }

  const projectRoot = path.dirname(appPath);
  const launcher = platform === 'win32'
    ? path.join(projectRoot, '.venv', 'Scripts', 'wpmchecker.exe')
    : path.join(projectRoot, '.venv', 'bin', 'wpmchecker');

  if (existsSync(launcher)) {
    return { command: launcher, args, cwd: projectRoot };
  }

  return {
    command: env.PYTHON || (platform === 'win32' ? 'python.exe' : 'python3'),
    args: ['-m', 'wpmchecker', ...args],
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

function stopBackend(
  child,
  { platform = process.platform, spawnSyncImpl = spawnSync } = {}
) {
  if (!child || child.killed || stoppedChildren.has(child)) return;
  stoppedChildren.add(child);

  if (platform === 'win32' && Number.isInteger(child.pid)) {
    const result = spawnSyncImpl(
      'taskkill.exe',
      ['/PID', String(child.pid), '/T', '/F'],
      { windowsHide: true, stdio: 'ignore' }
    );
    if (result && result.error && !child.killed) child.kill();
    return;
  }

  child.kill();
}

module.exports = {
  SERVICE_ARGS,
  buildServiceArgs,
  createBackendSpec,
  startBackend,
  stopBackend
};
