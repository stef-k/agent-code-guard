import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from agent_code_guard.analysis.provider import TreeSitterProvider
from agent_code_guard.analysis.regions import executable_regions
from agent_code_guard.analysis.facts import AnalysisFacts, FileFacts
from agent_code_guard.file_selection import resolve_invocation
from agent_code_guard.guards import callable_size, loc
from agent_code_guard.invocation import load_configuration


class SharedInvocationTests(unittest.TestCase):
    def args(self, patterns):
        return SimpleNamespace(
            paths=["."], changed_only=False, staged=False, base_ref=None,
            config=None, scope_exclude=patterns, include=[], exclude=[],
            warn=None, fail=None, count_blank_lines=False, ignore_comment_lines=False,
        )

    def test_candidate_canonicalization_does_not_grow_with_exclusion_patterns(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            for name in ("a.py", "b.py", "c.md"):
                (root / name).write_text("pass\n", encoding="utf-8")
            import agent_code_guard.file_selection as selection
            original = selection._canonicalize
            counts = []
            with patch.object(selection, "find_repo_root", return_value=None):
                for patterns in ([], [f"never-{index}/**" for index in range(50)]):
                    with patch.object(selection, "_canonicalize", wraps=original) as canonicalize:
                        context = resolve_invocation(self.args(patterns), root, {})
                        self.assertEqual(len(context.selected_files), 3)
                        counts.append(canonicalize.call_count)
            self.assertEqual(counts[0], counts[1])

    def test_guards_use_loaded_immutable_document_and_selected_identity(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            config_path = root / "config.json"
            source = root / "sample.py"
            config_path.write_text('{"guards":{"loc":{"warnAt":2,"failAt":3}}}', encoding="utf-8")
            source.write_text("one\ntwo\n", encoding="utf-8")
            document = load_configuration(str(config_path), root)
            args = self.args([])
            args.config = str(config_path)
            context = resolve_invocation(args, root, document)
            with self.assertRaises(TypeError):
                document["guards"]["loc"]["warnAt"] = 10
            with self.assertRaises(TypeError):
                document["guards"] |= {"futureGuard": {}}
            with patch.object(Path, "read_text", side_effect=AssertionError("configuration reread")):
                config = loc.load_config(args, document)
                result = loc.run(context.root, config, context.selected_files)
                callable_size.load_config(args, document)
            self.assertEqual(result.findings[0].path, "sample.py")

    def test_vue_regions_share_one_original_line_index_and_map_utf8_crlf(self):
        with tempfile.TemporaryDirectory() as value:
            path = Path(value) / "sample.vue"
            path.write_bytes((
                "<script>\r\nconst label = 'µ';\r\n</script>\r\n"
                "<script lang=\"ts\">\r\nconst count: number = 1;\r\n</script>\r\n"
            ).encode("utf-8"))
            regions = executable_regions(path, TreeSitterProvider())
            self.assertEqual(len(regions), 2)
            self.assertIs(regions[0].original_line_starts, regions[1].original_line_starts)
            point = regions[0].original_point(1, len("const label = '".encode("utf-8")) + 2)
            self.assertEqual((point.line, point.byte_column), (2, 18))

    def test_reporting_path_lookups_do_not_rescan_analyzed_files(self):
        class CountingFiles(tuple):
            iterations = 0

            def __iter__(self):
                self.iterations += 1
                return super().__iter__()

        files = CountingFiles(
            FileFacts(Path(f"file-{index}.py"), (), (), (), 1, f"src/file-{index}.py")
            for index in range(100)
        )
        facts = AnalysisFacts(files)
        construction_iterations = files.iterations
        for _ in range(100):
            self.assertEqual(facts.reporting_path_for(Path("file-99.py")), "src/file-99.py")
        self.assertEqual(files.iterations, construction_iterations)


if __name__ == "__main__":
    unittest.main()
