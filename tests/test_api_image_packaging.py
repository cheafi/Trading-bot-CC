"""Static packaging contracts; no launcher imports or trading service starts.

These deliberately check the narrow allowlist, not emulate Docker's matcher.
An image build without bind mounts remains the integration check.
"""

from pathlib import Path
import re
import shlex
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_SCRIPTS = ("scripts/cc_instant.py", "scripts/run_telegram_bot.py")
ARCHITECTURE_DOC = "docs/CC_X_ARCHITECTURE.md"
UNIVERSE_CONFIG = "data/universe.json"


class ApiImagePackagingTests(unittest.TestCase):
    def test_runtime_sources_exist(self):
        for source in (
            "_cc_instant.py",
            *RUNTIME_SCRIPTS,
            ARCHITECTURE_DOC,
            UNIVERSE_CONFIG,
        ):
            with self.subTest(source=source):
                self.assertTrue((ROOT / source).is_file(), source)

    def test_dockerignore_keeps_narrow_runtime_allowlists(self):
        rules = [
            line.strip()
            for line in (ROOT / ".dockerignore")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        for directory, sources in (
            ("scripts", RUNTIME_SCRIPTS),
            ("docs", (ARCHITECTURE_DOC,)),
            ("data", (UNIVERSE_CONFIG,)),
        ):
            with self.subTest(directory=directory):
                # Exclude children, keeping the parent traversable.
                self.assertNotIn(f"{directory}/", rules)
                self.assertNotIn(directory, rules)
                deny = f"{directory}/*"
                self.assertIn(deny, rules)
                start = rules.index(deny)
                scoped_rules = [
                    rule
                    for rule in rules[start:]
                    if rule.lstrip("!").startswith(f"{directory}/")
                ]
                expected = [deny, *(f"!{s}" for s in sources)]
                self.assertEqual(scoped_rules, expected)

    def test_image_copies_required_runtime_files_explicitly(self):
        copies = []
        path = ROOT / "docker/Dockerfile.api"
        dockerfile = path.read_text(encoding="utf-8")
        for line in dockerfile.splitlines():
            if not line.startswith("COPY "):
                continue
            tokens = shlex.split(line)
            copies.append([t for t in tokens[1:] if not t.startswith("--")])
        self.assertIn(["_cc_instant.py", "./"], copies)
        self.assertIn([*RUNTIME_SCRIPTS, "scripts/"], copies)
        self.assertIn([ARCHITECTURE_DOC, "docs/"], copies)
        self.assertIn([UNIVERSE_CONFIG, "data/"], copies)
        self.assertNotIn(["scripts/", "scripts/"], copies)
        self.assertNotIn(["docs/", "docs/"], copies)
        self.assertNotIn(["data/", "data/"], copies)

    def test_both_dev_services_mount_scripts_readonly(self):
        compose = (ROOT / "docker-compose.dev.yml").read_text(encoding="utf-8")
        for service in ("api", "telegram-bot"):
            with self.subTest(service=service):
                block = re.search(
                    rf"^  {re.escape(service)}:\n(.*?)(?=^  \S|\Z)",
                    compose,
                    re.MULTILINE | re.DOTALL,
                )
                self.assertIsNotNone(block, service)
                self.assertIn(
                    "      - ./scripts:/app/scripts:ro,delegated",
                    block.group(1),
                )


if __name__ == "__main__":
    unittest.main()
