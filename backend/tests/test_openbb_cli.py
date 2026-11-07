import io
import unittest
from unittest.mock import patch
import os

from app.openbb_cli import run_openbb_cli


class FakeProcess:
    def __init__(self, output=b"", returncode=0):
        self.stdout = io.BytesIO(output)
        self.returncode = returncode
        self.terminated = False

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = -15

    def kill(self):
        self.returncode = -9


class OpenBBCLITests(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    @patch("app.openbb_cli.shutil.which", return_value="/usr/bin/openbb")
    def test_disabled_by_default_gate_does_not_spawn_cli(self, _which):
        with patch("app.openbb_cli.subprocess.Popen") as popen:
            result = run_openbb_cli("help")
        self.assertTrue(result.available)
        self.assertIn("disabled", result.error)
        popen.assert_not_called()

    @patch.dict(os.environ, {"OPENBB_CLI_ENABLED": "true"})
    @patch("app.openbb_cli.shutil.which", return_value=None)
    def test_reports_missing_cli(self, _which):
        result = run_openbb_cli("help")
        self.assertFalse(result.available)
        self.assertIn("not installed", result.error)

    @patch.dict(os.environ, {"OPENBB_CLI_ENABLED": "true"})
    @patch("app.openbb_cli.subprocess.Popen")
    @patch("app.openbb_cli.shutil.which", return_value="/usr/bin/openbb")
    def test_help_uses_fixed_argument_and_no_shell(self, _which, popen):
        popen.return_value = FakeProcess(b"OpenBB usage")
        result = run_openbb_cli("help")
        self.assertTrue(result.available)
        self.assertEqual(result.output, "OpenBB usage")
        args, kwargs = popen.call_args
        self.assertEqual(args[0], ["/usr/bin/openbb", "--help"])
        self.assertFalse(kwargs["shell"])
        self.assertEqual(kwargs["stdin"], __import__("subprocess").DEVNULL)

    @patch.dict(os.environ, {"OPENBB_CLI_ENABLED": "true"})
    @patch("app.openbb_cli.Path.is_file", return_value=True)
    @patch("app.openbb_cli.subprocess.run")
    @patch("app.openbb_cli.shutil.which", return_value="/opt/openbb-venv/bin/openbb")
    def test_version_uses_cli_environment_python(self, _which, run, _is_file):
        run.return_value = __import__("subprocess").CompletedProcess(
            args=[], returncode=0, stdout="5.0.1\\n", stderr=""
        )
        result = run_openbb_cli("version")
        self.assertTrue(result.available)
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, "OpenBB CLI version 5.0.1")
        args, kwargs = run.call_args
        self.assertEqual(args[0][0], "/opt/openbb-venv/bin/python")
        self.assertIn("openbb-cli", args[0][2])
        self.assertFalse(kwargs["shell"])

    @patch.dict(os.environ, {"OPENBB_CLI_ENABLED": "true"})
    @patch("app.openbb_cli.subprocess.Popen")
    @patch("app.openbb_cli.shutil.which", return_value="/usr/bin/openbb")
    def test_caps_streamed_output_and_reports_nonzero(self, _which, popen):
        popen.return_value = FakeProcess(b"x" * 13000, returncode=2)
        result = run_openbb_cli("help")
        self.assertEqual(len(result.output), 12000)
        self.assertTrue(result.output.endswith("… [output truncated]"))
        self.assertIsNotNone(result.error)

    @patch.dict(os.environ, {"OPENBB_CLI_ENABLED": " TrUe "})
    def test_enable_flag_is_case_insensitive_and_trimmed(self):
        from app.openbb_cli import openbb_cli_enabled
        self.assertTrue(openbb_cli_enabled())

    @patch.dict(os.environ, {"OPENBB_CLI_ENABLED": "true"})
    @patch("app.openbb_cli.Path.is_file", return_value=True)
    @patch("app.openbb_cli.subprocess.run")
    @patch("app.openbb_cli.shutil.which", return_value="/opt/openbb-venv/bin/openbb")
    def test_version_handles_missing_distribution_metadata(self, _which, run, _is_file):
        run.return_value = __import__("subprocess").CompletedProcess(
            args=[], returncode=1, stdout="PackageNotFoundError\\n", stderr=""
        )
        result = run_openbb_cli("version")
        self.assertTrue(result.available)
        self.assertEqual(result.exit_code, 1)
        self.assertIn("metadata was not found", result.error)

    @patch.dict(os.environ, {"OPENBB_CLI_ENABLED": "true"})
    @patch("app.openbb_cli.subprocess.Popen")
    @patch("app.openbb_cli.shutil.which", return_value="/usr/bin/openbb")
    def test_busy_semaphore_prevents_extra_subprocess(self, _which, popen):
        from app.openbb_cli import _HELP_RUN_SEMAPHORE
        self.assertTrue(_HELP_RUN_SEMAPHORE.acquire(blocking=False))
        try:
            result = run_openbb_cli("help")
        finally:
            _HELP_RUN_SEMAPHORE.release()
        self.assertTrue(result.available)
        self.assertIn("busy", result.error)
        popen.assert_not_called()

    def test_rejects_unsupported_action(self):
        with self.assertRaises(ValueError):
            run_openbb_cli("arbitrary")


if __name__ == "__main__":
    unittest.main()
