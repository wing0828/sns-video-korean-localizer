from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
BUNDLED_APP_ROOT = SKILL_ROOT / "assets" / "app"
REQUIRED_MODULES = ("gradio", "yt_dlp", "faster_whisper", "argostranslate", "edge_tts")


def app_root(value: str | Path) -> Path:
    root = Path(value).resolve()
    required = (root / "app.py", root / "requirements.txt", root / "xsubtitle" / "core.py")
    if not all(path.is_file() for path in required):
        raise argparse.ArgumentTypeError(
            "app root must contain app.py, requirements.txt, and xsubtitle/core.py"
        )
    return root


def find_winget_executable(name: str) -> str | None:
    executable = shutil.which(name)
    if executable:
        return executable
    packages = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    if packages.is_dir():
        return next((str(path) for path in packages.glob(f"*/**/{name}.exe")), None)
    return None


def preflight(root: Path) -> int:
    venv_python = root / ".venv" / "Scripts" / "python.exe"
    modules = {name: False for name in REQUIRED_MODULES}
    if venv_python.is_file():
        probe = subprocess.run(
            [
                str(venv_python),
                "-c",
                "import importlib.util,json; print(json.dumps({n:importlib.util.find_spec(n) is not None for n in "
                + repr(REQUIRED_MODULES)
                + "}))",
            ],
            check=False,
            capture_output=True,
            text=True,
            shell=False,
        )
        if probe.returncode == 0:
            modules = json.loads(probe.stdout)

    tools = {name: find_winget_executable(name) for name in ("ffmpeg", "ffprobe", "deno")}
    missing = []
    if not venv_python.is_file():
        missing.append("Python virtual environment (.venv)")
    missing.extend(name for name, path in tools.items() if not path)
    missing.extend(f"Python package: {name}" for name, installed in modules.items() if not installed)
    checks = {
        "app_root": str(root),
        "venv_python": str(venv_python) if venv_python.is_file() else None,
        **tools,
        "modules": modules,
        "ready": not missing,
        "missing": missing,
        "next_step": None if not missing else f'powershell -NoProfile -ExecutionPolicy Bypass -File "{root / "setup.ps1"}"',
    }
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    return 0 if checks["ready"] else 1


def powershell_script(root: Path, name: str) -> int:
    if os.name != "nt":
        print(f"{name} is intended for Windows PowerShell.", file=sys.stderr)
        return 2
    completed = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(root / name)],
        cwd=root,
        check=False,
        shell=False,
    )
    return completed.returncode


def process(args: argparse.Namespace) -> int:
    sys.path.insert(0, str(args.app_root))
    from xsubtitle.core import KOREAN_VOICES, process_job, validate_video_url

    result = process_job(
        url=validate_video_url(args.url),
        uploaded_path=None,
        burn_in=args.burn_in,
        model_name=args.model,
        output_root=args.app_root / "outputs",
        dubbing=args.dubbing,
        voice=KOREAN_VOICES[args.voice],
        audio_mode=args.audio_mode,
        browser_cookie=args.browser_cookie,
        video_quality=args.quality,
    )
    print(json.dumps({
        "job_id": result.job_id,
        "english_srt": str(result.english_srt),
        "korean_srt": str(result.korean_srt),
        "subtitled_video": str(result.subtitled_video) if result.subtitled_video else None,
        "dubbed_video": str(result.dubbed_video) if result.dubbed_video else None,
    }, ensure_ascii=False, indent=2))
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Set up and run the bundled local SNS Korean video app.")
    commands = result.add_subparsers(dest="command", required=True)
    for name in ("preflight", "setup", "run"):
        command = commands.add_parser(name)
        command.add_argument("--app-root", type=app_root, default=BUNDLED_APP_ROOT)
    run = commands.add_parser("process")
    run.add_argument("--app-root", type=app_root, default=BUNDLED_APP_ROOT)
    run.add_argument("--url", required=True)
    run.add_argument("--burn-in", action="store_true")
    run.add_argument("--dubbing", action="store_true")
    run.add_argument("--voice", choices=("female", "male"), default="female")
    run.add_argument("--audio-mode", choices=("replace", "mix"), default="replace")
    run.add_argument("--browser-cookie", choices=("none", "edge", "chrome", "firefox"), default="none")
    run.add_argument("--quality", choices=("fast", "standard", "original"), default="fast")
    run.add_argument("--model", choices=("tiny", "base", "small", "medium"), default="small")
    return result


def main() -> int:
    args = parser().parse_args()
    if args.command == "preflight":
        return preflight(args.app_root)
    if args.command == "setup":
        return powershell_script(args.app_root, "setup.ps1")
    if args.command == "run":
        return powershell_script(args.app_root, "run.ps1")
    return process(args)


if __name__ == "__main__":
    raise SystemExit(main())
