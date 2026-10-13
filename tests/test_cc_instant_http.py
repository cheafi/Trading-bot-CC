"""AST-loaded HTTP regressions: stdlib only, no app or server startup."""

import ast
import gzip
import http.server
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

LAUNCHER = Path(__file__).resolve().parents[1] / "scripts" / "cc_instant.py"
TOKEN = b"{{ api_key|tojson|safe }}"


def load_http():
    """Load definitions without bootstrap side effects or sockets."""
    names = {
        "Handler",
        "_mark_backend_ready",
        "_patch_dashboard_api_key",
        "_read_gzip_dashboard_file",
        "_dashboard_response_body",
        "_template_response_bodies",
    }
    source = LAUNCHER.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(LAUNCHER))
    node_types = (ast.FunctionDef, ast.ClassDef)
    definitions = [
        node
        for node in tree.body
        if isinstance(node, node_types) and node.name in names
    ]
    ns = {
        "http": http,
        "gzip": gzip,
        "json": json,
        "os": SimpleNamespace(environ={"API_SECRET_KEY": "test-key"}),
        "time": SimpleNamespace(time=lambda: 110.0),
        "_start": 100.0,
        "_backend_ready": False,
        "_backend_healthy": Mock(return_value=False),
        "_clear_backend_fatal": Mock(),
        "_degraded_response": Mock(return_value=None),
        "_maybe_stamp_degraded_body": lambda body: body,
        "_bootstrap_gzip_dashboard_cache": Mock(),
        "_read_file_bytes": lambda path, **kwargs: path.read_bytes(),
        "_MIN_TEMPLATE_BYTES": 1,
        "_MAX_GZIP_DASHBOARD_BYTES": 400_000,
        "_DASHBOARD_LOADER_HTML": b"<html>loader</html>",
        "_read_template_bytes": Mock(return_value=b""),
    }
    module = ast.Module(body=definitions, type_ignores=[])
    exec(compile(module, str(LAUNCHER), "exec"), ns)
    return ns


def handler_for(ns, path, *, headers=None):
    handler = object.__new__(ns["Handler"])
    handler.path = path
    handler.command = "GET"
    handler.headers = headers or {}
    handler.wfile = io.BytesIO()
    handler.send_response = Mock()
    handler.send_header = Mock()
    handler.end_headers = Mock()
    handler._proxy = Mock(return_value=True)
    return handler


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.ns = load_http()

    def test_readiness_is_local_with_one_fresh_probe_in_every_state(self):
        # A latched ready flag must not hide a subsequent backend failure.
        for latched in (False, True):
            for healthy in (False, True):
                for path in ("/readyz", "/readyz?probe=1"):
                    case = (latched, healthy, path)
                    with self.subTest(case=case):
                        self.ns["_backend_ready"] = latched
                        probe = self.ns["_backend_healthy"]
                        probe.reset_mock()
                        probe.return_value = healthy
                        handler = handler_for(self.ns, path)
                        handler.do_GET()
                        handler.send_response.assert_called_once_with(
                            200 if healthy else 503
                        )
                        payload = json.loads(handler.wfile.getvalue())
                        self.assertIs(payload["ready"], healthy)
                        self.assertTrue(payload["alive"])
                        self.assertEqual(
                            payload["mode"], "full" if healthy else "loading"
                        )
                        self.assertEqual(payload["uptime_seconds"], 10.0)
                        probe.assert_called_once_with()
                        handler._proxy.assert_not_called()
                        self.ns["_degraded_response"].assert_not_called()
                        self.assertIs(self.ns["_backend_ready"], latched)

    def test_readiness_tracks_warmup_recovery_and_failure(self):
        self.ns["_backend_healthy"].side_effect = [False, True, False]
        for expected in (503, 200, 503):
            handler = handler_for(self.ns, "/readyz")
            handler.do_GET()
            handler.send_response.assert_called_once_with(expected)
            handler._proxy.assert_not_called()
        self.assertEqual(self.ns["_backend_healthy"].call_count, 3)

    def test_healthz_preserves_backend_response(self):
        self.ns["_backend_healthy"].return_value = True
        handler = handler_for(self.ns, "/healthz")
        handler.do_GET()
        handler._proxy.assert_called_once_with()
        # Only the proxy owns the response.
        handler.send_response.assert_not_called()
        self.ns["_backend_healthy"].assert_called_once_with()

    def test_healthz_remains_alive_during_warmup_without_repeat_probes(self):
        handler = handler_for(self.ns, "/healthz")
        handler.do_GET()
        handler.send_response.assert_called_once_with(200)
        self.assertEqual(
            json.loads(handler.wfile.getvalue()),
            {
                "status": "ok",
                "alive": True,
                "ready": False,
                "mode": "loading",
                "uptime_seconds": 10.0,
            },
        )
        self.ns["_backend_healthy"].assert_called_once_with()
        handler._proxy.assert_not_called()

    def test_healthz_proxy_failure_still_reports_shell_alive(self):
        self.ns["_backend_ready"] = True
        handler = handler_for(self.ns, "/healthz")
        handler._proxy.return_value = False
        handler.do_GET()
        handler.send_response.assert_called_once_with(200)
        payload = json.loads(handler.wfile.getvalue())
        self.assertTrue(payload["alive"])
        self.assertFalse(payload["ready"])
        handler._proxy.assert_called_once_with()
        self.ns["_backend_healthy"].assert_not_called()


