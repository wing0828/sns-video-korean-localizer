# Local subtitle server

This deployment uses English-only Whisper `small.en` (default) or `base.en`,
with language=en, transcribe, beam_size=5. It releases ASR weights before
loading NLLB-200 distilled 600M INT8 for English-to-Korean translation on CPU.
Source SRT preserves recognized English. There is no Gemini review pass.
Translation quality may be lower than the Gemini version.

Compose intentionally does not load `.env` or pass API credentials. The retained
legacy Gemini function is not part of the job pipeline. Model downloads require
Internet access during setup/first use; inference runs locally without API fees.
Electricity and Internet access are still required to operate the remote server.

Current translation model: https://huggingface.co/mijuanlo/nllb-200-distilled-600M-ct2-int8
Original model: https://huggingface.co/facebook/nllb-200-distilled-600M
License: CC-BY-NC-4.0 (personal noncommercial use).
Download with huggingface_hub.snapshot_download into /data/models/nllb-600m
in the existing whisper-models volume. Needed files: model.bin, config.json,
shared_vocabulary.json and sentencepiece.bpe.model (retain model metadata).
Do not execute downloaded Python code. Compose sets LOCAL_TRANSLATION_MODEL
to this volume path. ASR model caches are in the same persistent volume.

Legacy fallback model source: https://argos-net.com/v1/translate-en_ko-1_1.argosmodel
Official index: https://github.com/argosopentech/argospm-index
Extract the archive to `local-models/`, preserving `en_ko/model/` and
`en_ko/sentencepiece.model`. Model attribution is included in the archive.
The legacy model is included in the Docker image, not committed to Git.

Validation on this laptop: 5 sample sentences took about 10 seconds versus
1.5 seconds with the legacy translator (before sentence splitting). A roughly
7-second synthetic English video completed offline with small.en and NLLB
in 29.64 seconds, peak process RSS 1203 MiB under a 3 GiB container limit.
These small tests are not a general translation-quality or speed benchmark.

Run `docker compose up -d --build --wait` after changes. Existing output and
Whisper model volumes remain in use. Do not use `down -v` to update this server.

These deployment edits are local and uncommitted. Review incoming Git updates
before pulling: upstream still uses Gemini and could conflict with this mode.
