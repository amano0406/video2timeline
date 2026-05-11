# Third-Party Notices

TimelineForVideo is a local Docker-first worker. This file tracks direct
runtime components and model dependencies added to the Video worker. Verify
upstream license files and model cards before redistributing a built image.

## Direct Worker Components

| Component | Version / source | Role |
|---|---:|---|
| Python | `python:3.12-slim` base image | worker runtime |
| FFmpeg / ffprobe | Debian package | video metadata, frame sampling, audio extraction |
| Tesseract OCR | Debian package | local OCR over generated frame artifacts |
| Pillow | `>=10,<12` | image loading and OCR overlays |
| pytesseract | `>=0.3.10,<0.4` | Python bridge to Tesseract |
| torch | `2.8.0+cpu` | audio model runtime |
| torchaudio | `2.8.0+cpu` | audio loading and resampling |
| pyannote.audio | `4.0.1` | speaker diarization runtime |
| huggingface_hub | `0.36.0` | model download |
| faster-whisper | `>=1.1,<2` | readable speech transcription |
| ctranslate2 | `>=4.5,<5` | faster-whisper runtime |

## Model Dependencies

| Model | Role | Notes |
|---|---|---|
| `pyannote/speaker-diarization-community-1` | speaker diarization | Requires Hugging Face token and upstream access approval. Verify the model card and license before redistribution. |
| `Systran/faster-whisper-large-v3` | speech transcription | Verify the upstream model card and license before redistribution. |

## Product Boundaries

- TimelineForVideo does not import or share TimelineForAudio/Image source code.
- Source videos are not included in export ZIPs.
- Generated MP3 audio derivatives are not included in export ZIPs.
- No external analysis API is called by the default worker pipeline. Hugging
  Face access is used only when audio model execution is enabled and a token is
  configured.
