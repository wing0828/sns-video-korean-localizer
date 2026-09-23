"""Manual integration check: run with --network none after model preparation."""
import os
import time
import resource
import subprocess
from pathlib import Path
from xsubtitle.core import SubtitleCue, translate_cues_locally, process_job

assert not os.environ.get("GEMINI_API_KEY"), "API credentials must not enter the local container"
translated = translate_cues_locally([SubtitleCue(0, 2, "Hello. Thank you for watching.")])
assert any("가" <= c <= "힣" for c in translated[0].text), translated
assert translated[0].start == 0 and translated[0].end == 2
print("LOCAL_TRANSLATION:", translated[0].text, flush=True)
subprocess.run([
    "ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
    "color=c=blue:s=640x360:r=15", "-i", "/test/local-test.wav",
    "-shortest", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac",
    "/tmp/local-test.mp4",
], check=True)
started = time.monotonic()
result = process_job("/tmp/local-test.mp4", os.environ.get("TEST_ASR_MODEL", "small"), "/tmp/local-results")
assert result.subtitled_video.stat().st_size > 1000
assert any("가" <= c <= "힣" for c in result.korean_srt.read_text())
print("OFFLINE_VIDEO_PIPELINE_PASSED", flush=True)
print("SECONDS", round(time.monotonic()-started, 2), "PEAK_RSS_MB", resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024, flush=True)
print(result.korean_srt.read_text(), flush=True)
