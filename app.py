from __future__ import annotations

import gradio as gr

from xsubtitle.core import KOREAN_VOICES, UserFacingError, process_job


PRESETS = {
    "한국어 자막 영상 · 추천": {"burn_in": True, "dubbing": False},
    "한국어 더빙 + 자막 영상": {"burn_in": True, "dubbing": True},
}


def resolve_preset(preset: str) -> tuple[bool, bool]:
    """Translate a beginner-facing preset into core processing flags."""
    try:
        settings = PRESETS[preset]
    except KeyError as exc:
        raise UserFacingError("만들 결과를 선택해 주세요.") from exc
    return settings["burn_in"], settings["dubbing"]


def run_job(
    url: str,
    preset: str,
    model_name: str,
    voice: str,
    audio_mode: str,
    browser_cookie: str,
    video_quality: str,
    progress=gr.Progress(),
):
    try:
        burn_in, dubbing = resolve_preset(preset)
        result = process_job(
            url,
            None,
            burn_in,
            model_name,
            dubbing=dubbing,
            voice=voice,
            audio_mode=audio_mode,
            browser_cookie=browser_cookie,
            video_quality=video_quality,
            progress_callback=lambda value, description: progress(
                value, desc=f"{description} · {value:.0%}"
            ),
        )
    except UserFacingError as exc:
        raise gr.Error(str(exc)) from exc

    return (
        f"완료됐어요. 아래에서 결과를 저장하세요. (작업 번호: {result.job_id})",
        str(result.english_srt),
        str(result.korean_srt),
        str(result.subtitled_video) if result.subtitled_video else None,
        str(result.dubbed_video) if result.dubbed_video else None,
    )


CSS = """
@import url('https://fonts.googleapis.com/css2?family=Gowun+Dodum&family=Nanum+Myeongjo:wght@700;800&display=swap');
:root {
  --paper: #f5f1e8; --ink: #192622; --muted: #60706a;
  --mint: #b9e4d1; --mint-dark: #176b55; --line: #d9d7cc; --white: #fffdf8;
}
.gradio-container { background: var(--paper) !important; color: var(--ink); font-family: 'Gowun Dodum', sans-serif !important; }
.main-shell { max-width: 920px !important; margin: 0 auto; padding: 38px 18px 72px !important; }
.hero { padding: 18px 4px 28px; }
.eyebrow { color: var(--mint-dark); font-size: .82rem; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }
.hero h1 { font-family: 'Nanum Myeongjo', serif; font-size: clamp(2rem, 6vw, 3.5rem); line-height: 1.16; margin: .4rem 0 .8rem; letter-spacing: -.04em; }
.hero p { color: var(--muted); font-size: 1.03rem; max-width: 650px; line-height: 1.7; }
.privacy-note { display: inline-flex; gap: .55rem; align-items: center; margin-top: 1rem; padding: .65rem .9rem; border: 1px solid #a5cdbb; border-radius: 999px; background: #edf8f2; color: #245746; font-size: .9rem; }
.step-card { background: var(--white); border: 1px solid var(--line); border-radius: 22px; padding: clamp(18px, 4vw, 30px); margin-bottom: 16px; box-shadow: 0 10px 35px rgba(25,38,34,.045); }
.step-head { display: flex; align-items: baseline; gap: .75rem; margin-bottom: 8px; }
.step-number { color: var(--mint-dark); font-weight: 800; font-size: .78rem; letter-spacing: .12em; }
.step-head h2 { font-family: 'Nanum Myeongjo', serif; font-size: 1.35rem; margin: 0; }
.helper { color: var(--muted); margin: 0 0 14px; line-height: 1.65; font-size: .94rem; }
.platforms { color: #50615a; font-size: .82rem; margin-top: 8px; }
.preset-radio label { padding: 14px !important; border: 1px solid var(--line) !important; border-radius: 14px !important; background: #fff !important; }
.preset-radio label:has(input:checked) { border-color: var(--mint-dark) !important; background: #edf8f2 !important; box-shadow: inset 0 0 0 1px var(--mint-dark); }
.run-button { min-height: 52px !important; border-radius: 14px !important; background: var(--ink) !important; border: 0 !important; font-size: 1.02rem !important; }
.run-button:hover { background: var(--mint-dark) !important; transform: translateY(-1px); }
.result-status textarea { font-weight: 700 !important; color: var(--mint-dark) !important; }
footer { display: none !important; }
@media (max-width: 640px) {
  .main-shell { padding: 20px 10px 48px !important; }
  .hero { padding-top: 6px; }
  .step-card { border-radius: 17px; padding: 18px 14px; }
  .privacy-note { border-radius: 14px; align-items: flex-start; }
}
"""


