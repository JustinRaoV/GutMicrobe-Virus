import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gmv.config import load_llm_config


class AiSettingsTests(unittest.TestCase):
    def setUp(self):
        self._env_backup = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env_backup)

    def test_precedence_cli_over_env_over_file(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "llm.yaml"
            cfg.write_text(
                "\n".join(
                    [
                        "base_url: https://file.example/v1",
                        "model: file-model",
                        "api_key_env: GMV_API_KEY",
                        "timeout_s: 10",
                        "verify_tls: true",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            os.environ["GMV_BASE_URL"] = "https://env.example/v1"
            os.environ["GMV_MODEL"] = "env-model"
            os.environ["GMV_API_KEY"] = "sk-env"

            st = load_llm_config(base_url="https://cli.example/v1", model="cli-model", llm_config=str(cfg))
            self.assertEqual(st.base_url, "https://cli.example/v1")
            self.assertEqual(st.model, "cli-model")
            self.assertEqual(st.api_key, "sk-env")
            self.assertEqual(st.timeout_s, 10)

    def test_missing_api_key_raises_when_not_mock(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "llm.yaml"
            cfg.write_text("base_url: https://x/v1\nmodel: y\napi_key_env: GMV_API_KEY\n", encoding="utf-8")
            os.environ.pop("GMV_API_KEY", None)
            os.environ.pop("GMV_CHAT_MOCK", None)
            with self.assertRaises(ValueError):
                load_llm_config(llm_config=str(cfg))

    def test_missing_api_key_allowed_in_mock_mode(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "llm.yaml"
            cfg.write_text("base_url: https://x/v1\nmodel: y\napi_key_env: GMV_API_KEY\n", encoding="utf-8")
            os.environ.pop("GMV_API_KEY", None)
            os.environ["GMV_CHAT_MOCK"] = "1"
            st = load_llm_config(llm_config=str(cfg))
            self.assertEqual(st.api_key, "")


if __name__ == "__main__":
    unittest.main()
