"""
Sprint 13 Tests — Docker + Infrastructure Hardening

Verifies:
  1.    src/engines/__main__.py exists
  2.    __main__.py imports from main
  3.    config/default.yaml exists
  4-6.  default.yaml has engine, risk, strategies sections
  7.    docker-compose auto_trader uses correct CMD
  8.    docker-compose auto_trader has healthcheck
  9.    docker-compose auto_trader has LOG_FORMAT=json
  10.   docker-compose auto_trader has DRY_RUN env var
  11.   docker-compose auto_trader has CYCLE_INTERVAL env var
  12.   ARCHITECTURE.md updated with Sprint 9-12 history
  13.   ARCHITECTURE.md has pipeline diagram
  14.   ARCHITECTURE.md has engines/main.py in tree
  15.   ARCHITECTURE.md has trade_repo.py in tree
  16.   ARCHITECTURE.md has logging_config.py in tree
  17.   config/default.yaml parseable as YAML
"""
import os
import unittest

ROOT = os.path.dirname(os.path.abspath(__file__))


def _read(rel):
    with open(os.path.join(ROOT, rel)) as f:
        return f.read()


class TestEnginesMainModule(unittest.TestCase):
    """Tests 1-2: __main__.py for `python -m src.engines`."""

    def test_01_main_module_exists(self):
        path = os.path.join(
            ROOT, "src", "engines", "__main__.py"
        )
        self.assertTrue(os.path.exists(path))

    def test_02_main_imports_main(self):
        src = _read("src/engines/__main__.py")
        self.assertIn("from src.engines.main import main", src)


class TestConfigDefault(unittest.TestCase):
    """Tests 3-6, 17: config/default.yaml."""

    @classmethod
    def setUpClass(cls):
        cls.yaml_path = os.path.join(
            ROOT, "config", "default.yaml"
        )
        with open(cls.yaml_path) as f:
            cls.yaml_src = f.read()

    def test_03_config_file_exists(self):
        self.assertTrue(os.path.exists(self.yaml_path))

    def test_04_has_engine_section(self):
        self.assertIn("engine:", self.yaml_src)
        self.assertIn("cycle_interval_seconds", self.yaml_src)

    def test_05_has_risk_section(self):
        self.assertIn("risk:", self.yaml_src)
        self.assertIn("risk_per_trade", self.yaml_src)
        self.assertIn("max_drawdown_pct", self.yaml_src)

    def test_06_has_strategies_section(self):
        self.assertIn("strategies:", self.yaml_src)
        self.assertIn("momentum_breakout", self.yaml_src)

    def test_17_yaml_parseable(self):
        """YAML can be parsed without errors."""
        try:
            import yaml
            data = yaml.safe_load(self.yaml_src)
            self.assertIn("engine", data)
            self.assertIn("risk", data)
        except ImportError:
            # yaml not installed, just check structure
            self.assertIn("engine:", self.yaml_src)


class TestDockerCompose(unittest.TestCase):
    """Tests 7-11: Docker compose auto_trader service."""

    @classmethod
    def setUpClass(cls):
        cls.compose = _read("docker-compose.yml")

    def test_07_correct_cmd(self):
        """auto_trader uses src.engines.main not auto_trading_engine."""
        self.assertIn(
            'src.engines.main', self.compose,
        )
        # Old broken CMD should not exist
        self.assertNotIn(
            'src.engines.auto_trading_engine', self.compose,
        )

    def test_08_has_healthcheck(self):
        """auto_trader has a healthcheck block."""
        # Find auto_trader section
        idx = self.compose.find("auto_trader:")
        section = self.compose[idx:idx + 2000]
        self.assertIn("healthcheck:", section)

    def test_09_log_format_json(self):
        idx = self.compose.find("auto_trader:")
        section = self.compose[idx:idx + 2000]
        self.assertIn("LOG_FORMAT=json", section)

    def test_10_dry_run_env(self):
        idx = self.compose.find("auto_trader:")
        section = self.compose[idx:idx + 2000]
        self.assertIn("DRY_RUN", section)

    def test_11_cycle_interval_env(self):
        idx = self.compose.find("auto_trader:")
        section = self.compose[idx:idx + 2000]
        self.assertIn("CYCLE_INTERVAL", section)


class TestArchitectureDocs(unittest.TestCase):
    """Tests 12-16: ARCHITECTURE.md updated."""

    @classmethod
    def setUpClass(cls):
        cls.doc = _read("docs/ARCHITECTURE.md")

    def test_12_sprint_history_table(self):
        self.assertIn("Sprint History", self.doc)
        self.assertIn("| 10 |", self.doc)
        self.assertIn("| 11 |", self.doc)
        self.assertIn("| 12 |", self.doc)

    def test_13_pipeline_diagram(self):
        self.assertIn("_boot()", self.doc)
        self.assertIn("_run_cycle()", self.doc)
        self.assertIn("set_correlation_id()", self.doc)

    def test_14_engines_main_in_tree(self):
        self.assertIn("main.py", self.doc)
        self.assertIn("__main__.py", self.doc)

    def test_15_trade_repo_in_tree(self):
        self.assertIn("trade_repo.py", self.doc)

    def test_16_logging_config_in_tree(self):
        self.assertIn("logging_config.py", self.doc)


if __name__ == "__main__":
    unittest.main()
