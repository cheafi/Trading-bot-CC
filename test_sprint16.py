"""
Sprint 16 Tests — File Sync + Stale Reference Cleanup

Verifies:
  1.    src/discord_bot.py and src/notifications/discord_bot.py are identical
  2.    src/discord_bot.py has 57 @bot.tree.command decorators
  3.    src/notifications/discord_bot.py has /regime command
  4.    src/notifications/discord_bot.py has /leaderboard command
  5.    src/notifications/discord_bot.py has /recommendations command
  6.    README tagline says 57
  7.    README tagline mentions Telegram
  8.    README diagram says 57 commands
  9.    README diagram says 5,800 lines
  10.   README section heading says 57
  11.   README has /regime command listed
  12.   README has /leaderboard command listed
  13.   README has /recommendations command listed
  14.   ARCHITECTURE.md says 57 (not 54)
  15.   ARCHITECTURE.md Sprint table has Sprint 14
  16.   ARCHITECTURE.md Sprint table has Sprint 15
  17.   ARCHITECTURE.md Sprint table has Sprint 16
"""
import os
import unittest

ROOT = os.path.dirname(os.path.abspath(__file__))


def _read(rel):
    with open(os.path.join(ROOT, rel)) as f:
        return f.read()


class TestDiscordBotSync(unittest.TestCase):
    """Tests 1-5: notifications/discord_bot.py synced with canonical."""

    @classmethod
    def setUpClass(cls):
        cls.canonical = _read("src/discord_bot.py")
        cls.notif = _read("src/notifications/discord_bot.py")

    def test_01_files_identical(self):
        """Canonical and notifications copies are identical."""
        self.assertEqual(self.canonical, self.notif,
            "src/discord_bot.py and src/notifications/discord_bot.py differ")

    def test_02_canonical_has_57_commands(self):
        """src/discord_bot.py has 60 @bot.tree.command (Sprint 37: +3)."""
        count = self.canonical.count("@bot.tree.command")
        self.assertEqual(count, 60,
            f"Expected 60 commands, got {count}")

    def test_03_notif_has_regime(self):
        self.assertIn('name="regime"', self.notif)

    def test_04_notif_has_leaderboard(self):
        self.assertIn('name="leaderboard"', self.notif)

    def test_05_notif_has_recommendations(self):
        self.assertIn('name="recommendations"', self.notif)


class TestReadmeUpdated(unittest.TestCase):
    """Tests 6-13: README.md stale 54 references fixed."""

    @classmethod
    def setUpClass(cls):
        cls.readme = _read("README.md")

    def test_06_tagline_57(self):
        self.assertIn("60 slash commands", self.readme)
        self.assertNotIn("54 slash commands", self.readme)

    def test_07_tagline_telegram(self):
        self.assertIn("Telegram", self.readme)

    def test_08_diagram_57_commands(self):
        self.assertIn("DISCORD INTERFACE (60 commands)", self.readme)

    def test_09_diagram_5800_lines(self):
        self.assertIn("6,100 lines", self.readme)

    def test_10_section_heading_57(self):
        self.assertIn("All 60 Slash Commands", self.readme)

    def test_11_regime_in_readme(self):
        self.assertIn("/regime", self.readme)

    def test_12_leaderboard_in_readme(self):
        self.assertIn("/leaderboard", self.readme)

    def test_13_recommendations_in_readme(self):
        self.assertIn("/recommendations", self.readme)


class TestArchitectureUpdated(unittest.TestCase):
    """Tests 14-17: ARCHITECTURE.md updated."""

    @classmethod
    def setUpClass(cls):
        cls.arch = _read("docs/ARCHITECTURE.md")

    def test_14_arch_says_57(self):
        self.assertIn("60 slash commands", self.arch)
        self.assertNotIn("54 slash commands", self.arch)

    def test_15_sprint_14_in_table(self):
        self.assertIn("| 14 |", self.arch)
        self.assertIn("Typed Exceptions", self.arch)

    def test_16_sprint_15_in_table(self):
        self.assertIn("| 15 |", self.arch)

    def test_17_sprint_16_in_table(self):
        self.assertIn("| 16 |", self.arch)
        self.assertIn("Sync", self.arch)


if __name__ == "__main__":
    unittest.main()
