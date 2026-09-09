'use strict';

const assert = require('node:assert/strict');
const path = require('node:path');
const test = require('node:test');

const {
  createBackendSpec,
  startBackend,
  stopBackend
} = require('../backend-process');

const serviceArgs = ['--source', 'system', '--model', 'base', '--auth-token', 'test-token', 'serve'];

test('packaged app launches the embedded Windows backend executable', () => {
  const spec = createBackendSpec({
    isPackaged: true,
    resourcesPath: 'C:\\Program Files\\WPMChecker\\resources',
    appPath: 'C:\\unused',
    platform: 'win32',
    authToken: 'test-token'
  });

  assert.equal(
    spec.command,
    path.join('C:\\Program Files\\WPMChecker\\resources', 'backend', 'wpmchecker-backend.exe')
  );
  assert.deepEqual(spec.args, serviceArgs);
  assert.equal(spec.cwd, path.join('C:\\Program Files\\WPMChecker\\resources', 'backend'));
});

test('development app uses the repository virtualenv launcher when present', () => {
  const electronDir = path.join('/workspace', 'WPMChecker', 'electron');
  const expected = path.join('/workspace', 'WPMChecker', '.venv', 'bin', 'wpmchecker');
  const spec = createBackendSpec({
    isPackaged: false,
    resourcesPath: '/unused',
    appPath: electronDir,
    platform: 'linux',
    authToken: 'test-token',
    existsSync: (candidate) => candidate === expected
  });

  assert.equal(spec.command, expected);
  assert.deepEqual(spec.args, serviceArgs);
  assert.equal(spec.cwd, path.join('/workspace', 'WPMChecker'));
});

test('development app falls back to Python module execution', () => {
  const spec = createBackendSpec({
    isPackaged: false,
    resourcesPath: '/unused',
    appPath: path.join('/workspace', 'WPMChecker', 'electron'),
    platform: 'linux',
    authToken: 'test-token',
    existsSync: () => false,
    env: { PYTHON: '/custom/python' }
  });

  assert.equal(spec.command, '/custom/python');
  assert.deepEqual(spec.args, ['-m', 'wpmchecker', ...serviceArgs]);
});

test('backend starts hidden and reports spawn errors', () => {
  const calls = [];
  let errorHandler;
  const child = {
    killed: false,
    on(event, handler) {
      if (event === 'error') errorHandler = handler;
    },
    kill() {}
  };
  const error = new Error('spawn failed');
  let reported;

  const result = startBackend(
    { command: 'backend.exe', args: serviceArgs, cwd: 'C:\\app' },
    {
      spawnImpl(command, args, options) {
        calls.push({ command, args, options });
        return child;
      },
      onError: (value) => { reported = value; }
    }
  );
  errorHandler(error);

  assert.equal(result, child);
  assert.deepEqual(calls, [{
    command: 'backend.exe',
    args: serviceArgs,
    options: { cwd: 'C:\\app', windowsHide: true, stdio: 'ignore' }
  }]);
  assert.equal(reported, error);
});

test('backend shutdown terminates a live non-Windows child only once', () => {
  let kills = 0;
  const child = { killed: false, kill: () => { kills += 1; child.killed = true; } };

  stopBackend(child, { platform: 'linux' });
  stopBackend(child, { platform: 'linux' });
  stopBackend(undefined, { platform: 'linux' });

  assert.equal(kills, 1);
});

test('backend shutdown terminates the complete Windows process tree only once', () => {
  const calls = [];
  const child = { pid: 4242, killed: false, kill: () => assert.fail('must use taskkill') };
  const spawnSyncImpl = (command, args, options) => calls.push({ command, args, options });

  stopBackend(child, { platform: 'win32', spawnSyncImpl });
  stopBackend(child, { platform: 'win32', spawnSyncImpl });

  assert.deepEqual(calls, [{
    command: 'taskkill.exe',
    args: ['/PID', '4242', '/T', '/F'],
    options: { windowsHide: true, stdio: 'ignore' }
  }]);
});
