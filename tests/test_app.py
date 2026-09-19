import unittest
import sys
from types import SimpleNamespace
from unittest.mock import patch

class DummyComponent:
    def __init__(self, *_args, **_kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def click(self, *_args, **_kwargs):
        return None


fake_gradio = SimpleNamespace(
    Blocks=DummyComponent,
    Column=DummyComponent,
    Group=DummyComponent,
    Row=DummyComponent,
    HTML=DummyComponent,
    File=DummyComponent,
    Radio=DummyComponent,
    Button=DummyComponent,
    Markdown=DummyComponent,
    Textbox=DummyComponent,
    Progress=lambda: DummyComponent(),
    Error=RuntimeError,
)
sys.modules.setdefault("gradio", fake_gradio)

import app


class AppTests(unittest.TestCase):
    @patch("app.process_job")
    def test_run_job_processes_uploaded_video_with_burned_subtitles(self, process_job):
        process_job.return_value = SimpleNamespace(
            job_id="job-1",
            source_srt="source.srt",
            korean_srt="ko.srt",
            subtitled_video="subtitled.mp4",
        )
        progress_updates = []

        result = app.run_job(
            "video.mp4",
            "small",
            progress=lambda value, desc: progress_updates.append((value, desc)),
        )

        args, kwargs = process_job.call_args
        self.assertEqual(args[:2], ("video.mp4", "small"))
        kwargs["progress_callback"](0.5, "처리 중")
        self.assertEqual(progress_updates, [(0.5, "처리 중 · 50%")])
        self.assertEqual(result[1:], ("subtitled.mp4", "ko.srt", "source.srt"))


if __name__ == "__main__":
    unittest.main()
