import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from lens.feed.access import configure_token


class AccessTest(unittest.TestCase):
    def test_verified_token_is_private_and_replaces_atomically(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {}):
            path = Path(folder) / "provider/auth_token"
            path.parent.mkdir()
            path.write_text("old-token")
            token = "test-access-token-for-unit-tests-only"
            with patch("lens.feed.access._verify", return_value=True) as verify:
                configure_token(token, path)
            verify.assert_called_once_with(token)
            self.assertEqual(path.read_text(), token)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(os.environ["TABPFN_TOKEN"], token)
            self.assertEqual(list(path.parent.iterdir()), [path])

    def test_invalid_and_unavailable_tokens_never_replace_existing_access(self):
        with (
            tempfile.TemporaryDirectory() as folder,
            patch.dict(os.environ, {"TABPFN_TOKEN": "existing"}),
        ):
            path = Path(folder) / "auth_token"
            path.write_text("existing")
            for valid in [False, None]:
                with (
                    patch("lens.feed.access._verify", return_value=valid),
                    self.assertRaises(ValueError),
                ):
                    configure_token("test-access-token-for-unit-tests-only", path)
                self.assertEqual(path.read_text(), "existing")
                self.assertEqual(os.environ["TABPFN_TOKEN"], "existing")

    def test_malformed_tokens_are_rejected_before_verification(self):
        with tempfile.TemporaryDirectory() as folder, patch("lens.feed.access._verify") as verify:
            for token in [None, "short", "test-token-with-injected\nheader-content"]:
                with self.assertRaises(ValueError):
                    configure_token(token, Path(folder) / "auth_token")
            verify.assert_not_called()
