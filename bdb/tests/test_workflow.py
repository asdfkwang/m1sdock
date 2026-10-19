"""Hardware-free CLI tests. Build bdb first, then run this file with python3."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

BIN = Path(__file__).resolve().parents[1] / 'target/debug/bdb'

FAKE_LOADER = r'''
import configparser, json, os, time
from pathlib import Path
def event(text):
    with open(os.environ['TEST_EVENTS'], 'a') as stream: stream.write(text + '\n')
class BL808EflashLoader:
    def __init__(self, chip, args, values):
        self.args, self.values = args, values
        self.bflb_serial_object = None
        self._bflb_com_tx_size = 4104
    def run_step(self):
        self.bflb_serial_object = object()
        event('open')
        if os.environ.get('TEST_FAIL') == 'handshake':
            print('[All Success]')  # Must not override the boolean failure.
            return False, 'handshake'
        memory = Path(os.environ['TEST_MEMORY'])
        data = bytearray(memory.read_bytes())
        if self.args.write:
            txn = json.loads((Path(os.environ['XDG_RUNTIME_DIR']) / 'bdb/txn.json').read_text())
            assert txn['status'] == 'running' and txn['regions']
            assert all(r['src_sha256'] for r in txn['regions'])
            cfg = configparser.ConfigParser(); cfg.read(self.values.config)
            for section in cfg.sections():
                if section == 'cfg': continue
                start = int(cfg[section]['address'], 0)
                body = Path(cfg[section]['filedir']).read_bytes()
                data[start:start + len(body)] = body
            memory.write_bytes(data)
            event('write')
        return True, 'done'
    def flash_read_main_process(self, start, size, shake, file, callback):
        assert 0 < size <= 4096
        event(f'read {start} {size}')
        failure = os.environ.get('TEST_FAIL')
        if failure == 'timeout': time.sleep(20)
        body = Path(os.environ['TEST_MEMORY']).read_bytes()[start:start + size]
        if failure == 'short': body = body[:-1]
        if failure == 'corrupt': body = bytes([body[0] ^ 1]) + body[1:]
        return True, body
    def close_serial(self):
        event('close')
        self.bflb_serial_object = None
'''


class Workflow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='bdb test ')
        self.root = Path(self.tmp.name)
        self.tool = self.root / 'blflashcommand'
        self.runtime = self.root / 'runtime'
        self.bin_dir = self.root / 'bin'
        for path in (self.tool / 'venv/bin', self.tool / 'libs', self.root / 'utils',
                     self.runtime, self.bin_dir):
            path.mkdir(parents=True, exist_ok=True)
        (self.tool / 'venv/bin/python').symlink_to(sys.executable)
        (self.tool / 'libs/__init__.py').write_text('')
        (self.tool / 'libs/bflb_eflash_loader.py').write_text(FAKE_LOADER)
        (self.tool / 'libs/bflb_utils.py').write_text('''
import argparse
def eflash_loader_parser_init():
    p = argparse.ArgumentParser()
    for name in ('write', 'none', 'flash'): p.add_argument('--' + name, action='store_true')
    return p
''')
        (self.tool / 'BLFlashCommand.py').write_text('''
class MainClass:
    def get_value(self, args):
        return {'param': {}, 'config': args.config}
''')
        # Match the real adapter's dict config while keeping the mock tiny.
        mock = (self.tool / 'libs/bflb_eflash_loader.py')
        mock.write_text(mock.read_text().replace('self.values.config', "self.values['config']"))
        (self.bin_dir / 'tmux').write_text('''#!/bin/sh
if [ "$1" = "-V" ]; then echo "tmux test"; exit 0; fi
if [ "$1" = "has-session" ]; then test -f "$TEST_LOGGER"; exit $?; fi
exit 1
''')
        (self.bin_dir / 'tmux').chmod(0o755)
        for action in ('start', 'stop'):
            command = 'touch "$TEST_LOGGER"' if action == 'start' else 'rm -f "$TEST_LOGGER"'
            (self.root / f'utils/uart_logger_{action}.sh').write_text(
                f'#!/bin/sh\n{command}\necho logger-{action}\necho logger-{action} >> "$TEST_EVENTS"\n')
        self.events = self.root / 'events'
        self.logger = self.root / 'logger-running'
        self.memory = self.root / 'memory'
        self.memory.write_bytes(bytes(0x100000))
        self.port = self.root / 'ttyUSB-test'
        self.port.touch()
        self.source = self.root / 'firmware with spaces.bin'
        self.source.write_bytes(bytes(range(256)) * 40 + b'end')
        self.env = os.environ.copy()
        self.env.pop('BDB_HELD', None)
        self.env.update(PATH=f'{self.bin_dir}:{self.env["PATH"]}',
                        XDG_RUNTIME_DIR=str(self.runtime), TEST_EVENTS=str(self.events),
                        TEST_MEMORY=str(self.memory), TEST_LOGGER=str(self.logger))

    def tearDown(self):
        self.tmp.cleanup()

    def run_bdb(self, *args, code=0):
        result = subprocess.run([str(BIN), '--repo-root', str(self.root), '--timeout', '2',
                                 '--port-c0', str(self.root / 'c0'), '--port-c1', str(self.port),
                                 *args], env=self.env, text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return result.stdout

    def flash(self, *flags, code=0):
        return self.run_bdb('flash', 'file', str(self.source), '--addr', '0x2000', *flags, code=code)

    def history(self):
        return [json.loads(p.read_text()) for p in (self.runtime / 'bdb/txn-hist').glob('*.json')]

    def test_stops_logger_then_flashes_without_replug(self):
        self.logger.touch()
        output = self.flash()
        events = self.events.read_text().splitlines()
        self.assertLess(events.index('logger-stop'), events.index('open'))
        self.assertFalse(self.logger.exists())
        self.assertNotIn('replug', output.lower())

    def test_stops_logger_before_flash_mode_instruction_on_failure(self):
        self.logger.touch()
        self.env['TEST_FAIL'] = 'handshake'
        output = self.flash(code=1)
        self.assertLess(output.index('logger-stop'), output.index('NEED-USER: [buttons]'))
        self.assertFalse(self.logger.exists())

    def test_logger_stop_failure_never_prompts_for_flash_mode(self):
        self.logger.touch()
        (self.root / 'utils/uart_logger_stop.sh').write_text('exit 1\n')
        output = self.flash(code=1)
        self.assertNotIn('NEED-USER: [buttons]', output)
        self.assertTrue(self.logger.exists())
        self.assertFalse(self.events.exists())

    def test_repeated_flash_does_not_require_replug(self):
        self.flash()
        self.flash()
        self.assertEqual(self.events.read_text().splitlines().count('write'), 2)

    def test_write_verify_single_connection_and_logger_restart(self):
        output = self.flash()
        events = self.events.read_text().splitlines()
        self.assertEqual(events.count('open'), 1)
        self.assertEqual(events.count('close'), 1)
        self.assertEqual(sum(s.startswith('read ') for s in events), 3)
        self.assertNotIn('logger-start', events)
        self.assertIn('verification=on-chip-readback-sha256', output)
        self.assertNotIn('replug', output.lower())
        txn, = self.history()
        self.assertTrue(txn['regions'][0]['verified'])
        self.assertFalse((self.runtime / 'bdb/usb-replug-required').exists())
        self.run_bdb('log', 'start')
        self.assertTrue(self.logger.exists())

    def test_legacy_marker_and_flag_do_not_gate_operations(self):
        run = self.runtime / 'bdb'
        run.mkdir()
        (run / 'usb-replug-required').write_text('old version marker')
        self.flash('--usb-replugged')
        self.run_bdb('log', 'start')
        self.assertTrue(self.logger.exists())

    def test_external_port_holder_blocks_flashing(self):
        with self.port.open('rb'):
            output = self.flash(code=2)
        self.assertIn('port held', output)
        self.assertFalse(self.events.exists())

    def test_missing_port_blocks_session(self):
        self.port.unlink()
        self.flash(code=3)
        self.assertFalse(self.events.exists())

    def test_handshake_failure_does_not_trust_success_banner(self):
        self.env['TEST_FAIL'] = 'handshake'
        output = self.flash(code=1)
        self.assertNotIn('result=success', output)
        self.assertNotIn('write', self.events.read_text())
        self.assertFalse(self.logger.exists())

    def test_short_read_is_failure(self):
        self.env['TEST_FAIL'] = 'short'
        self.flash(code=1)
        self.assertIn('close', self.events.read_text())

    def test_sha_mismatch_is_failure(self):
        self.env['TEST_FAIL'] = 'corrupt'
        output = self.flash(code=1)
        self.assertIn('result=verify-mismatch', output)
        self.assertEqual(self.history()[0]['status'], 'failed')

    def test_timeout_leaves_recoverable_journal(self):
        self.env['TEST_FAIL'] = 'timeout'
        self.flash(code=1)
        txn = json.loads((self.runtime / 'bdb/txn.json').read_text())
        self.assertEqual(txn['status'], 'running')
        self.assertTrue(txn['regions'])

    def test_readback_and_verify_use_blflashcommand(self):
        self.flash()
        self.run_bdb('verify')
        output = self.root / 'dump.bin'
        self.run_bdb('readback', '--addr', '0x2000', '--len', str(self.source.stat().st_size),
                     '--out', str(output))
        self.assertEqual(output.read_bytes(), self.source.read_bytes())
        self.run_bdb('verify')
        self.assertEqual(self.events.read_text().splitlines().count('write'), 1)

    def test_recover_readback_never_writes(self):
        self.env['TEST_FAIL'] = 'short'
        self.run_bdb('readback', '--addr', '0x0', '--len', '64', code=1)
        del self.env['TEST_FAIL']
        self.run_bdb('recover')
        self.assertNotIn('write', self.events.read_text().splitlines())

    def test_low_load_recipe_and_preparation_failure(self):
        prep = self.root / 'utils/prepare_blflash_low_load.py'
        prep.write_text('raise RuntimeError("invalid flash table")\n')
        self.run_bdb('flash', 'low-load', code=1)
        self.assertFalse(self.events.exists())
        prep.write_text('''
from pathlib import Path
p = Path(__file__).resolve().parents[1] / 'blflashcommand/chips/bl808/img_create'
p.mkdir(parents=True, exist_ok=True)
for name in ('bootinfo_group0', 'bootinfo_group1', 'img_group0', 'img_group1'):
    (p / (name + '.bin')).write_bytes(name.encode() * 10)
''')
        self.run_bdb('flash', 'low-load')
        txn, = self.history()
        self.assertEqual([int(r['addr'], 0) for r in txn['regions']], [0, 0x1000, 0x2000, 0x52000])
        self.assertTrue(all(r['verified'] for r in txn['regions']))

    def test_zero_length_readback_rejected_without_uart(self):
        self.run_bdb('readback', '--addr', '0', '--len', '0', code=4)
        self.assertFalse(self.events.exists())

    def test_decimal_address_is_not_reinterpreted_as_hex(self):
        self.run_bdb('flash', 'file', str(self.source), '--addr', '8192')
        body = self.memory.read_bytes()
        self.assertEqual(body[8192:8192 + self.source.stat().st_size], self.source.read_bytes())

    def test_single_byte_readback(self):
        out = self.root / 'one.bin'
        self.run_bdb('readback', '--addr', '0', '--len', '1', '--out', str(out))
        self.assertEqual(out.read_bytes(), b'\0')

    def test_failed_flash_can_be_recovered_without_replug(self):
        self.env['TEST_FAIL'] = 'handshake'
        self.flash(code=1)
        del self.env['TEST_FAIL']
        self.run_bdb('recover')
        txn = json.loads((self.runtime / 'bdb/txn.json').read_text() or 'null')
        self.assertIsNone(txn)
        self.assertEqual(self.events.read_text().splitlines().count('write'), 1)


if __name__ == '__main__':
    unittest.main()
