import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from spt_piles import config


class TestConfig(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self._patcher = mock.patch.object(
            config, "get_config_dir", return_value=Path(self._tmpdir.name) / "spt_estacas"
        )
        self._patcher.start()
        self.addCleanup(self._patcher.stop)

    def test_load_api_key_returns_none_when_not_set(self):
        self.assertIsNone(config.load_api_key())

    def test_save_and_load_roundtrip(self):
        config.save_api_key("sk-ant-test-123")
        self.assertEqual(config.load_api_key(), "sk-ant-test-123")

    def test_save_strips_whitespace(self):
        config.save_api_key("  sk-ant-test-456  \n")
        self.assertEqual(config.load_api_key(), "sk-ant-test-456")

    def test_save_empty_raises(self):
        with self.assertRaises(ValueError):
            config.save_api_key("   ")

    def test_clear_removes_key(self):
        config.save_api_key("sk-ant-test-789")
        config.clear_api_key()
        self.assertIsNone(config.load_api_key())

    def test_clear_when_nothing_saved_does_not_raise(self):
        config.clear_api_key()
        self.assertIsNone(config.load_api_key())

    def test_config_file_created_on_save(self):
        config.save_api_key("sk-ant-test-abc")
        self.assertTrue(config.get_config_path().exists())

    def test_resolve_api_key_prefers_env_var(self):
        config.save_api_key("sk-ant-from-file")
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-from-env"}):
            self.assertEqual(config.resolve_api_key(), "sk-ant-from-env")

    def test_resolve_api_key_falls_back_to_file(self):
        config.save_api_key("sk-ant-from-file")
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(config.resolve_api_key(), "sk-ant-from-file")

    def test_resolve_api_key_none_when_nothing_configured(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(config.resolve_api_key())


if __name__ == "__main__":
    unittest.main()
