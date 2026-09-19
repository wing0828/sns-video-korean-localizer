import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from xsubtitle.core import (
    SubtitleCue,
    UserFacingError,
    ffmpeg_burn_command,
    format_srt_timestamp,
    process_job,
    render_srt,
    translate_cues_with_gemini,
)


class CoreTests(unittest.TestCase):
    def test_srt_rendering(self):
        cues = [SubtitleCue(0, 61.2346, "  Hello   world  ")]
        self.assertEqual(format_srt_timestamp(3661.005), "01:01:01,005")
        self.assertEqual(
            render_srt(cues),
            "1\n00:00:00,000 --> 00:01:01,235\nHello world\n",
        )

    def test_gemini_translation_runs_translation_and_review_passes(self):
        calls = []

        class FakeModels:
            def generate_content(self, **kwargs):
                calls.append(kwargs)
                text = "초벌" if len(calls) == 1 else "최종 번역"
                return SimpleNamespace(parsed=[{"index": 0, "text": text}])

        fake_genai = SimpleNamespace(Client=lambda **_kwargs: SimpleNamespace(models=FakeModels()))
        fake_types = SimpleNamespace(GenerateContentConfig=lambda **kwargs: kwargs)
        updates = []
        with patch.dict(
            sys.modules,
            {
                "google": SimpleNamespace(genai=fake_genai),
                "google.genai": SimpleNamespace(types=fake_types),
                "google.genai.types": fake_types,
            },
        ), patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}, clear=True):
            result = translate_cues_with_gemini(
                [SubtitleCue(0, 1, "Hello")],
                lambda value, text: updates.append((value, text)),
            )

        self.assertEqual(result, [SubtitleCue(0, 1, "최종 번역")])
        self.assertEqual(len(calls), 2)
        self.assertEqual(updates[0][0], 1.0)

    def test_gemini_translation_requires_api_key(self):
        with patch.dict("os.environ", {}, clear=True), self.assertRaisesRegex(
            UserFacingError, "GEMINI_API_KEY"
        ):
            translate_cues_with_gemini([SubtitleCue(0, 1, "Hello")])

    def test_ffmpeg_command_has_mobile_subtitle_style_and_fast_encoding(self):
        with tempfile.TemporaryDirectory() as directory, patch(
            "xsubtitle.core.shutil.which", return_value="/usr/bin/ffmpeg"
        ):
            root = Path(directory)
            command = ffmpeg_burn_command(
                root / "input.mp4", root / "ko.srt", root / "out.mp4"
            )

        video_filter = command[command.index("-vf") + 1]
        self.assertIn("force_original_aspect_ratio=decrease", video_filter)
        self.assertIn("BorderStyle=3", video_filter)
        self.assertIn("PrimaryColour=&H00151515", video_filter)
        self.assertIn("OutlineColour=&H004DD8FF", video_filter)
        self.assertIn("libx264", command)
        self.assertIn("veryfast", command)
        self.assertIn("+faststart", command)

    def test_ffmpeg_command_requires_ffmpeg(self):
        with patch("xsubtitle.core.shutil.which", return_value=None), self.assertRaisesRegex(
            UserFacingError, "ffmpeg"
        ):
            ffmpeg_burn_command(Path("input.mp4"), Path("ko.srt"), Path("out.mp4"))

    def test_process_job_writes_subtitles_and_burns_video(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            upload = root / "input.mp4"
            upload.write_bytes(b"video")
            source_cues = [SubtitleCue(0, 1.25, "Hello")]
            korean_cues = [SubtitleCue(0, 1.25, "안녕하세요")]
            updates = []

            def fake_burn(video, subtitles, output):
                self.assertTrue(video.is_file())
                self.assertTrue(subtitles.is_file())
                output.write_bytes(b"rendered")

            with (
                patch("xsubtitle.core.transcribe_video", return_value=source_cues),
                patch("xsubtitle.core.translate_cues_with_gemini", return_value=korean_cues),
                patch("xsubtitle.core.burn_subtitles", side_effect=fake_burn),
            ):
                result = process_job(
                    upload,
                    output_root=root / "outputs",
                    progress_callback=lambda value, text: updates.append((value, text)),
                )

            self.assertEqual(result.source_srt.read_text(encoding="utf-8").splitlines()[-1], "Hello")
            self.assertEqual(result.korean_srt.read_text(encoding="utf-8").splitlines()[-1], "안녕하세요")
            self.assertEqual(result.subtitled_video.read_bytes(), b"rendered")
            self.assertEqual([value for value, _ in updates], sorted(value for value, _ in updates))
            self.assertEqual(updates[-1][0], 1.0)

    def test_process_job_rejects_non_video_upload(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            upload = root / "notes.txt"
            upload.write_text("not a video", encoding="utf-8")
            with self.assertRaisesRegex(UserFacingError, "영상 형식"):
                process_job(upload, output_root=root / "outputs")

    def test_failed_job_removes_partial_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            upload = root / "input.mp4"
            upload.write_bytes(b"video")
            output_root = root / "outputs"
            with (
                patch("xsubtitle.core.transcribe_video", side_effect=UserFacingError("실패")),
                self.assertRaises(UserFacingError),
            ):
                process_job(upload, output_root=output_root)
            self.assertEqual(list(output_root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
