const localhostUrl = "http://127.0.0.1:7860";
const downloadUrl = "https://github.com/wing0828/sns-video-korean-localizer/releases/download/v0.1.0/sns-video-korean-localizer-windows.zip";
const githubUrl = "https://github.com/wing0828/sns-video-korean-localizer";

export function TranslatorFlow() {
  return (
    <main>
      <nav className="nav" aria-label="주요 메뉴">
        <a className="brand" href="#top" aria-label="말옮김 홈"><span>말</span>옮김</a>
        <div className="nav-right"><span className="status"><i aria-hidden="true" /> Windows · 로컬 처리</span><a className="quiet-link" href={githubUrl} target="_blank" rel="noreferrer">GitHub에서 소스 보기 ↗</a><a className="nav-cta" href={downloadUrl}>스킬 다운로드 ↓</a></div>
      </nav>

      <section className="hero" id="top">
        <div className="eyebrow"><span>WINDOWS · LOCAL FIRST</span><em>SNS 영상 번역을 내 컴퓨터에서</em></div>
        <h1>주소만 붙여넣으면,<br/><strong>한국어 영상이 됩니다.</strong></h1>
        <p className="lede">Windows용 스킬을 한 번 설치하고 SNS 영상 URL을 입력하세요.<br className="desktop"/> 한국어 자막과 음성 더빙을 내 컴퓨터에서 완성합니다.</p>
        <div className="hero-actions"><a className="primary download" href={downloadUrl}>Windows 스킬 다운로드 <span aria-hidden="true">↓</span></a><a className="secondary" href={githubUrl} target="_blank" rel="noreferrer">GitHub에서 소스 보기 ↗</a></div>
        <p className="microcopy">ZIP 파일 · Windows 전용 · 영상 파일 업로드 없이 공개 SNS URL로 사용 · <a className="inline-link" href="#install">3단계 설치 보기</a></p>
      </section>

      <section className="promise" aria-label="개인정보 보호 방식">
        <div className="promise-mark" aria-hidden="true">⌂</div><div><b>영상 처리는 로컬에서, 더빙 음성 생성만 Edge TTS로</b><p>영상 다운로드·음성 인식·번역·자막 합성·결과 저장은 사용자 PC에서 진행됩니다. 더빙을 선택하면 음성 생성을 위해 번역된 문장이 인터넷 기반 Edge TTS로 전송됩니다.</p></div><span className="promise-badge">LOCAL PROCESSING</span>
      </section>

      <section className="install" id="install">
        <div className="section-intro"><span className="section-tag">INSTALL IN 3 STEPS</span><h2>다운로드부터 실행까지,<br/>딱 세 단계예요.</h2><p>Codex를 사용하는 Windows PC에서 아래 순서대로 진행하세요. 압축 안에 설치와 실행에 필요한 파일이 함께 들어 있습니다.</p></div>
        <div className="install-card"><ol>
          <li><span>1</span><div><b>ZIP 다운로드</b><p><code>sns-video-korean-localizer-windows.zip</code>을 내려받으세요.</p></div></li>
          <li><span>2</span><div><b>스킬 폴더에 압축 풀기</b><p>압축을 풀어 <code>%USERPROFILE%\.codex\skills\sns-video-korean-localizer</code> 폴더가 되게 하세요.</p></div></li>
          <li><span>3</span><div><b>설치 후 실행</b><p>압축을 푼 폴더에서 <code>setup.ps1</code>을 한 번 실행하고, 이후 <code>run.ps1</code>을 실행하세요.</p></div></li>
        </ol><a className="primary download" href={downloadUrl}>스킬 ZIP 다운로드 <span aria-hidden="true">↓</span></a><p className="launch-note">PowerShell이 실행을 막으면 안내 문서를 확인하세요. AI 모델은 첫 작업 때 내려받습니다.</p></div>
      </section>

      <section className="guide" id="guide">
        <div className="section-intro"><span className="section-tag">AFTER INSTALL</span><h2>실행한 다음은<br/>더 간단해요.</h2><p>로컬 앱에서 세 가지만 진행하면 됩니다.</p></div>
        <ol className="flow-cards">
          <li><span className="flow-no">01</span><div className="flow-visual link-visual"><span>https://youtube.com/...</span><b>↵</b></div><h3>공개 영상 URL 입력</h3><p>X·YouTube 등의 지원되는 공개 게시물 URL을 붙여 넣으세요. 영상 파일 직접 업로드 방식은 지원하지 않습니다.</p></li>
          <li><span className="flow-no">02</span><div className="flow-visual choice-visual"><span><b>字</b> 한국어 자막</span><span><b>◖))</b> 음성 더빙</span></div><h3>원하는 결과 선택</h3><p>원본 음성에 한국어 자막을 더하거나, Edge TTS를 이용한 한국어 음성 더빙을 만들 수 있어요.</p></li>
          <li><span className="flow-no">03</span><div className="flow-visual result-visual"><span>MP4</span><i aria-hidden="true">✓</i></div><h3>결과 저장</h3><p>완성된 MP4와 SRT 자막 파일을 내 컴퓨터에 저장하세요.</p></li>
        </ol>
      </section>

      <section className="decision">
        <div><span className="section-tag">CHOOSE YOUR OUTPUT</span><h2>자막으로 볼까요,<br/>한국어로 들을까요?</h2></div>
        <div className="output-grid"><article><span className="output-icon" aria-hidden="true">字</span><div><h3>한국어 자막</h3><p>원래 목소리와 분위기를 유지하면서 내용을 이해하고 싶을 때.</p><ul><li>원본 음성 유지</li><li>영상에 자막 바로 삽입</li><li>SRT 파일 함께 제공</li></ul></div></article><article><span className="output-icon sound" aria-hidden="true">◖))</span><div><h3>한국어 음성 더빙</h3><p>화면에 집중하며 한국어로 편하게 듣고 싶을 때. 번역 문장은 Edge TTS로 전송됩니다.</p><ul><li>한국어 음성 생성</li><li>원본 소리와 자연스럽게 혼합</li><li>자막도 함께 선택 가능</li></ul></div></article></div>
      </section>

      <section className="final-cta"><span>ALREADY INSTALLED?</span><h2>스킬이 준비됐다면 로컬 앱을 여세요.</h2><a className="secondary local-launch" href={localhostUrl}>설치된 로컬 앱 열기 ↗</a><p>열리지 않으면 스킬 폴더의 <code>run.ps1</code>을 먼저 실행하세요.</p></section>
      <footer><span className="brand small"><span>말</span>옮김</span><span>Windows용 로컬 영상 번역 스킬</span><span className="footer-promise">URL 전용 · 영상 서버 저장 없음 · 더빙 시 Edge TTS 사용</span></footer>
    </main>
  );
}
