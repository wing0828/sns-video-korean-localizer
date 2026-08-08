---
name: sns-video-korean-localizer
description: Download an authorized video from a supported SNS URL and locally create English/Korean SRT subtitles, a Korean hard-subtitled MP4, or Korean dubbed MP4. Use for X/Twitter, YouTube, TikTok, Instagram, Facebook, Reddit, Vimeo, Twitch, or Threads requests involving Korean transcription, translation, subtitle burn-in, dubbing, first-time Windows setup, or local app launch.
---

# SNS Video Korean Localizer

Use the self-contained Windows app bundled in `assets/app`. Keep media and model processing local except SNS download, first-time dependency/model retrieval, and Edge TTS dubbing.

## Guardrails

- Process only content the user owns or may download and transform. Warn that redistribution may require separate permission.
- Accept only canonical HTTPS URLs allowed by `xsubtitle.core.validate_video_url`; never bypass its allowlist.
- Never request or copy cookie files. Pass only `none`, `edge`, `chrome`, or `firefox`, and use browser cookies only for authorized content.
- Launch Gradio only on `127.0.0.1` with sharing disabled.

## Set up and check

Run from any directory; the helper locates the bundled app automatically.

```powershell
py -3.12 <skill-dir>\scripts\localize.py preflight
& <skill-dir>\setup.ps1
```

`preflight` prints JSON and returns exit code 1 when setup is needed. `setup` creates only `assets/app/.venv` and installs Python packages there; it uses `winget` for missing Python, FFmpeg, or Deno. First-time setup and model downloads require internet access.

## Run

Launch the guided local UI:

```powershell
& <skill-dir>\run.ps1
```

Open `http://127.0.0.1:7860`, paste one SNS URL, choose the result, and start processing.

For deterministic processing:

```powershell
<skill-dir>\assets\app\.venv\Scripts\python.exe <skill-dir>\scripts\localize.py process --url "https://..." --burn-in
<skill-dir>\assets\app\.venv\Scripts\python.exe <skill-dir>\scripts\localize.py process --url "https://..." --burn-in --dubbing --voice female --audio-mode replace
```

Use `--quality fast|standard|original`, `--model tiny|base|small|medium`, or `--browser-cookie edge|chrome|firefox` only when needed. Dubbing sends translated subtitle text to Edge TTS.

## Report results

Read the JSON output and confirm the requested files exist under `assets/app/outputs/<job-id>/`. Report the absolute paths. Automatic transcription and translation should be reviewed for names, idioms, and technical terms.
