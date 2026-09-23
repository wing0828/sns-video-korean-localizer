from __future__ import annotations

import os
from pathlib import Path

import gradio as gr

from xsubtitle.core import UserFacingError, download_social_video, process_job


def run_job(uploaded_path: str | None, video_url: str, model_name: str, progress=gr.Progress()):
    downloaded_path = None; source_path = uploaded_path
    if video_url and video_url.strip():
        try: downloaded_path = download_social_video(video_url.strip(), lambda value, description: progress(value, desc=description)); source_path = str(downloaded_path)
        except UserFacingError as exc: raise gr.Error(str(exc)) from exc
    if not source_path: raise gr.Error("영상을 업로드하거나 X/Twitter 게시물 링크를 입력해 주세요.")
    try:
        result = process_job(source_path, model_name, progress_callback=lambda value, description: progress(value, desc=f"{description} · {value:.0%}"))
    except UserFacingError as exc: raise gr.Error(str(exc)) from exc
    finally:
        if downloaded_path is not None:
            downloaded_path.unlink(missing_ok=True)
            try: downloaded_path.parent.rmdir()
            except OSError: pass
    return (f"완료됐어요. 아래에서 결과를 저장하세요. (작업 번호: {result.job_id})", str(result.subtitled_video), str(result.korean_srt))


CSS = """
:root { --paper:#f6f2e9; --ink:#18231f; --muted:#647069; --green:#176b55; --line:#d8d8cf; }
.gradio-container { background:var(--paper)!important; color:var(--ink); }
.main-shell { max-width:760px!important; margin:0 auto; padding:28px 14px 64px!important; }
.hero h1 { font-size:clamp(2rem,8vw,3.4rem); line-height:1.12; letter-spacing:-.05em; margin:.35rem 0 .8rem; }
.hero p { color:var(--muted); line-height:1.7; }
.badge { display:inline-block; color:var(--green); font-size:.8rem; font-weight:800; letter-spacing:.1em; }
.card { background:#fffdf8; border:1px solid var(--line); border-radius:22px; padding:clamp(18px,5vw,30px); margin-top:16px; }
.run-button { min-height:54px!important; border-radius:14px!important; background:var(--ink)!important; }
footer { display:none!important; }
@media(max-width:640px){ .main-shell{padding:18px 10px 44px!important}.card{border-radius:17px;padding:18px 14px} }
"""


with gr.Blocks(title="한국어 자막 영상 만들기") as demo:
    with gr.Column(elem_classes="main-shell"):
        gr.HTML(
            """<header class="hero"><span class="badge">PRIVATE VIDEO TRANSLATOR</span>
            <h1>영상을 올리거나<br>게시물 링크를 넣으면</h1>
            <p>영어 전용 Whisper로 원문을 인식하고 NLLB 번역 모델로 한국어 자막을 만듭니다. API 요금 없이 이 노트북에서 처리합니다.</p></header>"""
        )
        with gr.Group(elem_classes="card"):
            video = gr.File(label="영상 선택", file_types=["video"], type="filepath")
            video_url = gr.Textbox(label="X/Twitter 게시물 링크 (선택)", placeholder="https://x.com/.../status/...", info="영상이 포함된 공개 게시물만 지원합니다.")
            model = gr.Radio(
                [("품질 우선 · 영어 small.en · 추천", "small"), ("더 빠르게 · 영어 base.en", "base")],
                value="small",
                label="음성 인식",
            )
            submit = gr.Button("한국어 자막 영상 만들기", variant="primary", elem_classes="run-button")
            gr.Markdown("로컬 무료 모드 · 영상과 자막은 이 노트북에서 처리됩니다. Gemini API를 호출하지 않습니다.")
        with gr.Group(elem_classes="card"):
            status = gr.Textbox(label="진행 상태", interactive=False)
            subtitled = gr.File(label="한국어 자막 영상 · MP4")
            korean = gr.File(label="한국어 자막 · SRT")
        gr.Markdown("처음 실행할 때 음성 인식 모델을 내려받으므로 시간이 더 걸릴 수 있습니다.")

    submit.click(run_job, [video, video_url, model], [status, subtitled, korean])


if __name__ == "__main__":
    Path("outputs").mkdir(exist_ok=True)
    demo.queue(default_concurrency_limit=1).launch(
        server_name="0.0.0.0",
        server_port=int(os.environ.get("PORT", "7860")),
        share=False,
        css=CSS,
        max_file_size="500mb",
    )
