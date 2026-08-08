# 말옮김 Web

Windows용 `sns-video-korean-localizer` 스킬 ZIP을 배포하고 설치 방법을 안내하는 Next.js 사이트입니다. 영상 처리는 사용자의 로컬 PC에서 실행되며, 더빙을 선택할 때만 번역된 문장이 Edge TTS로 전송됩니다. 입력은 지원되는 공개 SNS 영상 URL만 받습니다.

```bash
npm install
npm run dev
npm run build
```

Vercel에서 저장소를 연결할 때 **Root Directory**를 `web`으로 지정합니다. 다운로드 파일은 다음 경로에 있어야 합니다.

`public/downloads/sns-video-korean-localizer-windows.zip`

사이트의 다운로드 링크는 `/downloads/sns-video-korean-localizer-windows.zip`을 사용합니다.
