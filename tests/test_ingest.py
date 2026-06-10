from __future__ import annotations

import unittest
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from ingest import (
    PROGRESS_FILENAME,
    _choose_existing_result_action,
    _load_progress,
    _save_progress,
    cmd_draft,
)
from schemas import ParsedBlock, ParsedDocument


class DraftResumeTest(unittest.TestCase):
    def test_cli_rebuild_really_deletes_and_regenerates(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "input"
            output_dir = root / "result"
            input_dir.mkdir()
            output_dir.mkdir()
            (output_dir / "old.md").write_text("old", encoding="utf-8")
            (input_dir / "001.md").write_text(
                "# 第一章\n\n" + "这是一段用于生成知识库草稿的测试内容。" * 20,
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "ingest.py",
                    "draft",
                    "--input",
                    str(input_dir),
                    "--output",
                    str(output_dir),
                ],
                cwd=Path(__file__).resolve().parents[1],
                input="１\n",
                text=True,
                capture_output=True,
                check=False,
            )

            outputs = sorted(path.name for path in output_dir.glob("*.md"))

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("old.md", outputs)
        self.assertTrue(outputs)

    def test_rebuild_deletes_existing_files_and_generates(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "input"
            output_dir = root / "result"
            input_dir.mkdir()
            output_dir.mkdir()
            old = output_dir / "old.md"
            old.write_text("old", encoding="utf-8")
            source = input_dir / "001.md"
            source.write_text("source", encoding="utf-8")
            block = ParsedBlock(
                source_doc="001.md",
                source_section="1",
                content="x" * 80,
                pages=[1],
            )
            parsed = ParsedDocument(source, "001.md", "source", [block])

            class Args:
                input = str(input_dir)
                output = str(output_dir)
                max_chars = None
                status = "active"

            with patch("builtins.input", return_value="1"), patch(
                "ingest.parse_document", return_value=parsed
            ), patch("ingest.normalize_block", return_value=[]):
                code = cmd_draft(Args())

        self.assertEqual(code, 0)
        self.assertFalse(old.exists())

    def test_choose_existing_result_action_supports_three_choices(self):
        with TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            existing = [output_dir / "old.md"]

            with patch("builtins.input", return_value="1"):
                self.assertEqual(
                    _choose_existing_result_action(output_dir, existing),
                    "rebuild",
                )
            with patch("builtins.input", return_value="1：delete and rebuild"):
                self.assertEqual(
                    _choose_existing_result_action(output_dir, existing),
                    "rebuild",
                )
            with patch("builtins.input", return_value="2"):
                self.assertEqual(
                    _choose_existing_result_action(output_dir, existing),
                    "resume",
                )
            with patch("builtins.input", return_value="3"):
                self.assertEqual(
                    _choose_existing_result_action(output_dir, existing),
                    "exit",
                )

    def test_progress_file_round_trips_resume_position(self):
        with TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            progress_path = output_dir / PROGRESS_FILENAME
            files = [
                Path("/repo/input/pdf/001-alpha.pdf"),
                Path("/repo/input/pdf/002-beta.pdf"),
            ]

            _save_progress(
                progress_path,
                input_path=Path("/repo/input"),
                output_dir=output_dir,
                files=files,
                run_timestamp="20260610153045",
                run_trace_id="a1b2c3d4",
                source_order=12,
                total_items=12,
                file_index=1,
                block_index=3,
                status="failed",
                error="SystemExit(1)",
            )

            data = _load_progress(progress_path)

        self.assertIsNotNone(data)
        assert data is not None
        self.assertEqual(data["status"], "failed")
        self.assertEqual(data["run_timestamp"], "20260610153045")
        self.assertEqual(data["run_trace_id"], "a1b2c3d4")
        self.assertEqual(data["source_order"], 12)
        self.assertEqual(data["total_items"], 12)
        self.assertEqual(data["file_index"], 1)
        self.assertEqual(data["block_index"], 3)
        self.assertEqual(data["current_file_name"], "002-beta.pdf")


if __name__ == "__main__":
    unittest.main()