with gr.Blocks(title="SNS 영상 한국어 자막·더빙") as demo:
    with gr.Column(elem_classes="main-shell"):
        gr.HTML(
            """
            <header class="hero">
              <div class="eyebrow">LOCAL VIDEO STUDIO</div>
              <h1>영상 주소 하나로<br>한국어 영상 만들기</h1>
              <p>영어 SNS 영상의 주소를 붙여넣으면 한국어 자막 파일과 자막·더빙 영상을 만들어 드려요.</p>
              <div class="privacy-note" role="note"><span aria-hidden="true">⌂</span><span><strong>기본 자막 작업은 내 컴퓨터에서 처리돼요.</strong> 더빙을 선택하면 아래 안내처럼 온라인 음성 서비스를 사용합니다.</span></div>
            </header>
            """
        )

        with gr.Group(elem_classes="step-card"):
            gr.HTML(
                '<div class="step-head"><span class="step-number">STEP 01</span><h2>영상 주소 붙여넣기</h2></div>'
                '<p class="helper">브라우저 주소창에서 영상 또는 게시물 주소를 복사해 넣으세요.</p>'
            )
            url = gr.Textbox(
                label="SNS 영상 URL",
                placeholder="예: https://www.youtube.com/watch?v=...",
                info="영상 파일을 올리는 방식이 아니라, 공개된 영상 주소를 사용합니다.",
            )
            gr.HTML('<div class="platforms">지원: YouTube · X(Twitter) · TikTok · Instagram · Facebook · Reddit · Vimeo · Twitch · Threads</div>')

        with gr.Group(elem_classes="step-card"):
            gr.HTML(
                '<div class="step-head"><span class="step-number">STEP 02</span><h2>만들 결과 선택하기</h2></div>'
                '<p class="helper">처음이라면 추천 설정 그대로 시작하세요. 두 방식 모두 한글·영문 SRT 파일을 함께 만듭니다.</p>'
            )
            preset = gr.Radio(
                choices=list(PRESETS),
                value="한국어 자막 영상 · 추천",
                label="결과 형태",
                elem_classes="preset-radio",
            )
            gr.Markdown(
                "**한국어 자막 영상**은 영상·모델을 내려받은 뒤 내 컴퓨터에서 처리합니다.  "
                "**한국어 더빙 + 자막 영상**은 인터넷 연결이 필요하며, 음성을 만들기 위해 "
                "번역된 자막 문장이 Microsoft Edge TTS로 전송됩니다. 영상 파일 자체는 전송하지 않습니다."
            )

        with gr.Group(elem_classes="step-card"):
            gr.HTML(
                '<div class="step-head"><span class="step-number">STEP 03</span><h2>만들기</h2></div>'
                '<p class="helper">처리 중에는 이 창과 컴퓨터를 켜 두세요. 영상 길이와 PC 성능에 따라 시간이 걸릴 수 있습니다.</p>'
            )
            with gr.Accordion("세부 설정 · 문제가 있을 때만 열기", open=False):
                video_quality = gr.Radio(
                    [("빠르게 · 360p", "fast"), ("선명하게 · 720p", "standard"), ("원본 화질", "original")],
                    value="fast",
                    label="가져올 영상 화질",
                    info="처음에는 360p가 가장 빠르고 안정적입니다.",
                )
                model = gr.Dropdown(
                    [("빠르게", "base"), ("균형 · 추천", "small"), ("더 정확하게", "medium")],
                    value="small",
                    label="음성 인식 정확도",
                )
                with gr.Row():
                    voice = gr.Dropdown(
                        [("여성 목소리", KOREAN_VOICES["female"]), ("남성 목소리", KOREAN_VOICES["male"])],
                        value=KOREAN_VOICES["female"],
                        label="더빙 목소리",
                    )
                    audio_mode = gr.Radio(
                        [("원래 음성 대신 더빙", "replace"), ("원래 소리를 작게 유지", "mix")],
                        value="replace",
                        label="더빙 소리",
                    )
                browser_cookie = gr.Dropdown(
                    [("사용하지 않음", "none"), ("Edge 로그인 사용", "edge"), ("Chrome 로그인 사용", "chrome"), ("Firefox 로그인 사용", "firefox")],
                    value="none",
                    label="로그인이 필요한 내 영상",
                    info="공개 영상은 사용하지 마세요. 접근 권한이 있는 콘텐츠에만 선택하세요.",
                )

            submit = gr.Button("한국어 영상 만들기", variant="primary", elem_classes="run-button")
            gr.Markdown("작업은 이 PC에서 진행됩니다. 첫 실행은 필요한 AI 모델을 내려받아 더 오래 걸릴 수 있어요.")

        with gr.Group(elem_classes="step-card"):
            gr.HTML('<div class="step-head"><span class="step-number">RESULT</span><h2>완성된 파일</h2></div>')
            status = gr.Textbox(label="진행 상태", interactive=False, elem_classes="result-status")
            with gr.Row():
                korean = gr.File(label="한국어 자막 · SRT")
                english = gr.File(label="영어 원문 자막 · SRT")
            with gr.Row():
                subtitled = gr.File(label="한국어 자막 영상 · MP4")
                dubbed = gr.File(label="한국어 더빙 + 자막 영상 · MP4")

        gr.Markdown("권한이 있는 영상만 사용해 주세요. 결과는 `outputs/작업번호/` 폴더에도 보관됩니다.")

    submit.click(
        run_job,
        [url, preset, model, voice, audio_mode, browser_cookie, video_quality],
        [status, english, korean, subtitled, dubbed],
    )


if __name__ == "__main__":
    demo.queue(default_concurrency_limit=1).launch(
        server_name="127.0.0.1", share=False, inbrowser=True, css=CSS
    )
