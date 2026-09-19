# 모바일 한국어 자막 영상 변환기

휴대폰에서 외국어 영상을 올리면 음성을 인식하고 한국어로 번역·자동 검수한 뒤, 읽기 좋은 자막을 입힌 MP4와 SRT를 내려받을 수 있는 개인용 서버입니다.

## 처리 방식

- `faster-whisper small` CPU INT8로 외국어 음성과 언어를 자동 인식합니다.
- Gemini가 여러 자막을 문맥 단위로 번역하고, 별도의 두 번째 요청에서 오역·누락·용어 불일치를 자동 검수합니다.
- FFmpeg가 굵은 검정 글자와 따뜻한 노란색 배경으로 한국어 자막을 영상에 입힙니다.
- 영상 파일은 노트북 안에서 처리합니다. 음성에서 추출한 자막 텍스트만 Gemini API로 전송합니다.
- 작업은 한 번에 하나만 처리합니다.

## 준비

Google AI Studio에서 Gemini API 키를 만든 뒤 저장소를 내려받습니다. API 키를 채팅이나 Git에 올리지 마세요.

```bash
git clone https://github.com/wing0828/sns-video-korean-localizer.git
cd sns-video-korean-localizer
cp .env.example .env
nano .env
```

`.env`의 다음 값만 실제 키로 바꿉니다.

```dotenv
GEMINI_API_KEY=여기에_본인의_API_키
```

## Docker 실행

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f subtitle-app
```

처음 실행할 때 Whisper 모델을 내려받습니다. 모델은 Docker 볼륨에 보존되어 이후 실행에서 재사용됩니다.

노트북 브라우저에서는 `http://127.0.0.1:7860`으로 접속합니다.

## 휴대폰에서 접속

Windows와 휴대폰에 Tailscale을 설치하고 같은 계정으로 로그인한 뒤, Windows PowerShell에서 다음 명령을 실행합니다.

```powershell
tailscale serve --bg http://127.0.0.1:7860
tailscale serve status
```

출력된 `https://...ts.net` 주소를 휴대폰에서 열면 됩니다. 공용 인터넷에는 공개되지 않으며 같은 Tailscale 네트워크의 기기만 접근할 수 있습니다.

## 운영 제한

- 지원 형식: MP4, MOV, MKV, WEBM, AVI, M4V
- 최대 업로드: 500MB
- 기본 모델: `small`
- WSL 메모리 제한을 고려한 컨테이너 메모리: 3GB
- CPU 사용 제한: 2코어

완료된 파일은 Docker의 `subtitle-outputs` 볼륨에 저장되며 웹 화면에서 내려받을 수 있습니다. 저장 공간이 부족해지면 오래된 작업을 지운 뒤 다음 명령으로 사용하지 않는 Docker 데이터를 정리할 수 있습니다.

```bash
docker system df
docker image prune
```

## 중지와 업데이트

```bash
docker compose down
git pull
docker compose up -d --build
```

`docker compose down`은 결과와 Whisper 모델 볼륨을 지우지 않습니다. 볼륨까지 지우는 `docker compose down -v`는 저장된 결과와 모델을 모두 삭제하므로 사용하지 마세요.

## 라이선스

MIT 라이선스입니다. 자세한 내용은 [LICENSE](LICENSE)를 확인하세요.
