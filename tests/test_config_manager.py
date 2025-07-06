import unittest
import tempfile
import json
import os
from src.config_manager import ConfigManager

class TestConfigManager(unittest.TestCase):
    def test_reload_and_watcher(self):
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as tf:
            tf.write(json.dumps({"foo": "bar"}))
            tf.flush()
            cm = ConfigManager(config_path=tf.name)
            called = []
            def watcher(cfg):
                called.append(cfg)
            cm.register_watcher(watcher)
            # Simulate config change
            tf.seek(0)
            tf.write(json.dumps({"foo": "baz"}))
            tf.flush()
            os.utime(tf.name, None)
            import time; time.sleep(1)
            self.assertTrue(any("foo" in c for c in called))
        os.unlink(tf.name)

if __name__ == "__main__":
    unittest.main()
