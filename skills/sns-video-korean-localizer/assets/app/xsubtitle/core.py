from __future__ import annotations

import asyncio
import os
import re
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence
from urllib.parse import parse_qs, urlparse


PLATFORM_HOSTS = {
    "X/Twitter": {"x.com", "www.x.com", "mobile.x.com", "twitter.com", "www.twitter.com", "mobile.twitter.com"},
    "YouTube": {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"},
    "TikTok": {"tiktok.com", "www.tiktok.com", "m.tiktok.com", "vm.tiktok.com", "vt.tiktok.com"},
    "Instagram": {"instagram.com", "www.instagram.com"},
    "Facebook": {"facebook.com", "www.facebook.com", "m.facebook.com", "fb.watch"},
    "Reddit": {"reddit.com", "www.reddit.com", "old.reddit.com", "redd.it", "www.redd.it"},
    "Vimeo": {"vimeo.com", "www.vimeo.com", "player.vimeo.com"},
    "Twitch": {"twitch.tv", "www.twitch.tv", "m.twitch.tv", "clips.twitch.tv"},
    "Threads": {"threads.net", "www.threads.net", "threads.com", "www.threads.com"},
}
ALLOWED_X_HOSTS = PLATFORM_HOSTS["X/Twitter"]
SUPPORTED_BROWSER_COOKIES = {"none", "edge", "chrome", "firefox"}
ProgressCallback = Callable[[float, str], None]


def _emit_progress(
    progress_callback: ProgressCallback | None, value: float, description: str
) -> None:
    """Report progress without allowing presentation failures to abort a job."""
    if not progress_callback:
        return
    try:
        progress_callback(value, description)
    except Exception:
        pass


class UserFacingError(RuntimeError):
    """An error safe to display in the web UI."""


@dataclass(frozen=True)
class SubtitleCue:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class JobResult:
    job_id: str
    english_srt: Path
    korean_srt: Path
    subtitled_video: Path | None
    dubbed_video: Path | None


KOREAN_VOICES = {
    "female": "ko-KR-SunHiNeural",
    "male": "ko-KR-InJoonNeural",
}

# Mobile-first subtitle styling. ASS colors use AABBGGRR ordering.
SUBTITLE_FORCE_STYLE = (
    "FontName=Noto Sans CJK KR,FontSize=20,Bold=-1,"
    "PrimaryColour=&H00151515,OutlineColour=&H004DD8FF,"
    "BackColour=&H004DD8FF,BorderStyle=3,Outline=4,Shadow=0,"
    "Alignment=2,MarginL=24,MarginR=24,MarginV=26"
)


def _winget_media_pairs() -> list[tuple[tuple[int, ...], Path, Path]]:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        return []
    packages = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
    pairs = []
    for ffmpeg in packages.glob("Gyan.FFmpeg*/**/bin/ffmpeg.exe"):
        ffprobe = ffmpeg.with_name("ffprobe.exe")
        if not ffprobe.is_file():
            continue
        match = re.search(r"ffmpeg-(\d+(?:\.\d+)*)", str(ffmpeg), re.IGNORECASE)
        version = tuple(map(int, match.group(1).split("."))) if match else ()
        pairs.append((version, ffmpeg.resolve(), ffprobe.resolve()))
    return sorted(pairs, key=lambda item: (item[0], str(item[1]).casefold()), reverse=True)


def resolve_media_pair() -> tuple[Path, Path] | None:
    """Resolve a compatible pair; split PATH tools are not treated as a pair."""
    path_ffmpeg, path_ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if path_ffmpeg and path_ffprobe:
        ffmpeg, ffprobe = Path(path_ffmpeg).resolve(), Path(path_ffprobe).resolve()
        if ffmpeg.parent == ffprobe.parent:
            return ffmpeg, ffprobe
    pairs = _winget_media_pairs()
    return (pairs[0][1], pairs[0][2]) if pairs else None


def resolve_media_executable(name: str) -> Path:
    """Resolve one executable from PATH or a compatible WinGet pair."""
    if name not in {"ffmpeg", "ffprobe"}:
        raise ValueError("Only ffmpeg and ffprobe are supported")
    executable = shutil.which(name)
    if executable:
        return Path(executable).resolve()
    pair = resolve_media_pair()
    if pair:
        return pair[0 if name == "ffmpeg" else 1]
    raise FileNotFoundError(f"{name} executable was not found")


def detect_platform(value: str) -> str | None:
    parsed = urlparse(value.strip())
    host = (parsed.hostname or "").lower().rstrip(".")
    return next((platform for platform, hosts in PLATFORM_HOSTS.items() if host in hosts), None)


def _is_canonical_media_path(platform: str, host: str, path: str, query: str) -> bool:
    params = parse_qs(query)
    rules = {
        "X/Twitter": bool(re.fullmatch(r"/[^/]+/status/\d+(?:/(?:video|photo)/\d+)?/?", path)),
        "YouTube": (
            (host == "youtu.be" and bool(re.fullmatch(r"/[A-Za-z0-9_-]+/?", path)))
            or (path == "/watch" and bool(params.get("v", [""])[0]))
            or bool(re.fullmatch(r"/(?:shorts|live)/[A-Za-z0-9_-]+/?", path))
        ),
        "TikTok": bool(re.fullmatch(r"/@[^/]+/video/\d+/?", path)) or (
            host in {"vm.tiktok.com", "vt.tiktok.com"} and bool(re.fullmatch(r"/[A-Za-z0-9]+/?", path))
        ),
        "Instagram": bool(re.fullmatch(r"/(?:p|reel|reels|tv)/[A-Za-z0-9_-]+/?", path)),
        "Facebook": (
            (host == "fb.watch" and bool(re.fullmatch(r"/[A-Za-z0-9_-]+/?", path)))
            or (path == "/watch/" and bool(params.get("v", [""])[0]))
            or bool(re.fullmatch(r"/(?:reel/\d+|[^/]+/videos/\d+)/?", path))
        ),
        "Reddit": bool(re.fullmatch(r"/r/[^/]+/comments/[A-Za-z0-9]+(?:/[^/]*)?/?", path)) or (
            host in {"redd.it", "www.redd.it"} and bool(re.fullmatch(r"/[A-Za-z0-9]+/?", path))
        ),
        "Vimeo": bool(re.fullmatch(r"/\d+/?", path)) or (
            host == "player.vimeo.com" and bool(re.fullmatch(r"/video/\d+/?", path))
        ),
        "Twitch": bool(re.fullmatch(r"/(?:videos/\d+|[^/]+/clip/[A-Za-z0-9_-]+)/?", path)) or (
            host == "clips.twitch.tv" and bool(re.fullmatch(r"/[A-Za-z0-9_-]+/?", path))
        ),
        "Threads": bool(re.fullmatch(r"/@[^/]+/post/[A-Za-z0-9_-]+/?", path)),
    }
    return rules.get(platform, False)


def validate_video_url(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("지원되는 SNS 영상 URL을 입력해 주세요.")
    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.username or parsed.password:
        raise ValueError("사용자 정보가 없는 올바른 https SNS URL을 입력해 주세요.")
    platform = detect_platform(value)
    if platform is None:
        raise ValueError("지원하지 않는 사이트입니다. X, YouTube, TikTok, Instagram, Facebook, Reddit, Vimeo, Twitch, Threads URL을 사용해 주세요.")
    host = (parsed.hostname or "").lower().rstrip(".")
    if not _is_canonical_media_path(platform, host, parsed.path, parsed.query):
        raise ValueError(f"{platform}의 실제 영상 또는 게시물 주소를 입력해 주세요. 외부 링크 이동 주소는 허용되지 않습니다.")
    return value


def validate_x_url(value: str) -> str:
    """Backward-compatible alias for URL validation."""
    return validate_video_url(value)


def format_srt_timestamp(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def render_srt(cues: Iterable[SubtitleCue]) -> str:
    blocks = []
    for index, cue in enumerate(cues, 1):
        text = re.sub(r"\s+", " ", cue.text).strip()
        blocks.append(
            f"{index}\n{format_srt_timestamp(cue.start)} --> "
            f"{format_srt_timestamp(cue.end)}\n{text}"
        )
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def translate_cues(
    cues: Sequence[SubtitleCue],
    translate_text: Callable[[str], str],
    progress_callback: ProgressCallback | None = None,
) -> list[SubtitleCue]:
    translated = []
    total = len(cues)
    for index, cue in enumerate(cues, 1):
        translated.append(SubtitleCue(cue.start, cue.end, translate_text(cue.text)))
        if total:
            _emit_progress(progress_callback, index / total, f"한국어 번역 중 ({index}/{total})")
    return translated


def _is_browser_cookie_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "cookie" in message and any(
        marker in message
        for marker in ("dpapi", "decrypt", "could not copy", "failed to extract")
    )


def download_video(
    url: str,
    job_dir: Path,
    browser_cookie: str = "none",
    video_quality: str = "fast",
    progress_callback: ProgressCallback | None = None,
) -> Path:
    try:
        import yt_dlp
    except ImportError as exc:
        raise UserFacingError("yt-dlp가 설치되어 있지 않습니다.") from exc

    browser_cookie = (browser_cookie or "none").lower()
    if browser_cookie not in SUPPORTED_BROWSER_COOKIES:
        raise UserFacingError("브라우저 쿠키는 없음, Edge, Chrome, Firefox 중에서 선택해 주세요.")
    quality_formats = {
        "fast": "bestvideo[height<=360]+bestaudio/best[height<=360]/worst[height<=360]",
        "standard": "bestvideo[height<=720]+bestaudio/best[height<=720]/worst[height<=720]",
        "original": "bestvideo*+bestaudio/best",
    }
    if video_quality not in quality_formats:
        raise UserFacingError("영상 화질은 360p, 720p, 원본 중에서 선택해 주세요.")
    platform = detect_platform(url) or "SNS"
    output_template = str(job_dir / "source.%(ext)s")
    options = {
        "format": quality_formats[video_quality],
        "outtmpl": output_template,
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "restrictfilenames": True,
    }
    highest_download_progress = 0.0
    component_progress: dict[str, float] = {}
    component_order: list[str] = []
    expected_streams = 2

    def download_progress(status: dict) -> None:
        nonlocal highest_download_progress
        info = status.get("info_dict") or {}
        format_id = str(info.get("format_id") or status.get("filename") or "download")
        if format_id not in component_order:
            component_order.append(format_id)
        total = status.get("total_bytes") or status.get("total_bytes_estimate")
        downloaded = status.get("downloaded_bytes")
        if status.get("status") == "finished":
            component_progress[format_id] = 1.0
        elif total and downloaded is not None:
            component_progress[format_id] = min(1.0, float(downloaded) / float(total))
        elif status.get("fragment_index") and status.get("fragment_count"):
            component_progress[format_id] = min(
                1.0, float(status["fragment_index"]) / float(status["fragment_count"])
            )
        else:
            component_progress.setdefault(format_id, 0.0)

        completed_slots = sum(component_progress.values())
        weighted = completed_slots / max(expected_streams, len(component_order))
        highest_download_progress = max(highest_download_progress, min(0.99, weighted))
        fragment_index = status.get("fragment_index")
        fragment_count = status.get("fragment_count")
        if fragment_index and fragment_count:
            description = f"영상 다운로드 중 (조각 {fragment_index}/{fragment_count})"
        elif not total and downloaded is not None:
            description = f"영상 다운로드 중 ({float(downloaded) / 1_048_576:.1f} MB)"
        else:
            description = "영상 다운로드 중"
        _emit_progress(progress_callback, highest_download_progress, description)

    options["progress_hooks"] = [download_progress]
    media_pair = resolve_media_pair()
    if media_pair:
        options["ffmpeg_location"] = str(media_pair[0].parent)
    if browser_cookie != "none":
        options["cookiesfrombrowser"] = (browser_cookie,)
    cookie_retry = False
    try:
        try:
            with yt_dlp.YoutubeDL(options) as downloader:
                info = downloader.extract_info(url, download=True)
                highest_download_progress = 1.0
                _emit_progress(progress_callback, 1.0, "영상 다운로드 완료")
                prepared = Path(downloader.prepare_filename(info))
        except Exception as exc:
            if browser_cookie == "none" or not _is_browser_cookie_error(exc):
                raise
            cookie_retry = True
            retry_options = dict(options)
            retry_options.pop("cookiesfrombrowser", None)
            with yt_dlp.YoutubeDL(retry_options) as downloader:
                info = downloader.extract_info(url, download=True)
                highest_download_progress = 1.0
                _emit_progress(progress_callback, 1.0, "영상 다운로드 완료")
                prepared = Path(downloader.prepare_filename(info))
    except Exception as exc:
        if cookie_retry:
            raise UserFacingError(
                f"{platform} 브라우저 쿠키 복호화에 실패하여 쿠키 없이 다시 시도했지만 다운로드하지 못했습니다. "
                f"공개 게시물인지 확인하고, 비공개 게시물이라면 브라우저 로그인을 확인해 주세요. ({exc})"
            ) from exc
        raise UserFacingError(f"{platform} 영상을 다운로드하지 못했습니다. URL, 공개 범위, 로그인 필요 여부를 확인해 주세요. ({exc})") from exc

    candidates = [job_dir / "source.mp4", prepared]
    candidates.extend(job_dir.glob("source.*"))
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise UserFacingError("다운로드된 동영상 파일을 찾지 못했습니다.")


def download_x_video(
    url: str,
    job_dir: Path,
    browser_cookie: str = "none",
    video_quality: str = "fast",
    progress_callback: ProgressCallback | None = None,
) -> Path:
    """Backward-compatible alias for video downloading."""
    return download_video(url, job_dir, browser_cookie, video_quality, progress_callback)


def transcribe_video(
    video_path: Path,
    model_name: str = "small",
    progress_callback: ProgressCallback | None = None,
) -> list[SubtitleCue]:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise UserFacingError("faster-whisper가 설치되어 있지 않습니다.") from exc
    try:
        model = WhisperModel(model_name, device="cpu", compute_type="int8")
        segments, info = model.transcribe(str(video_path), language="en", vad_filter=True)
        duration = float(getattr(info, "duration", 0) or 0)
        cues = []
        for segment in segments:
            text = segment.text.strip()
            if text:
                cues.append(SubtitleCue(float(segment.start), float(segment.end), text))
            if duration > 0:
                _emit_progress(
                    progress_callback,
                    min(1.0, float(segment.end) / duration),
                    "영어 음성 인식 중",
                )
    except Exception as exc:
        raise UserFacingError(f"음성 인식에 실패했습니다: {exc}") from exc
    if not cues:
        raise UserFacingError("영어 음성을 찾지 못했습니다.")
    return cues


def get_argos_translator() -> Callable[[str], str]:
    try:
        import argostranslate.package
        import argostranslate.translate
    except ImportError as exc:
        raise UserFacingError("Argos Translate가 설치되어 있지 않습니다.") from exc

    def find_translation():
        languages = argostranslate.translate.get_installed_languages()
        source = next((lang for lang in languages if lang.code == "en"), None)
        target = next((lang for lang in languages if lang.code == "ko"), None)
        return source.get_translation(target) if source and target else None

    translation = find_translation()
    if translation is None:
        try:
            argostranslate.package.update_package_index()
            package = next(
                (p for p in argostranslate.package.get_available_packages() if p.from_code == "en" and p.to_code == "ko"),
                None,
            )
            if package is None:
                raise UserFacingError("Argos 영어→한국어 번역 패키지를 찾지 못했습니다.")
            argostranslate.package.install_from_path(package.download())
            translation = find_translation()
        except UserFacingError:
            raise
        except Exception as exc:
            raise UserFacingError(f"Argos 번역 패키지 설치에 실패했습니다: {exc}") from exc
    if translation is None:
        raise UserFacingError("Argos 영어→한국어 번역기를 불러오지 못했습니다.")
    return translation.translate


def ffmpeg_burn_command(video: Path, subtitles: Path, output: Path) -> list[str]:
    subtitle_filter_path = str(subtitles.resolve()).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
    return [
        str(resolve_media_executable("ffmpeg")), "-y", "-i", str(video), "-vf",
        f"subtitles='{subtitle_filter_path}':force_style='{SUBTITLE_FORCE_STYLE}'",
        "-c:a", "copy", str(output),
    ]


def burn_subtitles(video: Path, subtitles: Path, output: Path) -> None:
    try:
        subprocess.run(ffmpeg_burn_command(video, subtitles, output), check=True, capture_output=True, text=True, shell=False)
    except FileNotFoundError as exc:
        raise UserFacingError("ffmpeg를 찾지 못했습니다. PATH에 설치한 뒤 다시 시도해 주세요.") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "알 수 없는 ffmpeg 오류").strip().splitlines()[-1]
        raise UserFacingError(f"자막 입히기에 실패했습니다: {detail}") from exc


def atempo_filters(speed: float) -> list[str]:
    if speed <= 0:
        raise ValueError("speed must be positive")
    factors: list[float] = []
    while speed > 2.0:
        factors.append(2.0)
        speed /= 2.0
    while speed < 0.5:
        factors.append(0.5)
        speed /= 0.5
    factors.append(speed)
    return [f"atempo={factor:.6g}" for factor in factors]


def ffmpeg_timeline_command(cue_audio: Sequence[Path], cues: Sequence[SubtitleCue], durations: Sequence[float], output: Path) -> list[str]:
    if not (len(cue_audio) == len(cues) == len(durations)) or not cues:
        raise ValueError("cue audio, cues, and durations must be non-empty and have equal lengths")
    total = max(cue.end for cue in cues)
    command = [str(resolve_media_executable("ffmpeg")), "-y", "-f", "lavfi", "-t", f"{total:.3f}", "-i", "anullsrc=r=24000:cl=mono"]
    for audio in cue_audio:
        command.extend(["-i", str(audio)])
    filters, inputs = [], ["[0:a]"]
    for index, (cue, duration) in enumerate(zip(cues, durations), 1):
        length = max(0.001, cue.end - cue.start)
        chain = atempo_filters(max(0.001, duration) / length)
        chain += [f"apad=whole_dur={length:.3f}", f"atrim=duration={length:.3f}", f"adelay={round(cue.start * 1000)}:all=1"]
        filters.append(f"[{index}:a]{','.join(chain)}[cue{index}]")
        inputs.append(f"[cue{index}]")
    filters.append(f"{''.join(inputs)}amix=inputs={len(inputs)}:duration=longest:normalize=0[out]")
    command += ["-filter_complex", ";".join(filters), "-map", "[out]", "-t", f"{total:.3f}", "-c:a", "pcm_s16le", str(output)]
    return command


def ffmpeg_mux_command(video: Path, narration: Path, output: Path, audio_mode: str) -> list[str]:
    command = [str(resolve_media_executable("ffmpeg")), "-y", "-i", str(video), "-i", str(narration)]
    if audio_mode == "replace":
        return command + [
            "-filter_complex", "[1:a]apad[dub]", "-map", "0:v:0", "-map", "[dub]",
            "-c:v", "copy", "-c:a", "aac", "-shortest", str(output),
        ]
    if audio_mode == "mix":
        return command + ["-filter_complex", "[0:a]volume=0.2[original];[original][1:a]amix=inputs=2:duration=first:normalize=0[mixed]", "-map", "0:v:0", "-map", "[mixed]", "-c:v", "copy", "-c:a", "aac", str(output)]
    raise ValueError("audio_mode must be 'replace' or 'mix'")


def _run_ffmpeg(command: Sequence[str], action: str) -> None:
    try:
        subprocess.run(list(command), check=True, capture_output=True, text=True, shell=False)
    except FileNotFoundError as exc:
        raise UserFacingError("ffmpeg/ffprobe를 찾을 수 없습니다. PATH 설정을 확인해 주세요.") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "알 수 없는 오류").strip().splitlines()[-1]
        raise UserFacingError(f"{action}에 실패했습니다: {detail}") from exc


def probe_audio_duration(path: Path) -> float:
    try:
        command = [str(resolve_media_executable("ffprobe")), "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)]
        result = subprocess.run(command, check=True, capture_output=True, text=True, shell=False)
        return float(result.stdout.strip())
    except (FileNotFoundError, subprocess.CalledProcessError, ValueError) as exc:
        raise UserFacingError("생성된 음성 길이를 확인하지 못했습니다. ffprobe 설치를 확인해 주세요.") from exc


def video_has_audio(path: Path) -> bool:
    try:
        command = [
            str(resolve_media_executable("ffprobe")), "-v", "error", "-select_streams", "a:0",
            "-show_entries", "stream=index", "-of", "csv=p=0", str(path),
        ]
        result = subprocess.run(command, check=True, capture_output=True, text=True, shell=False)
        return bool(result.stdout.strip())
    except FileNotFoundError as exc:
        raise UserFacingError("ffprobe를 찾을 수 없습니다. PATH 설정을 확인해 주세요.") from exc
    except subprocess.CalledProcessError as exc:
        raise UserFacingError("영상의 오디오 스트림을 확인하지 못했습니다.") from exc


def create_dubbed_video(
    video: Path,
    cues: Sequence[SubtitleCue],
    job_dir: Path,
    voice: str,
    audio_mode: str,
    output: Path,
    progress_callback: ProgressCallback | None = None,
) -> None:
    if voice not in KOREAN_VOICES.values():
        raise UserFacingError("지원하지 않는 한국어 음성입니다.")
    try:
        import edge_tts
    except ImportError as exc:
        raise UserFacingError("더빙을 사용하려면 edge-tts를 설치해 주세요.") from exc
    cue_files = [job_dir / f"dub-{index:04d}.mp3" for index in range(1, len(cues) + 1)]

    async def synthesize() -> None:
        for index, (cue, cue_file) in enumerate(zip(cues, cue_files), 1):
            await edge_tts.Communicate(cue.text, voice).save(str(cue_file))
            _emit_progress(
                progress_callback,
                index / len(cues) * 0.75,
                f"더빙 음성 생성 중 ({index}/{len(cues)})",
            )
    narration = job_dir / "dubbed-audio.wav"
    try:
        try:
            asyncio.run(synthesize())
        except Exception as exc:
            raise UserFacingError(f"한국어 음성 생성에 실패했습니다: {exc}") from exc
        _run_ffmpeg(ffmpeg_timeline_command(cue_files, cues, [probe_audio_duration(path) for path in cue_files], narration), "더빙 타이밍 정렬")
        _emit_progress(progress_callback, 0.8, "더빙 음성 타이밍 조정 중")
        effective_mode = "replace" if audio_mode == "mix" and not video_has_audio(video) else audio_mode
        _emit_progress(progress_callback, 0.9, "더빙 영상 합성 중")
        _run_ffmpeg(ffmpeg_mux_command(video, narration, output, effective_mode), "더빙 영상 생성")
        _emit_progress(progress_callback, 1.0, "더빙 영상 완성")
    finally:
        for path in [*cue_files, narration]:
            path.unlink(missing_ok=True)


def process_job(
    url: str | None,
    uploaded_path: str | Path | None,
    burn_in: bool,
    model_name: str = "small",
    output_root: str | Path = "outputs",
    dubbing: bool = False,
    voice: str = KOREAN_VOICES["female"],
    audio_mode: str = "replace",
    browser_cookie: str = "none",
    video_quality: str = "fast",
    progress_callback: ProgressCallback | None = None,
) -> JobResult:
    if bool(url and url.strip()) == bool(uploaded_path):
        raise UserFacingError("SNS URL 또는 업로드 파일 중 하나만 선택해 주세요.")

    job_id = str(uuid.uuid4())
    job_dir = Path(output_root).resolve() / job_id
    job_dir.mkdir(parents=True, exist_ok=False)
    last_progress = 0.0

    def report(value: float, description: str) -> None:
        nonlocal last_progress
        last_progress = max(last_progress, min(1.0, value))
        _emit_progress(progress_callback, last_progress, description)

    def stage(start: float, end: float) -> ProgressCallback:
        return lambda value, description: report(start + (end - start) * value, description)

    try:
        report(0.01, "작업 준비 중")
        if url:
            try:
                safe_url = validate_video_url(url)
            except ValueError as exc:
                raise UserFacingError(str(exc)) from exc
            video = download_video(
                safe_url, job_dir, browser_cookie, video_quality,
                stage(0.02, 0.25) if progress_callback else None,
            )
        else:
            source = Path(uploaded_path).resolve()  # type: ignore[arg-type]
            if not source.is_file():
                raise UserFacingError("업로드한 파일을 찾을 수 없습니다.")
            suffix = source.suffix.lower() or ".mp4"
            video = job_dir / f"source{suffix}"
            shutil.copy2(source, video)

        report(0.27, "영상 준비 완료")
        report(0.29, "음성 인식 모델 준비 중")
        english_cues = transcribe_video(
            video, model_name, stage(0.30, 0.62) if progress_callback else None
        )
        report(0.64, "번역기 준비 중")
        korean_cues = translate_cues(
            english_cues, get_argos_translator(),
            stage(0.65, 0.82) if progress_callback else None,
        )
        english_srt = job_dir / "subtitles.en.srt"
        korean_srt = job_dir / "subtitles.ko.srt"
        english_srt.write_text(render_srt(english_cues), encoding="utf-8")
        korean_srt.write_text(render_srt(korean_cues), encoding="utf-8")
        report(0.84, "한·영 자막 파일 생성 완료")
        subtitled_video = job_dir / "subtitled.mp4" if burn_in else None
        if subtitled_video:
            report(0.86, "영상에 한국어 자막 입히는 중")
            burn_subtitles(video, korean_srt, subtitled_video)
            report(0.91, "자막 영상 생성 완료")
        dubbed_video = job_dir / "dubbed.mp4" if dubbing else None
        if dubbed_video:
            dub_args = (subtitled_video or video, korean_cues, job_dir, voice, audio_mode, dubbed_video)
            if progress_callback:
                create_dubbed_video(
                    *dub_args, progress_callback=stage(0.91 if burn_in else 0.85, 0.99)
                )
            else:
                create_dubbed_video(*dub_args)
        report(1.0, "작업 완료")
        return JobResult(job_id, english_srt, korean_srt, subtitled_video, dubbed_video)
    except UserFacingError:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise UserFacingError(f"작업 처리 중 오류가 발생했습니다: {exc}") from exc
