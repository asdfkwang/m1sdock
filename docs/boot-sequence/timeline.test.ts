import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { ADDRESSES, durationOf, hex, initialPlayback, locateBeat, playbackReducer, scenes, snapshotAt } from './timeline.ts';

test('both playable scenes have a finite, ordered timeline', () => {
  assert.equal(scenes.length, 2);
  for (const scene of scenes) {
    assert.equal(new Set(scene.beats.map(beat => beat.id)).size, scene.beats.length);
    assert.ok(scene.beats.every(beat => beat.duration > 0));
    let elapsed = 0;
    scene.beats.forEach((beat, index) => {
      assert.equal(locateBeat(scene, elapsed).beat.id, beat.id);
      assert.equal(locateBeat(scene, elapsed).index, index);
      assert.equal(locateBeat(scene, elapsed).progress, 0);
      elapsed += beat.duration;
    });
    assert.equal(locateBeat(scene, durationOf(scene)).progress, 1);
    assert.equal(locateBeat(scene, durationOf(scene)).index, scene.beats.length - 1);
  }
});

test('D0 waits until both flags are published and clears them before loader setup', () => {
  const index = (id: string) => scenes[1].beats.findIndex(beat => beat.id === id);
  assert.deepEqual(snapshotAt(1, index('d0-wait')).flags, [null, null]);
  assert.equal(snapshotAt(1, index('d0-wait')).d0Heap, false);
  assert.deepEqual(snapshotAt(1, index('flag-one')).flags, [ADDRESSES.ready, null]);
  assert.deepEqual(snapshotAt(1, index('flag-two')).flags, [ADDRESSES.ready, ADDRESSES.ready]);
  assert.deepEqual(snapshotAt(1, index('d0-consume')).flags, [0, 0]);
  assert.equal(snapshotAt(1, index('d0-consume')).d0Sections, false);
  assert.equal(snapshotAt(1, index('d0-ready')).d0Heap, true);
});

test('scene navigation reconstructs prerequisites and removes later side effects', () => {
  const enteredD0 = snapshotAt(1, -1);
  assert.equal(enteredD0.m0Heap, true);
  assert.equal(enteredD0.psramReady, true);
  assert.equal(enteredD0.d0Stack, false);
  assert.deepEqual(enteredD0.flags, [null, null]);
  const resetM0 = snapshotAt(0, -1);
  assert.equal(resetM0.m0Stack, false);
  assert.equal(resetM0.d0Heap, false);
  assert.equal(resetM0.psramReady, false);
  assert.deepEqual(resetM0.flags, [null, null]);
});

test('pause, resume and scene changes reject an old animation clock', () => {
  let state = playbackReducer(initialPlayback, { type: 'select', scene: 0, animate: true });
  const oldRun = state.run;
  state = playbackReducer(state, { type: 'tick', elapsed: 500, run: oldRun });
  state = playbackReducer(state, { type: 'pause' });
  assert.equal(playbackReducer(state, { type: 'tick', elapsed: 900, run: oldRun }), state);
  state = playbackReducer(state, { type: 'resume' });
  assert.equal(state.elapsed, 500);
  assert.equal(playbackReducer(state, { type: 'tick', elapsed: 2000, run: oldRun }), state);
  state = playbackReducer(state, { type: 'select', scene: 1, animate: true });
  assert.equal(state.elapsed, 0);
  assert.equal(playbackReducer(state, { type: 'tick', elapsed: 10000, run: oldRun }), state);
});

test('each scene stops at its own end, and replay starts a new run', () => {
  let state = playbackReducer(initialPlayback, { type: 'select', scene: 0, animate: true });
  state = playbackReducer(state, { type: 'tick', elapsed: 1e9, run: state.run });
  assert.equal(state.scene, 0);
  assert.equal(state.elapsed, durationOf(scenes[0]));
  assert.equal(state.playing, false);
  const run = state.run;
  state = playbackReducer(state, { type: 'replay', animate: true });
  assert.equal(state.elapsed, 0);
  assert.equal(state.playing, true);
  assert.ok(state.run > run);
  assert.equal(playbackReducer(state, { type: 'select', scene: -1, animate: true }), state);
  assert.equal(playbackReducer(state, { type: 'select', scene: 2, animate: true }), state);
});

test('reduced motion goes directly to a stable final snapshot', () => {
  const state = playbackReducer(initialPlayback, { type: 'select', scene: 1, animate: false });
  assert.equal(state.playing, false);
  assert.equal(state.elapsed, durationOf(scenes[1]));
  assert.equal(snapshotAt(state.scene, locateBeat(scenes[1], state.elapsed).index).d0Heap, true);
});

test('stack and heap bounds match the checked-in linker scripts', () => {
  const source = (name: string) => readFileSync(new URL(`../../M1s_BL808_Linux_SDK/bl_mcu_sdk_bl808/${name}`, import.meta.url), 'utf8');
  for (const [cpu, file] of [
    ['m0', 'drivers/bl808_driver/startup/m0/bl808_flash.ld'],
    ['d0', 'examples/low_load/bl808_flash_d0.ld'],
  ] as const) {
    const text = source(file);
    const region = (name: string) => {
      const match = text.match(new RegExp(`^\\s*${name}\\s+[^:]+:\\s*ORIGIN\\s*=\\s*(0x[\\da-f]+),\\s*LENGTH\\s*=\\s*(\\d+)K`, 'im'));
      assert.ok(match, `${cpu}: ${name}`);
      return Number.parseInt(match[1], 16) + Number(match[2]) * 1024;
    };
    const stackSize = Number.parseInt(text.match(/StackSize\s*=\s*(0x[\da-f]+)/i)![1], 16);
    const top = ADDRESSES[cpu === 'm0' ? 'm0StackTop' : 'd0StackTop'];
    assert.equal(top, region('dtcm_memory'));
    assert.equal(top - stackSize, ADDRESSES[cpu === 'm0' ? 'm0StackLimit' : 'd0StackLimit']);
    assert.equal(region('ram_memory'), ADDRESSES[cpu === 'm0' ? 'm0HeapLimit' : 'd0HeapLimit']);
  }
});

test('shared readiness values match the SDK definitions', () => {
  const header = readFileSync(new URL('../../M1s_BL808_Linux_SDK/bl_mcu_sdk_bl808/drivers/bl808_driver/regs/bl808.h', import.meta.url), 'utf8');
  for (const [symbol, expected] of [['IPC_SYNC_ADDR1', ADDRESSES.flag1], ['IPC_SYNC_ADDR2', ADDRESSES.flag2], ['IPC_SYNC_FLAG', ADDRESSES.ready]] as const) {
    assert.equal(Number.parseInt(header.match(new RegExp(`#define\\s+${symbol}\\s+(0x[\\da-f]+)`, 'i'))![1], 16), expected);
  }
  assert.equal(hex(ADDRESSES.ready), '0x1234_5678');
});
