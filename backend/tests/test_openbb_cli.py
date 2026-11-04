import unittest
from unittest.mock import patch, Mock
import os

from app.openbb_cli import run_openbb_cli


class OpenBBCLITests(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    @patch("app.openbb_cli.shutil.which", return_value="/usr/bin/openbb")
    def test_disabled_by_default_gate_does_not_spawn_cli(self, _which):
        with patch("app.openbb_cli.subprocess.run") as run:
            result = run_openbb_cli("help")
        self.assertFalse(result.available)
        self.assertIn("disabled", result.error)
        run.assert_not_called()

    @patch.dict(os.environ, {"OPENBB_CLI_ENABLED": "true"})
    @patch("app.openbb_cli.shutil.which", return_value=None)
    def test_reports_missing_cli(self, _which):
        result = run_openbb_cli("help")
        self.assertFalse(result.available)
        self.assertIn("not installed", result.error)

    @patch.dict(os.environ, {"OPENBB_CLI_ENABLED": "true"})
    @patch("app.openbb_cli.subprocess.run")
    @patch("app.openbb_cli.shutil.which", return_value="/usr/bin/openbb")
    def test_help_uses_fixed_argument_and_no_shell(self, _which, run):
        run.return_value = Mock(stdout="OpenBB usage", stderr="", returncode=0)
        result = run_openbb_cli("help")
        self.assertTrue(result.available)
        self.assertEqual(result.output, "OpenBB usage")
        args, kwargs = run.call_args
        self.assertEqual(args[0], ["/usr/bin/openbb", "--help"])
        self.assertFalse(kwargs["shell"])
        self.assertEqual(kwargs["timeout"], 8)

    @patch.dict(os.environ, {"OPENBB_CLI_ENABLED": "true"})
    @patch("app.openbb_cli.importlib.metadata.version", return_value="5.0.1")
    @patch("app.openbb_cli.shutil.which", return_value="/usr/bin/openbb")
    def test_version_uses_package_metadata_not_unsupported_flag(self, _which, version):
        result = run_openbb_cli("version")
        self.assertTrue(result.available)
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, "OpenBB CLI version 5.0.1")
        version.assert_called_once_with("openbb-cli")

    @patch.dict(os.environ, {"OPENBB_CLI_ENABLED": "true"})
    @patch("app.openbb_cli.subprocess.run")
    @patch("app.openbb_cli.shutil.which", return_value="/usr/bin/openbb")
    def test_caps_output_and_reports_nonzero(self, _which, run):
        run.return_value = Mock(stdout="x" * 13000, stderr="", returncode=2)
        result = run_openbb_cli("help")
        self.assertEqual(len(result.output), 12000)
        self.assertIsNotNone(result.error)

    @patch.dict(os.environ, {"OPENBB_CLI_ENABLED": "true"})
    @patch("app.openbb_cli.subprocess.run", side_effect=__import__("subprocess").TimeoutExpired("openbb", 8))
    @patch("app.openbb_cli.shutil.which", return_value="/usr/bin/openbb")
    def test_timeout_is_reported(self, _which, _run):
        result = run_openbb_cli("help")
        self.assertTrue(result.available)
        self.assertIn("timed out", result.error)


if __name__ == "__main__":
    unittest.main()