class DashboardEncodingTests(unittest.TestCase):
    def setUp(self):
        self.ns = load_http()
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.asset = Path(directory.name) / "dashboard.html.gz"
        self.ns["_GZIP_DASHBOARD_PATH"] = self.asset
        self.ns["_GZIP_DASHBOARD_CACHE"] = Path(directory.name) / "absent.gz"
        # Match the checked-in asset's JSON script, not the old assignment.
        script = b'<script id="cc-api-key" type="application/json">'
        self.plain = script + TOKEN + b"</script>"
        self.original_gzip = gzip.compress(self.plain)
        self.asset.write_bytes(self.original_gzip)

    def expected(self):
        return self.plain.replace(TOKEN, b'"test-key"')

    def test_dashboard_encoding_parity(self):
        for accept in ("", "gzip"):
            with self.subTest(accept=accept):
                request_headers = {"Accept-Encoding": accept}
                handler = handler_for(self.ns, "/", headers=request_headers)
                handler.do_GET()
                body = handler.wfile.getvalue()
                calls = handler.send_header.call_args_list
                headers = dict(call.args for call in calls)
                self.assertEqual(int(headers["Content-Length"]), len(body))
                if accept:
                    self.assertEqual(headers["Content-Encoding"], "gzip")
                    body = gzip.decompress(body)
                else:
                    self.assertNotIn("Content-Encoding", headers)
                self.assertEqual(body, self.expected())
                handler.send_response.assert_called_once_with(200)
                handler._proxy.assert_not_called()
        # Credentials are rendered in memory, never persisted to the bundle.
        self.assertEqual(self.asset.read_bytes(), self.original_gzip)

    def test_loader_routes_return_rendered_gzip_file(self):
        paths = (
            "/cc-asset/dashboard.html.gz",
            "/static/cc-dashboard.html.gz?v=1",
        )
        for path in paths:
            with self.subTest(path=path):
                handler = handler_for(self.ns, path)
                handler.do_GET()
                body = handler.wfile.getvalue()
                calls = handler.send_header.call_args_list
                headers = dict(call.args for call in calls)
                self.assertEqual(gzip.decompress(body), self.expected())
                self.assertEqual(headers["Content-Type"], "application/gzip")
                self.assertEqual(int(headers["Content-Length"]), len(body))
                self.assertEqual(headers["Cache-Control"], "no-store")
                self.assertNotIn("Content-Encoding", headers)

    def test_template_response_pair_has_encoding_parity(self):
        plain, compressed = self.ns["_template_response_bodies"]()
        self.assertEqual(plain, self.expected())
        self.assertEqual(gzip.decompress(compressed), plain)

    def test_token_like_key_content_is_not_rendered_twice(self):
        self.ns["os"].environ["API_SECRET_KEY"] = TOKEN.decode()
        expected = self.plain.replace(TOKEN, b'"' + TOKEN + b'"')
        respond = self.ns["_dashboard_response_body"]
        self.assertEqual(respond(use_gzip=False), expected)
        self.assertEqual(gzip.decompress(respond(use_gzip=True)), expected)
        plain, compressed = self.ns["_template_response_bodies"]()
        self.assertEqual(plain, expected)
        self.assertEqual(gzip.decompress(compressed), expected)

    def test_old_assignment_and_json_script_both_render_html_safe_json(self):
        key = "quote\"\\line\n</script>&'"
        self.ns["os"].environ["API_SECRET_KEY"] = key
        patch = self.ns["_patch_dashboard_api_key"]
        literal = patch(TOKEN)
        self.assertEqual(json.loads(literal), key)
        self.assertNotIn(b"<", literal)
        self.assertNotIn(b">", literal)
        self.assertNotIn(b"&", literal)
        self.assertNotIn(b"'", literal)
        self.assertEqual(
            patch(b"window._apiKey = " + TOKEN + b";"),
            b"window._apiKey = " + literal + b";",
        )
        self.assertEqual(patch(self.plain), self.plain.replace(TOKEN, literal))

    def test_unchanged_asset_retains_original_compressed_bytes(self):
        compressed = gzip.compress(b"<html>already rendered</html>", mtime=123)
        self.asset.write_bytes(compressed)
        self.assertEqual(self.ns["_read_gzip_dashboard_file"](), compressed)

    def test_missing_or_invalid_gzip_uses_loader_in_both_encodings(self):
        for invalid in (None, b"not gzip"):
            with self.subTest(invalid=invalid):
                if invalid is None:
                    self.asset.unlink()
                else:
                    self.asset.write_bytes(invalid)
                respond = self.ns["_dashboard_response_body"]
                plain = respond(use_gzip=False)
                self.assertEqual(plain, self.ns["_DASHBOARD_LOADER_HTML"])
                compressed = respond(use_gzip=True)
                self.assertEqual(gzip.decompress(compressed), plain)


if __name__ == "__main__":
    unittest.main()
