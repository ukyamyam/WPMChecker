'use strict';

const assert = require('node:assert/strict');
const path = require('node:path');
const test = require('node:test');

const pkg = require('../package.json');

test('Windows package embeds the frozen backend executable', () => {
  assert.deepEqual(pkg.build.extraResources, [{
    from: '../dist/wpmchecker-backend.exe',
    to: 'backend/wpmchecker-backend.exe'
  }]);
});

test('Windows package produces an installer and portable executable', () => {
  const targets = pkg.build.win.target.map((entry) => typeof entry === 'string' ? entry : entry.target);
  assert.deepEqual(targets, ['nsis', 'portable']);
  assert.equal(pkg.build.directories.output, '../release');
  assert.match(pkg.scripts['build:win'], /electron-builder --win/);
});

test('npm test uses the built-in Node test runner', () => {
  assert.equal(pkg.scripts.test, 'node --test');
});
