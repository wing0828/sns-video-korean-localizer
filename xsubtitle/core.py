from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence


ProgressCallback = Callable[[float, str], None]
SUPPORTED_VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
MAX_UPLOAD_BYTES = 500 * 1024 * 1024

# ASS colors use AABBGGRR ordering. The yellow box is intentionally opaque.
SUBTITLE_FORCE_STYLE = (
    "FontName=Noto Sans CJK KR,FontSize=12,Bold=-1,"
    "PrimaryColour=&H00151515,OutlineColour=&H004DD8FF,"
    "BackColour=&H004DD8FF,BorderStyle=3,Outline=4,Shadow=0,"
    "Alignment=2,MarginL=24,MarginR=24,MarginV=20"
)


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
    source_srt: Path
    korean_srt: Path
    subtitled_video: Path


def _emit_progress(
    progress_callback: ProgressCallback | None, value: float, description: str
) -> None:
    if not progress_callback:
        return
    try:
        progress_callback(value, description)
    except Exception:
        # Closing a browser tab must not abort a long-running conversion.
        pass


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
        model = WhisperModel(
            model_name,
            device="cpu",
            compute_type="int8",
            cpu_threads=int(os.environ.get("WHISPER_CPU_THREADS", "3")),
        )
        segments, info = model.transcribe(
            str(video_path), vad_filter=True, beam_size=3
        )
        duration = float(getattr(info, "duration", 0) or 0)
        cues = []
        for segment in segments:
            text = segment.text.strip()
            if text:
                cues.append(SubtitleCue(float(segment.start), float(segment.end), text))
            if duration:
                _emit_progress(
                    progress_callback,
                    min(1.0, float(segment.end) / duration),
                    "외국어 음성 인식 중",
                )
    except Exception as exc:
        raise UserFacingError(f"음성 인식에 실패했습니다: {exc}") from exc
    if not cues:
        raise UserFacingError("영상에서 음성을 찾지 못했습니다.")
    return cues


