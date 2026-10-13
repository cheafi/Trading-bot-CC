"""Launcher regressions: stdlib mocks, no app imports or network."""

import ast
import os
import subprocess
import sys
import tempfile
import textwrap
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call, sentinel

LAUNCHER = Path(__file__).resolve().parents[1] / "scripts" / "cc_instant.py"


def load_lifecycle():
    """Load functions without re-exec, chdir, or dashboard cache I/O."""
    tree = ast.parse(
        LAUNCHER.read_text(encoding="utf-8"),
        filename=str(LAUNCHER),
    )
    names = {"_stop_backend", "_supervise_backend", "main"}
    functions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    ns = {
        "subprocess": subprocess,
        "threading": threading,
        "_backend_ready": True,
        "_spawn_backend": Mock(),
        "print": Mock(),
    }
    module = ast.Module(body=functions, type_ignores=[])
    exec(compile(module, str(LAUNCHER), "exec"), ns)
    return ns


def process(*, exited=False):
    # Deliberately exclude multiprocessing's is_alive/join methods.
    proc = Mock(spec_set=["pid", "poll", "terminate", "wait", "kill"])
    proc.pid = 123
    proc.poll.return_value = 1 if exited else None
    proc.wait.return_value = 0
    return proc


class LauncherImportPathTests(unittest.TestCase):
    def test_bootstrap_resolves_src_from_another_cwd_without_pythonpath(self):
        # Run only the real bootstrap, never dashboard I/O or servers.
        probe = textwrap.dedent("""
            import ast
            import importlib.util
            import os
            import sys
            from pathlib import Path

            launcher = Path(sys.argv[1])
            root = launcher.parent.parent
            assert Path.cwd() != root
            assert "PYTHONPATH" not in os.environ
            # Match direct script execution rather than `-c`'s cwd import path.
            sys.path.insert(0, str(launcher.parent))
            assert str(root) not in sys.path
            assert "" not in sys.path
            assert importlib.util.find_spec("src") is None

            tree = ast.parse(launcher.read_text(encoding="utf-8"))
            prefix = []
            for node in tree.body:
                if isinstance(node, ast.Assign) and any(
                    isinstance(target, ast.Name) and target.id == "_PORT_RAW"
                    for target in node.targets
                ):
                    break
                prefix.append(node)
            else:
                raise AssertionError("launcher bootstrap boundary not found")
            ns = {"__file__": str(launcher), "__name__": "bootstrap_probe"}
            module = ast.Module(body=prefix, type_ignores=[])
            exec(compile(module, str(launcher), "exec"), ns)
            assert Path.cwd() == root
            assert sys.path[0] == str(root)
            spec = importlib.util.find_spec("src")
            assert spec is not None
            assert str(root / "src") in spec.submodule_search_locations
            assert "src.api.main" not in sys.modules
            print("bootstrap resolves repository src")
            """)
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        env["CC_INSTANT_VENV_REEXEC"] = "1"
        with tempfile.TemporaryDirectory() as cwd:
            result = subprocess.run(
                [sys.executable, "-I", "-S", "-c", probe, str(LAUNCHER)],
                cwd=cwd,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("bootstrap resolves repository src", result.stdout)


class BackendShutdownTests(unittest.TestCase):
    def setUp(self):
        self.ns = load_lifecycle()

    def test_terminate_and_reap_using_popen_methods(self):
        proc = process()
        self.ns["_stop_backend"](proc)
        self.assertEqual(
            proc.mock_calls,
            [
                call.poll(),
                call.terminate(),
                call.wait(timeout=5.0),
            ],
        )

    def test_exited_child_needs_no_signal(self):
        proc = process(exited=True)
        self.ns["_stop_backend"](proc)
        self.assertEqual(proc.mock_calls, [call.poll()])

    def test_uncooperative_child_is_killed_and_reaped(self):
        proc = process()
        proc.wait.side_effect = [subprocess.TimeoutExpired("child", 5), 0]
        self.ns["_stop_backend"](proc)
        self.assertEqual(
            proc.mock_calls,
            [
                call.poll(),
                call.terminate(),
                call.wait(timeout=5.0),
                call.kill(),
                call.wait(timeout=1.0),
            ],
        )

    def test_post_kill_wait_is_bounded_and_reported(self):
        proc = process()
        proc.wait.side_effect = subprocess.TimeoutExpired("child", 1)
        self.ns["_stop_backend"](proc)
        self.assertEqual(
            proc.wait.call_args_list,
            [
                call(timeout=5.0),
                call(timeout=1.0),
            ],
        )
        self.assertIn(
            "did not exit after kill",
            self.ns["print"].call_args.args[0],
        )

    def test_stopped_supervisor_never_spawns(self):
        stop = threading.Event()
        stop.set()
        self.ns["_supervise_backend"](stop)
        self.ns["_spawn_backend"].assert_not_called()

    def test_spawn_oserrors_back_off_and_retry_until_success(self):
        stop = threading.Event()
        proc = process()
        spawn = self.ns["_spawn_backend"]
        spawn.side_effect = [OSError("spawn unavailable"), OSError("still busy"), proc]

        def wait(timeout):
            self.assertFalse(self.ns["_backend_ready"])
            if timeout == 0.2:
                stop.set()
            return stop.is_set()

        stop.wait = Mock(side_effect=wait)
        self.ns["_supervise_backend"](stop)
        self.assertEqual(spawn.call_count, 3)
        self.assertEqual(stop.wait.call_args_list, [call(3), call(3), call(0.2)])
        messages = [entry.args[0] for entry in self.ns["print"].call_args_list]
        self.assertEqual(len(messages), 2)
        reasons = ("spawn unavailable", "still busy")
        for message, reason in zip(messages, reasons):
            self.assertIn("child spawn failed", message)
            self.assertIn(reason, message)
            self.assertIn("retrying backend in 3s", message)
        proc.terminate.assert_called_once_with()
        proc.wait.assert_called_once_with(timeout=5.0)

    def test_shutdown_interrupts_spawn_failure_backoff_without_respawn(self):
        stop = threading.Event()
        self.ns["_spawn_backend"].side_effect = OSError("spawn unavailable")
        self.ns["_stop_backend"] = Mock()

        def wait(timeout):
            self.assertEqual(timeout, 3)
            stop.set()
            return stop.is_set()

        stop.wait = Mock(side_effect=wait)
        self.ns["_supervise_backend"](stop)
        stop.wait.assert_called_once_with(3)
        self.ns["_spawn_backend"].assert_called_once_with()
        self.ns["_stop_backend"].assert_not_called()
        self.assertFalse(self.ns["_backend_ready"])

    def test_failed_restart_retries_and_cleans_latest_child(self):
        stop = threading.Event()
        old = process(exited=True)
        latest = process()
        spawn = self.ns["_spawn_backend"]
        spawn.side_effect = [old, OSError("restart unavailable"), latest]

        def wait(timeout):
            if spawn.call_count == 3:
                stop.set()
            return stop.is_set()

        stop.wait = Mock(side_effect=wait)
        self.ns["_supervise_backend"](stop)
        self.assertEqual(spawn.call_count, 3)
        self.assertEqual(
            stop.wait.call_args_list, [call(0.2), call(3), call(3), call(0.2)]
        )
        old.terminate.assert_not_called()
        latest.terminate.assert_called_once_with()
        latest.wait.assert_called_once_with(timeout=5.0)
        self.assertFalse(self.ns["_backend_ready"])

    def test_unexpected_spawn_error_is_not_silently_retried(self):
        stop = threading.Event()
        stop.wait = Mock()
        self.ns["_spawn_backend"].side_effect = ValueError("invalid spawn arguments")
        with self.assertRaisesRegex(ValueError, "invalid spawn arguments"):
            self.ns["_supervise_backend"](stop)
        self.ns["_spawn_backend"].assert_called_once_with()
        stop.wait.assert_not_called()
        self.assertFalse(self.ns["_backend_ready"])

    def test_shutdown_during_restart_delay_cancels_respawn(self):
        stop = threading.Event()
        proc = process(exited=True)
        self.ns["_spawn_backend"].return_value = proc

        def wait(timeout):
            if timeout == 3:
                stop.set()
            return stop.is_set()

        stop.wait = Mock(side_effect=wait)
        self.ns["_supervise_backend"](stop)
        self.ns["_spawn_backend"].assert_called_once_with()
        proc.terminate.assert_not_called()
        self.assertFalse(self.ns["_backend_ready"])

    def test_shutdown_terminates_latest_child_after_multiple_restarts(self):
        stop = threading.Event()
        children = [process(exited=True), process(exited=True), process()]
        spawn = self.ns["_spawn_backend"]
        spawn.side_effect = children

        def wait(timeout):
            if spawn.call_count == 3:
                stop.set()
            return stop.is_set()

        stop.wait = Mock(side_effect=wait)
        self.ns["_supervise_backend"](stop)
        self.assertEqual(spawn.call_count, 3)
        for old in children[:2]:
            old.terminate.assert_not_called()
        children[-1].terminate.assert_called_once_with()
        children[-1].wait.assert_called_once_with(timeout=5.0)

    def test_stop_while_spawn_is_in_flight_still_cleans_up_child(self):
        stop = threading.Event()
        spawning = threading.Event()
        release = threading.Event()
        proc = process()
        failures = []

        def spawn():
            spawning.set()
            if not release.wait(2):
                raise AssertionError("test did not release spawn")
            return proc

        def supervise():
            try:
                self.ns["_supervise_backend"](stop)
            except BaseException as exc:
                failures.append(exc)

        self.ns["_spawn_backend"].side_effect = spawn
        worker = threading.Thread(target=supervise, daemon=True)
        worker.start()
        try:
            self.assertTrue(spawning.wait(2))
        finally:
            stop.set()
            release.set()
            worker.join(timeout=2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(failures, [])
        proc.terminate.assert_called_once_with()
        proc.wait.assert_called_once_with(timeout=5.0)
        self.ns["_spawn_backend"].assert_called_once_with()


class MainShutdownTests(unittest.TestCase):
    def setUp(self):
        self.ns = load_lifecycle()
        self.stop = threading.Event()
        self.server = Mock()
        self.server.serve_forever.side_effect = KeyboardInterrupt
        # Fail immediately instead of allowing an unsafe shutdown call to hang.
        self.server.shutdown.side_effect = AssertionError(
            "same-thread shutdown must not be called"
        )
        self.supervisor = Mock(ident=123)
        self.supervisor.is_alive.return_value = False
        self.thread_factory = Mock(return_value=self.supervisor)
        self.signals = SimpleNamespace(
            SIGTERM=15,
            signal=Mock(return_value=sentinel.previous_handler),
        )
        self.ns.update(
            {
                "threading": SimpleNamespace(
                    Event=Mock(return_value=self.stop),
                    Thread=self.thread_factory,
                ),
                "signal": self.signals,
                "os": SimpleNamespace(environ={}),
                "time": SimpleNamespace(sleep=Mock()),
                "atexit": SimpleNamespace(register=Mock()),
                "_log_main_exit": Mock(),
                "_acquire_single_instance": Mock(return_value=True),
                "_kill_port": Mock(),
                "ReusableTCPServer": Mock(return_value=self.server),
                "Handler": sentinel.handler,
                "PORT": 8000,
                "BACKEND_PORT": 8001,
            }
        )

        def joined(timeout):
            self.assertTrue(self.stop.is_set())
            self.assertEqual(timeout, 8.0)

        self.supervisor.join.side_effect = joined

    def assert_cleaned_up(self, *, backend=True):
        self.assertTrue(self.stop.is_set())
        self.server.shutdown.assert_not_called()
        self.server.server_close.assert_called_once_with()
        if backend:
            self.supervisor.join.assert_called_once_with(timeout=8.0)
        else:
            self.thread_factory.assert_not_called()
        self.signals.signal.assert_called_with(
            self.signals.SIGTERM,
            sentinel.previous_handler,
        )

    def send_sigterm(self, *args):
        handler = self.signals.signal.call_args_list[0].args[1]
        handler(self.signals.SIGTERM, None)

    def test_keyboard_interrupt_closes_server_and_stops_supervisor(self):
        self.ns["main"]()
        self.assert_cleaned_up()
        self.thread_factory.assert_called_once_with(
            target=self.ns["_supervise_backend"],
            args=(self.stop,),
            name="cc-backend-supervisor",
            daemon=True,
        )
        self.supervisor.start.assert_called_once_with()

    def test_no_backend_mode_still_closes_server(self):
        self.ns["os"].environ["CC_INSTANT_NO_BACKEND"] = "1"
        self.ns["main"]()
        self.assert_cleaned_up(backend=False)
        self.ns["_spawn_backend"].assert_not_called()

    def test_sigterm_uses_same_cleanup_path(self):
        self.server.serve_forever.side_effect = self.send_sigterm
        self.ns["main"]()
        self.assert_cleaned_up()

    def test_sigterm_during_startup_restores_handler(self):
        self.ns["time"].sleep.side_effect = self.send_sigterm
        self.ns["main"]()
        self.assertTrue(self.stop.is_set())
        self.ns["ReusableTCPServer"].assert_not_called()
        self.thread_factory.assert_not_called()
        self.signals.signal.assert_called_with(
            self.signals.SIGTERM,
            sentinel.previous_handler,
        )

    def test_bind_failure_does_not_start_backend(self):
        self.ns["ReusableTCPServer"].side_effect = OSError("bind failed")
        with self.assertRaisesRegex(OSError, "bind failed"):
            self.ns["main"]()
        self.assertTrue(self.stop.is_set())
        self.thread_factory.assert_not_called()
        self.signals.signal.assert_called_with(
            self.signals.SIGTERM,
            sentinel.previous_handler,
        )

    def test_close_failure_does_not_skip_supervisor_cleanup(self):
        self.server.server_close.side_effect = OSError("close failed")
        with self.assertRaisesRegex(OSError, "close failed"):
            self.ns["main"]()
        self.assert_cleaned_up()

    def test_repeated_sigterm_during_cleanup_does_not_interrupt_it(self):
        self.server.server_close.side_effect = self.send_sigterm
        self.ns["main"]()
        self.assert_cleaned_up()


if __name__ == "__main__":
    unittest.main()
