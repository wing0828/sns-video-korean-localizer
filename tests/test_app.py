import unittest
from types import SimpleNamespace
from unittest.mock import patch

import app
from xsubtitle.core import KOREAN_VOICES, UserFacingError


class AppPresetTests(unittest.TestCase):
    def test_subtitle_preset_maps_to_burn_in_only(self):
        self.assertEqual(app.resolve_preset("한국어 자막 영상 · 추천"), (True, False))

    def test_dubbing_preset_maps_to_burn_in_and_dubbing(self):
        self.assertEqual(app.resolve_preset("한국어 더빙 + 자막 영상"), (True, True))

    def test_unknown_preset_is_user_facing_error(self):
        with self.assertRaisesRegex(UserFacingError, "결과"):
            app.resolve_preset("알 수 없음")

    @patch("app.process_job")
    def test_run_job_passes_url_only_and_selected_preset(self, process_job):
        process_job.return_value = SimpleNamespace(
            job_id="job-1",
            english_srt="en.srt",
            korean_srt="ko.srt",
            subtitled_video="subtitled.mp4",
            dubbed_video="dubbed.mp4",
        )
        progress_updates = []

        result = app.run_job(
            "https://youtu.be/example",
            "한국어 더빙 + 자막 영상",
            "small",
            KOREAN_VOICES["female"],
            "replace",
            "none",
            "fast",
            progress=lambda value, desc: progress_updates.append((value, desc)),
        )

        args, kwargs = process_job.call_args
        self.assertEqual(args[:4], ("https://youtu.be/example", None, True, "small"))
        self.assertTrue(kwargs["dubbing"])
        self.assertEqual(kwargs["video_quality"], "fast")
        kwargs["progress_callback"](0.5, "처리 중")
        self.assertEqual(progress_updates, [(0.5, "처리 중 · 50%")])
        self.assertEqual(result[1:], ("en.srt", "ko.srt", "subtitled.mp4", "dubbed.mp4"))


if __name__ == "__main__":
    unittest.main()