def translate_cues_with_gemini(
    cues: Sequence[SubtitleCue],
    progress_callback: ProgressCallback | None = None,
) -> list[SubtitleCue]:
    """Translate subtitle batches to Korean and run an automatic correction pass."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise UserFacingError("GEMINI_API_KEY가 설정되어 있지 않습니다.")
    try:
        from google import genai
        from google.genai import types
        from pydantic import BaseModel, Field
    except ImportError as exc:
        raise UserFacingError("Gemini 번역 라이브러리가 설치되어 있지 않습니다.") from exc

    class TranslationItem(BaseModel):
        index: int = Field(description="입력 자막의 index")
        text: str = Field(description="자연스럽고 간결한 한국어 자막")

    client = genai.Client(api_key=api_key)
    model = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
    batch_size = max(1, int(os.environ.get("GEMINI_BATCH_SIZE", "40")))
    translated: list[SubtitleCue] = []
    total_batches = max(1, (len(cues) + batch_size - 1) // batch_size)

    def generate(prompt: str) -> list[TranslationItem]:
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=list[TranslationItem],
                    ),
                )
                return [TranslationItem.model_validate(item) for item in response.parsed]
            except Exception as exc:
                if attempt == 2:
                    raise UserFacingError(f"Gemini 번역 요청에 실패했습니다: {exc}") from exc
                time.sleep(2**attempt)
        raise AssertionError("unreachable")

    def validate(items: Sequence[TranslationItem], expected: Sequence[int]) -> dict[int, str]:
        values = {item.index: re.sub(r"\s+", " ", item.text).strip() for item in items}
        if len(items) != len(expected) or set(values) != set(expected) or any(not text for text in values.values()):
            raise UserFacingError("Gemini가 일부 자막을 누락했습니다. 다시 실행해 주세요.")
        return values

    for batch_number, start in enumerate(range(0, len(cues), batch_size), 1):
        batch = cues[start : start + batch_size]
        indexed = [
            {"index": start + offset, "text": cue.text}
            for offset, cue in enumerate(batch)
        ]
        expected = [item["index"] for item in indexed]
        first = validate(
            generate(
                "다음은 한 영상에서 시간 순서대로 추출한 외국어 자막이다. 전체 문맥, 화자의 의도, "
                "대명사, 고유명사와 전문용어를 일관되게 유지해 자연스러운 한국어 자막으로 번역하라. "
                "말투와 감정을 보존하되 직역투를 피하고, 화면에서 빨리 읽을 수 있도록 간결하게 작성하라. "
                "index는 절대 변경하거나 누락하지 마라.\n\n입력:\n"
                + json.dumps(indexed, ensure_ascii=False)
            ),
            expected,
        )
        review_input = [
            {"index": item["index"], "source": item["text"], "korean": first[item["index"]]}
            for item in indexed
        ]
        reviewed = validate(
            generate(
                "한국어 영상 자막 편집자로서 아래 번역을 자동 검수하고 최종본을 반환하라. "
                "오역, 누락, 문맥 불일치, 고유명사 불일치, 어색한 말투를 고친다. 의미를 추가하지 말고, "
                "자막 길이는 가능한 한 짧게 유지한다. 문제가 없으면 기존 번역을 유지한다. "
                "index는 절대 변경하거나 누락하지 마라.\n\n검수 대상:\n"
                + json.dumps(review_input, ensure_ascii=False)
            ),
            expected,
        )
        translated.extend(
            SubtitleCue(cue.start, cue.end, reviewed[start + offset])
            for offset, cue in enumerate(batch)
        )
        _emit_progress(
            progress_callback,
            batch_number / total_batches,
            f"Gemini 번역·자동 검수 중 ({batch_number}/{total_batches})",
        )
    return translated


def ffmpeg_burn_command(video: Path, subtitles: Path, output: Path) -> list[str]:
    executable = shutil.which("ffmpeg")
    if not executable:
        raise UserFacingError("ffmpeg를 찾지 못했습니다.")
    subtitle_path = str(subtitles.resolve()).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
    video_filter = (
        "scale=w='min(1280,iw)':h='min(720,ih)':"
        "force_original_aspect_ratio=decrease:force_divisible_by=2,"
        f"subtitles='{subtitle_path}':force_style='{SUBTITLE_FORCE_STYLE}'"
    )
    return [
        executable,
        "-y",
        "-i",
        str(video),
        "-vf",
        video_filter,
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
        str(output),
    ]


def burn_subtitles(video: Path, subtitles: Path, output: Path) -> None:
    try:
        subprocess.run(
            ffmpeg_burn_command(video, subtitles, output),
            check=True,
            capture_output=True,
            text=True,
            shell=False,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "알 수 없는 ffmpeg 오류").strip().splitlines()[-1]
        raise UserFacingError(f"자막 입히기에 실패했습니다: {detail}") from exc


def process_job(
    uploaded_path: str | Path,
    model_name: str = "small",
    output_root: str | Path = "outputs",
    progress_callback: ProgressCallback | None = None,
) -> JobResult:
    source = Path(uploaded_path).resolve()
    if not source.is_file():
        raise UserFacingError("업로드한 파일을 찾을 수 없습니다.")
    if source.stat().st_size > MAX_UPLOAD_BYTES:
        raise UserFacingError("영상은 500MB 이하만 올릴 수 있습니다.")
    if source.suffix.lower() not in SUPPORTED_VIDEO_SUFFIXES:
        raise UserFacingError("지원하는 영상 형식은 MP4, MOV, MKV, WEBM, AVI, M4V입니다.")
    if model_name not in {"base", "small"}:
        raise UserFacingError("음성 인식 모델은 base 또는 small만 사용할 수 있습니다.")

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
        report(0.01, "영상 준비 중")
        video = job_dir / f"source{source.suffix.lower()}"
        shutil.copy2(source, video)
        cues = transcribe_video(video, model_name, stage(0.05, 0.60))
        korean_cues = translate_cues_with_gemini(cues, stage(0.62, 0.82))
        source_srt = job_dir / "subtitles.source.srt"
        korean_srt = job_dir / "subtitles.ko.srt"
        source_srt.write_text(render_srt(cues), encoding="utf-8")
        korean_srt.write_text(render_srt(korean_cues), encoding="utf-8")
        report(0.84, "자막 파일 생성 완료")
        subtitled_video = job_dir / "subtitled.mp4"
        burn_subtitles(video, korean_srt, subtitled_video)
        report(1.0, "작업 완료")
        return JobResult(job_id, source_srt, korean_srt, subtitled_video)
    except UserFacingError:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise UserFacingError(f"작업 처리 중 오류가 발생했습니다: {exc}") from exc
