import tempfile
import unittest
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from xsubtitle.core import (
    SubtitleCue,
    UserFacingError,
    atempo_filters,
    create_dubbed_video,
    detect_platform,
    download_video,
    ffmpeg_burn_command,
    ffmpeg_mux_command,
    ffmpeg_timeline_command,
    format_srt_timestamp,
    process_job,
    probe_audio_duration,
    render_srt,
    resolve_media_executable,
    resolve_media_pair,
    translate_cues,
    validate_x_url,
    validate_video_url,
    video_has_audio,
)


class CoreTests(unittest.TestCase):
    def test_media_executable_prefers_path(self):
        with patch("xsubtitle.core.shutil.which", return_value=r"C:\\tools\\ffmpeg.exe"):
            self.assertEqual(resolve_media_executable("ffmpeg"), Path(r"C:\\tools\\ffmpeg.exe").resolve())

    def test_media_executable_finds_winget_install_without_path(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = (
                Path(directory) / "Microsoft" / "WinGet" / "Packages"
                / "Gyan.FFmpeg_Microsoft.Winget.Source_x" / "ffmpeg-9.0-full_build"
                / "bin" / "ffmpeg.exe"
            )
            executable.parent.mkdir(parents=True)
            executable.write_bytes(b"")
            executable.with_name("ffprobe.exe").write_bytes(b"")
            with patch("xsubtitle.core.shutil.which", return_value=None), patch.dict(
                "os.environ", {"LOCALAPPDATA": directory}, clear=True
            ):
                self.assertEqual(resolve_media_executable("ffmpeg"), executable.resolve())

    def test_media_pair_uses_numeric_winget_version_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "Microsoft" / "WinGet" / "Packages" / "Gyan.FFmpeg_x"
            for version in ("9.0", "10.0"):
                binary_dir = root / f"ffmpeg-{version}-full_build" / "bin"
                binary_dir.mkdir(parents=True)
                (binary_dir / "ffmpeg.exe").write_bytes(b"")
                (binary_dir / "ffprobe.exe").write_bytes(b"")
            with patch("xsubtitle.core.shutil.which", return_value=None), patch.dict(
                "os.environ", {"LOCALAPPDATA": directory}, clear=True
            ):
                pair = resolve_media_pair()
            self.assertIsNotNone(pair)
            self.assertIn("ffmpeg-10.0-full_build", str(pair[0]))

    def test_media_pair_rejects_split_path_and_incomplete_winget_install(self):
        with tempfile.TemporaryDirectory() as directory:
            binary_dir = (
                Path(directory) / "Microsoft" / "WinGet" / "Packages" / "Gyan.FFmpeg_x"
                / "ffmpeg-10.0-full_build" / "bin"
            )
            binary_dir.mkdir(parents=True)
            (binary_dir / "ffmpeg.exe").write_bytes(b"")
            split = {"ffmpeg": r"C:\\one\\ffmpeg.exe", "ffprobe": r"D:\\two\\ffprobe.exe"}
            with patch("xsubtitle.core.shutil.which", side_effect=split.get), patch.dict(
                "os.environ", {"LOCALAPPDATA": directory}, clear=True
            ):
                self.assertIsNone(resolve_media_pair())

    def test_probe_resolution_failures_are_user_facing(self):
        with patch("xsubtitle.core.resolve_media_executable", side_effect=FileNotFoundError):
            with self.assertRaises(UserFacingError):
                probe_audio_duration(Path("audio.wav"))
            with self.assertRaises(UserFacingError):
                video_has_audio(Path("video.mp4"))

    def test_validate_x_url_accepts_supported_hosts(self):
        urls = [
            "https://x.com/user/status/1",
            "https://x.com/user/status/1/video/1",
            "https://x.com/user/status/1/photo/1",
            "https://x.com/sairahul1/status/2085697283728044114",
            "https://www.twitter.com/user/status/1",
            "https://mobile.twitter.com/user/status/1",
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(validate_x_url(url), url)

    def test_validate_x_url_rejects_unsafe_values(self):
        urls = [
            "https://evil.example/x.com/status/1",
            "https://x.com.evil.example/status/1",
            "file:///tmp/video",
            "https://user:pass@x.com/status/1",
            "https://x.com/",
        ]
        for url in urls:
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_x_url(url)

    def test_validate_video_url_accepts_each_supported_platform(self):
        cases = {
            "X/Twitter": "https://x.com/u/status/1",
            "YouTube": "https://youtu.be/abc",
            "TikTok": "https://www.tiktok.com/@u/video/1",
            "Instagram": "https://www.instagram.com/reel/abc/",
            "Facebook": "https://fb.watch/abc/",
            "Reddit": "https://redd.it/abc",
            "Vimeo": "https://vimeo.com/123",
            "Twitch": "https://clips.twitch.tv/ClipName",
            "Threads": "https://www.threads.net/@u/post/abc",
        }
        for platform, url in cases.items():
            with self.subTest(platform=platform):
                self.assertEqual(validate_video_url(url), url)
                self.assertEqual(detect_platform(url), platform)

    def test_validate_video_url_rejects_lookalikes_credentials_and_non_http(self):
        for url in [
            "https://youtube.com.evil.test/watch?v=1",
            "https://evil.youtube.com/watch?v=1",
            "https://user:pass@instagram.com/reel/1",
            "file:///tmp/video.mp4",
            "javascript://youtube.com/watch?v=1",
            "http://youtube.com/watch?v=1",
            "https://www.facebook.com/l.php?u=https%3A%2F%2F127.0.0.1%2F",
            "https://www.youtube.com/redirect?q=http%3A%2F%2F169.254.169.254%2F",
            "https://www.instagram.com/accounts/login/",
        ]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_video_url(url)

    @patch("xsubtitle.core.resolve_media_pair", return_value=(Path("C:/media/bin/ffmpeg.exe"), Path("C:/media/bin/ffprobe.exe")))
    def test_download_video_builds_safe_yt_dlp_options_with_optional_cookie(self, _media_pair):
        captured = []

        class FakeYoutubeDL:
            def __init__(self, options):
                captured.append(options)

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def extract_info(self, _url, download):
                self.assert_download = download
                return {"id": "1"}

            def prepare_filename(self, _info):
                path = Path(captured[-1]["outtmpl"].replace("%(ext)s", "mp4"))
                path.write_bytes(b"video")
                return str(path)

        with tempfile.TemporaryDirectory() as directory, patch.dict(
            sys.modules, {"yt_dlp": SimpleNamespace(YoutubeDL=FakeYoutubeDL)}
        ):
            root = Path(directory)
            download_video("https://youtu.be/abc", root, "chrome", "fast")
            download_video("https://youtu.be/def", root, "none", "standard")
            download_video("https://youtu.be/ghi", root, "none", "original")

        self.assertTrue(captured[0]["noplaylist"])
        self.assertEqual(Path(captured[0]["ffmpeg_location"]).name, "bin")
        self.assertEqual(captured[0]["cookiesfrombrowser"], ("chrome",))
        self.assertNotIn("cookiesfrombrowser", captured[1])
        self.assertIn("height<=360", captured[0]["format"])
        self.assertIn("height<=720", captured[1]["format"])
        for options in captured[:2]:
            alternatives = options["format"].split("/")
            self.assertTrue(all("height<=" in alternative for alternative in alternatives))
            self.assertNotIn("best", alternatives)
            self.assertNotIn("worst", alternatives)
        self.assertEqual(captured[2]["format"], "bestvideo*+bestaudio/best")

    def test_download_video_rejects_unknown_quality(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            sys.modules, {"yt_dlp": SimpleNamespace()}
        ), self.assertRaises(UserFacingError):
            download_video("https://x.com/u/status/1", Path(directory), video_quality="4k")

    @patch("xsubtitle.core.resolve_media_pair", return_value=None)
    def test_download_video_retries_without_cookie_after_dpapi_failure(self, _media_pair):
        captured = []

        class FakeYoutubeDL:
            def __init__(self, options):
                self.options = options
                captured.append(options)

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def extract_info(self, _url, download):
                self.options["progress_hooks"][0](
                    {"status": "downloading", "downloaded_bytes": 10, "total_bytes": 100}
                )
                if "cookiesfrombrowser" in self.options:
                    raise RuntimeError("ERROR: Failed to decrypt cookies with DPAPI")
                self.options["progress_hooks"][0]({"status": "finished"})
                return {"id": "1"}

            def prepare_filename(self, _info):
                path = Path(self.options["outtmpl"].replace("%(ext)s", "mp4"))
                path.write_bytes(b"video")
                return str(path)

        updates = []
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            sys.modules, {"yt_dlp": SimpleNamespace(YoutubeDL=FakeYoutubeDL)}
        ):
            result = download_video(
                "https://x.com/u/status/1", Path(directory), "edge",
                progress_callback=lambda value, text: updates.append((value, text)),
            )
            self.assertTrue(result.is_file())

        self.assertEqual(captured[0]["cookiesfrombrowser"], ("edge",))
        self.assertNotIn("cookiesfrombrowser", captured[1])
        self.assertEqual([value for value, _ in updates], [0.05, 0.05, 0.5, 1.0])

    @patch("xsubtitle.core.resolve_media_pair", return_value=None)
    def test_download_video_does_not_retry_unrelated_failure(self, _media_pair):
        calls = []

        class FakeYoutubeDL:
            def __init__(self, options):
                calls.append(options)

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def extract_info(self, _url, download):
                raise RuntimeError("HTTP Error 403: Forbidden")

        with tempfile.TemporaryDirectory() as directory, patch.dict(
            sys.modules, {"yt_dlp": SimpleNamespace(YoutubeDL=FakeYoutubeDL)}
        ), self.assertRaises(UserFacingError):
            download_video("https://x.com/u/status/1", Path(directory), "edge")

        self.assertEqual(len(calls), 1)

    @patch("xsubtitle.core.resolve_media_pair", return_value=None)
    def test_download_video_cookie_retry_failure_is_actionable(self, _media_pair):
        class FakeYoutubeDL:
            def __init__(self, options):
                self.options = options

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def extract_info(self, _url, download):
                if "cookiesfrombrowser" in self.options:
                    raise RuntimeError("ERROR: Failed to decrypt cookies with DPAPI")
                raise RuntimeError("Video unavailable")

        with tempfile.TemporaryDirectory() as directory, patch.dict(
            sys.modules, {"yt_dlp": SimpleNamespace(YoutubeDL=FakeYoutubeDL)}
        ), self.assertRaisesRegex(UserFacingError, "쿠키 없이 다시 시도.*공개 게시물"):
            download_video("https://x.com/u/status/1", Path(directory), "edge")

    def test_srt_rendering_and_translation(self):
        cues = [SubtitleCue(0, 61.2346, "  Hello   world  ")]
        translated = translate_cues(cues, lambda text: "안녕하세요")
        self.assertEqual(format_srt_timestamp(3661.005), "01:01:01,005")
        self.assertEqual(render_srt(cues), "1\n00:00:00,000 --> 00:01:01,235\nHello world\n")
        self.assertEqual(translated, [SubtitleCue(0, 61.2346, "안녕하세요")])

    def test_translation_reports_cue_progress(self):
        updates = []
        cues = [SubtitleCue(0, 1, "One"), SubtitleCue(1, 2, "Two")]
        translate_cues(cues, str.upper, lambda value, text: updates.append((value, text)))
        self.assertEqual([value for value, _ in updates], [0.5, 1.0])

    @patch("xsubtitle.core.resolve_media_pair", return_value=None)
    def test_download_reports_actual_byte_progress_monotonically(self, _media_pair):
        class FakeYoutubeDL:
            def __init__(self, options):
                self.options = options

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def extract_info(self, _url, download):
                hook = self.options["progress_hooks"][0]
                hook({"status": "downloading", "downloaded_bytes": 25, "total_bytes": 100})
                hook({"status": "downloading", "downloaded_bytes": 10, "total_bytes": 100})
                hook({"status": "finished"})
                return {"id": "1"}

            def prepare_filename(self, _info):
                path = Path(self.options["outtmpl"].replace("%(ext)s", "mp4"))
                path.write_bytes(b"video")
                return str(path)

        updates = []
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            sys.modules, {"yt_dlp": SimpleNamespace(YoutubeDL=FakeYoutubeDL)}
        ):
            download_video(
                "https://youtu.be/abc", Path(directory),
                progress_callback=lambda value, text: updates.append((value, text)),
            )
        self.assertEqual([value for value, _ in updates], [0.125, 0.125, 0.5, 1.0])

    @patch("xsubtitle.core.resolve_media_pair", return_value=None)
    def test_download_aggregates_video_and_audio_formats(self, _media_pair):
        class FakeYoutubeDL:
            def __init__(self, options):
                self.options = options

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def extract_info(self, _url, download):
                hook = self.options["progress_hooks"][0]
                hook({"status": "finished", "info_dict": {"format_id": "video"}})
                hook({"status": "downloading", "downloaded_bytes": 10, "total_bytes": 20,
                      "info_dict": {"format_id": "audio"}})
                hook({"status": "finished", "info_dict": {"format_id": "audio"}})
                return {"id": "1"}

            def prepare_filename(self, _info):
                path = Path(self.options["outtmpl"].replace("%(ext)s", "mp4"))
                path.write_bytes(b"video")
                return str(path)

        updates = []
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            sys.modules, {"yt_dlp": SimpleNamespace(YoutubeDL=FakeYoutubeDL)}
        ):
            download_video(
                "https://youtu.be/abc", Path(directory),
                progress_callback=lambda value, text: updates.append((value, text)),
            )
        values = [value for value, _ in updates]
        self.assertEqual(values, [0.5, 0.75, 0.99, 1.0])
        self.assertTrue(all(value < 1.0 for value in values[:-1]))

    @patch("xsubtitle.core.resolve_media_pair", return_value=None)
    def test_download_reports_unknown_total_and_fragment_description(self, _media_pair):
        class FakeYoutubeDL:
            def __init__(self, options):
                self.options = options

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def extract_info(self, _url, download):
                hook = self.options["progress_hooks"][0]
                hook({"status": "downloading", "downloaded_bytes": 1_048_576})
                hook({"status": "downloading", "downloaded_bytes": 2_097_152,
                      "fragment_index": 2, "fragment_count": 8})
                return {"id": "1"}

            def prepare_filename(self, _info):
                path = Path(self.options["outtmpl"].replace("%(ext)s", "mp4"))
                path.write_bytes(b"video")
                return str(path)

        updates = []
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            sys.modules, {"yt_dlp": SimpleNamespace(YoutubeDL=FakeYoutubeDL)}
        ):
            download_video(
                "https://youtu.be/abc", Path(directory),
                progress_callback=lambda value, text: updates.append((value, text)),
            )
        self.assertEqual([value for value, _ in updates], [0.0, 0.125, 1.0])
        self.assertIn("1.0 MB", updates[0][1])
        self.assertIn("2/8", updates[1][1])

    def test_progress_callback_exceptions_do_not_abort_job(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            upload = root / "input.mp4"
            upload.write_bytes(b"video")
            cues = [SubtitleCue(0, 1, "Hello")]
            with (
                patch("xsubtitle.core.transcribe_video", return_value=cues),
                patch("xsubtitle.core.get_argos_translator", return_value=lambda text: text),
            ):
                result = process_job(
                    None, upload, False, output_root=root / "outputs",
                    progress_callback=lambda _value, _text: (_ for _ in ()).throw(RuntimeError("UI closed")),
                )
            self.assertTrue(result.korean_srt.is_file())

    def test_process_job_progress_is_monotonic_and_completes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            upload = root / "input.mp4"
            upload.write_bytes(b"video")
            updates = []

            def fake_transcribe(_video, _model, progress_callback):
                progress_callback(0.8, "transcribing")
                progress_callback(0.2, "late update")
                return [SubtitleCue(0, 1, "Hello")]

            with (
                patch("xsubtitle.core.transcribe_video", side_effect=fake_transcribe),
                patch("xsubtitle.core.get_argos_translator", return_value=lambda text: text),
            ):
                process_job(
                    None, upload, False, output_root=root / "outputs",
                    progress_callback=lambda value, text: updates.append((value, text)),
                )

        values = [value for value, _ in updates]
        self.assertEqual(values, sorted(values))
        self.assertEqual(values[-1], 1.0)

    def test_ffmpeg_command_is_argument_list(self):
        with tempfile.TemporaryDirectory() as directory, patch(
            "xsubtitle.core.resolve_media_executable", return_value=Path("C:/test-bin/ffmpeg.exe")
        ):
            root = Path(directory)
            command = ffmpeg_burn_command(root / "input.mp4", root / "ko.srt", root / "out.mp4")
        self.assertEqual(Path(command[0]).name, "ffmpeg.exe")
        self.assertTrue(command[-1].endswith("out.mp4"))
        self.assertIn("subtitles=", command[5])

    def test_atempo_and_timeline_commands(self):
        self.assertEqual(atempo_filters(4.5), ["atempo=2", "atempo=2", "atempo=1.125"])
        cues = [SubtitleCue(1.25, 3.25, "안녕하세요")]
        with patch("xsubtitle.core.resolve_media_executable", return_value=Path("C:/test-bin/ffmpeg.exe")):
            command = ffmpeg_timeline_command([Path("cue.mp3")], cues, [4.0], Path("track.wav"))
        filters = command[command.index("-filter_complex") + 1]
        self.assertIn("atempo=2", filters)
        self.assertIn("adelay=1250:all=1", filters)
        self.assertIn("apad=whole_dur=2.000", filters)
        self.assertNotIn("shell", command)

    def test_mux_commands_support_replace_and_mix(self):
        with patch("xsubtitle.core.resolve_media_executable", return_value=Path("C:/test-bin/ffmpeg.exe")):
            replace = ffmpeg_mux_command(Path("video.mp4"), Path("dub.wav"), Path("out.mp4"), "replace")
            mix = ffmpeg_mux_command(Path("video.mp4"), Path("dub.wav"), Path("out.mp4"), "mix")
        self.assertIn("[1:a]apad[dub]", replace)
        self.assertIn("volume=0.2", mix[mix.index("-filter_complex") + 1])

    def test_process_job_requires_exactly_one_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(UserFacingError):
                process_job("", None, False, output_root=root)
            upload = root / "video.mp4"
            upload.write_bytes(b"video")
            with self.assertRaises(UserFacingError):
                process_job("https://x.com/u/status/1", upload, False, output_root=root)

    def test_process_uploaded_video_writes_utf8_subtitles_and_burns(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            upload = root / "input video.mp4"
            upload.write_bytes(b"video")
            cues = [SubtitleCue(0, 1.25, "Hello")]

            def fake_burn(video, subtitles, output):
                self.assertTrue(video.is_file())
                self.assertTrue(subtitles.is_file())
                output.write_bytes(b"rendered")

            with (
                patch("xsubtitle.core.transcribe_video", return_value=cues) as transcribe,
                patch("xsubtitle.core.get_argos_translator", return_value=lambda text: "안녕하세요"),
                patch("xsubtitle.core.burn_subtitles", side_effect=fake_burn) as burn,
            ):
                result = process_job(None, upload, True, output_root=root / "outputs")

            self.assertEqual(result.english_srt.read_text(encoding="utf-8").splitlines()[-1], "Hello")
            self.assertEqual(result.korean_srt.read_text(encoding="utf-8").splitlines()[-1], "안녕하세요")
            self.assertEqual(result.subtitled_video.read_bytes(), b"rendered")
            self.assertTrue((result.english_srt.parent / "source.mp4").is_file())
            transcribe.assert_called_once()
            burn.assert_called_once()

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
                process_job(None, upload, False, output_root=output_root)
            self.assertEqual(list(output_root.iterdir()), [])

    def test_process_job_creates_dubbed_video_from_subtitled_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            upload = root / "input.mp4"
            upload.write_bytes(b"video")
            cues = [SubtitleCue(0, 1, "Hello")]

            def fake_burn(video, subtitles, output):
                output.write_bytes(b"subtitled")

            def fake_dub(video, translated, job_dir, voice, audio_mode, output):
                self.assertEqual(video.read_bytes(), b"subtitled")
                self.assertEqual(translated[0].text, "안녕하세요")
                self.assertEqual(audio_mode, "mix")
                output.write_bytes(b"dubbed")

            with (
                patch("xsubtitle.core.transcribe_video", return_value=cues),
                patch("xsubtitle.core.get_argos_translator", return_value=lambda text: "안녕하세요"),
                patch("xsubtitle.core.burn_subtitles", side_effect=fake_burn),
                patch("xsubtitle.core.create_dubbed_video", side_effect=fake_dub) as dub,
            ):
                result = process_job(None, upload, True, output_root=root / "outputs", dubbing=True, audio_mode="mix")
            self.assertEqual(result.dubbed_video.read_bytes(), b"dubbed")
            dub.assert_called_once()

    def test_dubbing_falls_back_for_silent_video_and_removes_intermediates(self):
        class FakeCommunicate:
            def __init__(self, text, voice):
                self.text = text

            async def save(self, path):
                Path(path).write_bytes(b"mp3")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / "silent.mp4"
            video.write_bytes(b"video")
            output = root / "dubbed.mp4"
            commands = []

            def fake_ffmpeg(command, action):
                commands.append(list(command))
                Path(command[-1]).write_bytes(b"generated")

            with (
                patch.dict(sys.modules, {"edge_tts": SimpleNamespace(Communicate=FakeCommunicate)}),
                patch("xsubtitle.core.probe_audio_duration", return_value=1.0),
                patch("xsubtitle.core.video_has_audio", return_value=False),
                patch("xsubtitle.core._run_ffmpeg", side_effect=fake_ffmpeg),
                patch("xsubtitle.core.resolve_media_executable", return_value=Path("C:/test-bin/ffmpeg.exe")),
            ):
                create_dubbed_video(
                    video, [SubtitleCue(0, 1, "안녕하세요")], root,
                    "ko-KR-SunHiNeural", "mix", output,
                )

            self.assertTrue(output.is_file())
            self.assertIn("[1:a]apad[dub]", commands[-1])
            self.assertFalse((root / "dub-0001.mp3").exists())
            self.assertFalse((root / "dubbed-audio.wav").exists())


if __name__ == "__main__":
    unittest.main()
