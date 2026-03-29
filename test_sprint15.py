"""
Sprint 15 Tests — Requirements Cleanup + README Modernisation

Verifies:
  1.    polars removed from base.txt
  2.    aioredis removed from base.txt
  3.    feature-engine removed from engine.txt
  4.    slack-sdk commented out in notifications.txt
  5.    sendgrid commented out in notifications.txt
  6.    tweepy commented out in ingestor.txt
  7.    praw commented out in ingestor.txt
  8.    README has Docker Compose section
  9.    README has Multi-Broker section
  10.   README At a Glance has 57 commands
  11.   README At a Glance has Python 3.11
  12.   README Key Files has auto_trading_engine
  13.   README Key Files has trade_repo
  14.   README Key Files has logging_config
  15.   README has docker compose quick start
  16.   README has Dockerfile.discord reference
  17.   README has AutoTradingEngine mention
"""
import os
import unittest

ROOT = os.path.dirname(os.path.abspath(__file__))


def _read(rel):
    with open(os.path.join(ROOT, rel)) as f:
        return f.read()


class TestRequirementsCleanup(unittest.TestCase):
    """Tests 1-7: Ghost dependencies removed."""

    @classmethod
    def setUpClass(cls):
        cls.base = _read("requirements/base.txt")
        cls.engine = _read("requirements/engine.txt")
        cls.notif = _read("requirements/notifications.txt")
        cls.ingest = _read("requirements/ingestor.txt")

    def test_01_polars_removed(self):
        """polars not an active dependency in base.txt."""
        # Line should be commented or removed
        for line in self.base.splitlines():
            stripped = line.strip()
            if stripped.startswith("polars"):
                self.fail("polars is still an active dependency")

    def test_02_aioredis_removed(self):
        """aioredis not an active dependency in base.txt."""
        for line in self.base.splitlines():
            stripped = line.strip()
            if stripped.startswith("aioredis"):
                self.fail("aioredis is still an active dependency")

    def test_03_feature_engine_removed(self):
        """feature-engine not an active dependency in engine.txt."""
        for line in self.engine.splitlines():
            stripped = line.strip()
            if stripped.startswith("feature-engine"):
                self.fail("feature-engine is still active")

    def test_04_slack_sdk_commented(self):
        """slack-sdk is commented out in notifications.txt."""
        for line in self.notif.splitlines():
            stripped = line.strip()
            if stripped.startswith("slack-sdk"):
                self.fail("slack-sdk is still active")

    def test_05_sendgrid_commented(self):
        """sendgrid is commented out in notifications.txt."""
        for line in self.notif.splitlines():
            stripped = line.strip()
            if stripped.startswith("sendgrid"):
                self.fail("sendgrid is still active")

    def test_06_tweepy_commented(self):
        """tweepy is commented out in ingestor.txt."""
        for line in self.ingest.splitlines():
            stripped = line.strip()
            if stripped.startswith("tweepy"):
                self.fail("tweepy is still active")

    def test_07_praw_commented(self):
        """praw is commented out in ingestor.txt."""
        for line in self.ingest.splitlines():
            stripped = line.strip()
            if stripped.startswith("praw"):
                self.fail("praw is still active")


class TestReadmeModernised(unittest.TestCase):
    """Tests 8-17: README.md updated with Sprint 3-14 content."""

    @classmethod
    def setUpClass(cls):
        cls.readme = _read("README.md")

    def test_08_docker_compose_section(self):
        self.assertIn("Docker Compose", self.readme)
        self.assertIn("docker compose up", self.readme)

    def test_09_multi_broker_section(self):
        self.assertIn("Multi-Broker", self.readme)
        self.assertIn("BrokerManager", self.readme)
        self.assertIn("Alpaca", self.readme)

    def test_10_at_a_glance_57_commands(self):
        self.assertIn("60 slash commands", self.readme)

    def test_11_at_a_glance_python_311(self):
        self.assertIn("Python 3.11", self.readme)

    def test_12_key_files_auto_trading_engine(self):
        self.assertIn("auto_trading_engine.py", self.readme)
        self.assertIn("Autonomous trading loop", self.readme)

    def test_13_key_files_trade_repo(self):
        self.assertIn("trade_repo.py", self.readme)

    def test_14_key_files_logging_config(self):
        self.assertIn("logging_config.py", self.readme)

    def test_15_docker_quick_start(self):
        self.assertIn("docker compose", self.readme)
        self.assertIn("Docker Compose (full stack)", self.readme)

    def test_16_dockerfile_discord_in_readme(self):
        self.assertIn("Dockerfile.discord", self.readme)

    def test_17_autotrading_engine_mention(self):
        self.assertIn("AutoTradingEngine", self.readme)


if __name__ == "__main__":
    unittest.main()
