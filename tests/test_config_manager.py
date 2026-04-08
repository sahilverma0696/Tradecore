import unittest
import tempfile
import json
import os
import time
from src.config_manager import ConfigManager

_VALID_CONFIG = {
    "symbols": ["BTCUSDT"],
    "market_close_time": "15:30",
    "trail": 0.03,
    "loss_stop_low": 0.96,
    "loss_stop_high": 1.06,
    "default_quantity": 75,
}


class TestConfigManager(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False
        )
        json.dump(_VALID_CONFIG, self._tmp)
        self._tmp.flush()
        self._tmp.close()

    def tearDown(self):
        try:
            os.unlink(self._tmp.name)
        except OSError:
            pass

    def test_initial_load(self):
        """Config is loaded on construction and accessible via get()."""
        cm = ConfigManager(config_path=self._tmp.name)
        cfg = cm.get()
        self.assertEqual(cfg['symbols'], ['BTCUSDT'])
        self.assertAlmostEqual(cfg['trail'], 0.03)
        cm.stop()

    def test_dot_notation_get(self):
        """get_value() resolves dot-notation paths."""
        cm = ConfigManager(config_path=self._tmp.name)
        self.assertEqual(cm.get_value('trail'), 0.03)
        self.assertIsNone(cm.get_value('nonexistent.key'))
        self.assertEqual(cm.get_value('nonexistent.key', default=99), 99)
        cm.stop()

    def test_get_returns_deep_copy(self):
        """Mutating the returned dict must not affect internal config."""
        cm = ConfigManager(config_path=self._tmp.name)
        cfg = cm.get()
        cfg['trail'] = 999
        self.assertEqual(cm.get_value('trail'), 0.03)
        cm.stop()

    def test_reload_and_watcher(self):
        """Watcher is called when the file changes on disk."""
        cm = ConfigManager(config_path=self._tmp.name, poll_interval=0.2)
        received = []
        cm.register_watcher(lambda cfg: received.append(cfg.get('trail')))

        updated = dict(_VALID_CONFIG)
        updated['trail'] = 0.05
        with open(self._tmp.name, 'w') as f:
            json.dump(updated, f)
        os.utime(self._tmp.name, None)  # force mtime change

        time.sleep(0.6)  # wait > one poll cycle
        cm.stop()

        self.assertTrue(len(received) > 0, "Watcher was never called")
        self.assertAlmostEqual(received[-1], 0.05)

    def test_validation_rejects_bad_config(self):
        """Missing required fields raise RuntimeError on construction."""
        bad = tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False
        )
        json.dump({"symbols": ["X"]}, bad)  # missing most required fields
        bad.flush()
        bad.close()
        try:
            with self.assertRaises(RuntimeError):
                ConfigManager(config_path=bad.name)
        finally:
            os.unlink(bad.name)

if __name__ == "__main__":
    unittest.main()
