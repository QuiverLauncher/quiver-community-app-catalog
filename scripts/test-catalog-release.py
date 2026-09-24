import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("release", Path(__file__).with_name("catalog-release.py"))
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.docs = {p: {"name": p, "version": "1.2.3", "apps": []} for p in release.LISTS}
        self.state = release.snapshot(self.docs)

    def test_unchanged_and_formatting_only_do_not_release(self):
        self.assertEqual(release.plan(self.docs, self.state), ({}, self.state))
        self.assertEqual(release.fingerprint(self.docs[release.LISTS[0]]),
                         release.fingerprint(json.loads(json.dumps(self.docs[release.LISTS[0]], indent=4))))

    def test_many_apps_one_bump_and_only_changed_lists(self):
        path = release.LISTS[0]
        self.docs[path]["apps"].extend([{"name": "A"}, {"name": "B"}])
        updates, state = release.plan(self.docs, self.state)
        self.assertEqual(updates, {path: "1.2.4"})
        self.docs[path]["version"] = updates[path]
        self.assertEqual(release.plan(self.docs, state), ({}, state))
        self.docs[path]["apps"].append({"name": "C"})
        self.assertEqual(release.plan(self.docs, state)[0], {path: "1.2.5"})

    def test_multiple_lists_and_manual_legacy_bumps(self):
        for path in release.LISTS[:2]:
            self.docs[path]["apps"].append({"name": "A"})
        self.docs[release.LISTS[0]]["version"] = "1.2.4"
        updates, state = release.plan(self.docs, self.state)
        self.assertEqual(updates, {release.LISTS[0]: "1.2.5", release.LISTS[1]: "1.2.4"})
        self.assertEqual(state[release.LISTS[0]]["version"], "1.2.5")

    def test_rejects_decreased_or_invalid_versions_and_unknown_lists(self):
        for invalid in ["1.2.2", "garbage"]:
            self.docs[release.LISTS[0]]["version"] = invalid
            with self.assertRaises(ValueError):
                release.plan(self.docs, self.state)
        with self.assertRaises(ValueError):
            release.plan({}, self.state)

    def test_write_changes_only_version_and_is_repeatable(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "community-app-catalog").mkdir()
            (root / ".github").mkdir()
            (root / release.STATE).write_text(json.dumps(self.state), encoding="utf-8")
            self.docs[release.LISTS[0]]["apps"].append({"name": "A"})
            originals = {}
            for path, doc in self.docs.items():
                originals[path] = json.dumps(doc, indent=2) + "\n"
                (root / path).write_text(originals[path], encoding="utf-8")
            release.write_plan(root)
            for path in release.LISTS:
                expected = originals[path].replace('"1.2.3"', '"1.2.4"') if path == release.LISTS[0] else originals[path]
                self.assertEqual((root / path).read_text(encoding="utf-8"), expected)
            self.assertEqual(release.write_plan(root), ({}, False))

    def test_validation_rejects_app_edits_wrong_bumps_and_arbitrary_files(self):
        with tempfile.TemporaryDirectory() as temp:
            base, head = Path(temp) / "base", Path(temp) / "head"
            self.docs[release.LISTS[0]]["apps"].append({"name": "A"})
            for root in [base, head]:
                (root / "community-app-catalog").mkdir(parents=True)
                (root / ".github").mkdir()
                (root / release.STATE).write_text(json.dumps(self.state), encoding="utf-8")
                for path, doc in self.docs.items():
                    (root / path).write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
                release.run("git", "-C", str(root), "init")
                release.run("git", "-C", str(root), "add", ".")
            release.write_plan(head)
            release.validate(base, head)
            path = head / release.LISTS[0]
            good = path.read_text(encoding="utf-8")
            for bad in [good.replace('"1.2.4"', '"1.2.5"'), good.replace('"A"', '"Injected"')]:
                path.write_text(bad, encoding="utf-8")
                with self.assertRaises(ValueError):
                    release.validate(base, head)
            path.write_text(good, encoding="utf-8")
            (head / "unexpected.txt").write_text("not allowed", encoding="utf-8")
            release.run("git", "-C", str(head), "add", ".")
            with self.assertRaises(ValueError):
                release.validate(base, head)


if __name__ == "__main__":
    unittest.main()
