# 말옮김 Web

Windows용 `sns-video-korean-localizer` 스킬 ZIP을 배포하고 설치 방법을 안내하는 Next.js 사이트입니다. 영상 처리는 사용자의 로컬 PC에서 실행되며, 더빙을 선택할 때만 번역된 문장이 Edge TTS로 전송됩니다. 입력은 지원되는 공개 SNS 영상 URL만 받습니다.

```bash
npm install
npm run dev
npm run build
```

Vercel에서 저장소를 연결할 때 **Root Directory**를 `web`으로 지정합니다. 다운로드 CTA는 GitHub Release `v0.1.0`의 `sns-video-korean-localizer-windows.zip` 자산을 사용하고, 소스 링크는 공개 GitHub 저장소로 연결됩니다.
