"""
Sprint 14 Tests — Typed Exceptions + Healthcheck + Docker Hygiene

Verifies:
  1-9.   All 9 bare except Exception: replaced with typed catches
  10.    _touch_heartbeat method added to engine
  11.    Docker healthcheck uses heartbeat file age check
  12.    Dockerfile.discord exists with discord.py
  13.    Dockerfile.jupyter exists with jupyterlab
  14.    docker-compose discord_bot uses Dockerfile.discord
  15.    .gitignore has data/ entry
  16.    .gitignore has models/ entry
  17.    .gitignore has notebooks/ entry
"""
import os
import unittest

ROOT = os.path.dirname(os.path.abspath(__file__))


def _read(rel):
    with open(os.path.join(ROOT, rel)) as f:
        return f.read()


class TestTypedExceptions(unittest.TestCase):
    """Tests 1-9: No bare except Exception: left in auto_trading_engine."""

    @classmethod
    def setUpClass(cls):
        cls.src = _read("src/engines/auto_trading_engine.py")
        # Count occurrences of bare 'except Exception:'
        cls.bare_count = cls.src.count("except Exception:")

    def test_01_no_bare_except_exception(self):
        """Zero bare except Exception: remain."""
        self.assertEqual(self.bare_count, 0,
            f"Found {self.bare_count} bare except Exception:")

    def test_02_has_import_error_catch(self):
        """Database check catches ImportError."""
        self.assertIn("except (ImportError, OSError, ConnectionError)", self.src)

    def test_03_has_runtime_error_catch_for_db(self):
        """Regime DB persist catches RuntimeError."""
        self.assertIn("except (OSError, ConnectionError, RuntimeError)", self.src)

    def test_04_has_value_error_catch_for_edge(self):
        """Edge calculator fallback catches ValueError."""
        self.assertIn("except (ValueError, KeyError, TypeError)", self.src)

    def test_05_has_connection_error_for_market(self):
        """Market data fallback catches ConnectionError."""
        self.assertIn(
            "except (ConnectionError, OSError, ValueError, KeyError)",
            self.src,
        )

    def test_06_broker_error_catch_for_equity(self):
        """_get_equity catches BrokerError + typed fallback."""
        # Find _get_equity method
        idx = self.src.find("async def _get_equity")
        section = self.src[idx:idx + 400]
        self.assertIn("except BrokerError", section)
        self.assertNotIn("except Exception:", section)

    def test_07_broker_error_catch_for_positions(self):
        """_count_positions catches BrokerError + typed fallback."""
        idx = self.src.find("async def _count_positions")
        section = self.src[idx:idx + 400]
        self.assertIn("except BrokerError", section)
        self.assertNotIn("except Exception:", section)

    def test_08_health_check_broker_probe(self):
        """health_check broker probe uses typed catch."""
        idx = self.src.find("async def health_check")
        section = self.src[idx:idx + 1500]
        self.assertIn("except (BrokerError, ConnectionError, OSError)", section)

    def test_09_debug_logging_on_typed_catches(self):
        """Typed catches use logger.debug for non-critical fallbacks."""
        self.assertIn('logger.debug("Edge calc fallback', self.src)
        self.assertIn('logger.debug("Market data fallback', self.src)
        self.assertIn('logger.debug("Equity fetch fallback', self.src)


class TestHeartbeat(unittest.TestCase):
    """Tests 10-11: Heartbeat mechanism."""

    @classmethod
    def setUpClass(cls):
        cls.engine_src = _read("src/engines/auto_trading_engine.py")
        cls.compose = _read("docker-compose.yml")

    def test_10_touch_heartbeat_method(self):
        """_touch_heartbeat method exists in engine."""
        self.assertIn("def _touch_heartbeat(self)", self.engine_src)
        self.assertIn("/tmp/engine_heartbeat", self.engine_src)

    def test_11_docker_healthcheck_uses_heartbeat(self):
        """auto_trader healthcheck checks heartbeat file age."""
        idx = self.compose.find("auto_trader:")
        section = self.compose[idx:idx + 2500]
        self.assertIn("engine_heartbeat", section)
        self.assertNotIn("import sys; sys.exit(0)", section)


class TestDockerfiles(unittest.TestCase):
    """Tests 12-14: Docker build files."""

    def test_12_dockerfile_discord_exists(self):
        path = os.path.join(ROOT, "docker", "Dockerfile.discord")
        self.assertTrue(os.path.exists(path))
        src = _read("docker/Dockerfile.discord")
        self.assertIn("discord.py", src)
        self.assertIn("run_discord_bot.py", src)

    def test_13_dockerfile_jupyter_exists(self):
        path = os.path.join(ROOT, "docker", "Dockerfile.jupyter")
        self.assertTrue(os.path.exists(path))
        src = _read("docker/Dockerfile.jupyter")
        self.assertIn("jupyterlab", src)
        self.assertIn("8888", src)

    def test_14_compose_discord_uses_dockerfile_discord(self):
        compose = _read("docker-compose.yml")
        idx = compose.find("discord_bot:")
        section = compose[idx:idx + 500]
        self.assertIn("Dockerfile.discord", section)
        self.assertNotIn("Dockerfile.telegram", section)


class TestGitignore(unittest.TestCase):
    """Tests 15-17: .gitignore entries."""

    @classmethod
    def setUpClass(cls):
        cls.gi = _read(".gitignore")

    def test_15_data_dir_ignored(self):
        self.assertIn("data/", self.gi)

    def test_16_models_dir_ignored(self):
        self.assertIn("models/", self.gi)

    def test_17_notebooks_dir_ignored(self):
        self.assertIn("notebooks/", self.gi)


if __name__ == "__main__":
    unittest.main()
