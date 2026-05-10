# Runtime

The supported runtime path is Docker-first from Windows PowerShell.

```powershell
cd C:\apps\TimelineForVideo
.\start.ps1
.\cli.ps1 health
.\cli.ps1 items refresh --max-items 1
```

The worker image includes Python, ffmpeg/ffprobe, Tesseract OCR, and Japanese +
English OCR language data. The compose service mounts:

- `C:\apps\TimelineForVideo` at `/workspace`
- `C:\` at `/mnt/c`
- `F:\` at `/mnt/f`
- Docker volumes for shared app data and cache

The shared cache volume is used for Hugging Face, Torch, and related model
caches so audio-model downloads can be reused across worker runs.

The Docker service runs `serve` by default. `serve` is the resident worker loop:
it loads `settings.json`, processes changed videos with the same pipeline as
`items refresh`, records run status, then sleeps until the next interval.
The compose default sets `TIMELINE_FOR_VIDEO_WORKER_MAX_ITEMS=1`, so first-run
processing advances one changed item per cycle unless the operator explicitly
raises or clears that environment variable.

## CPU And GPU Compose

GPU is the default worker flavor for TimelineForAudio-compatible audio models.
When `settings.json` has `"computeMode": "gpu"`, `start.ps1` and `cli.ps1` add
`docker-compose.gpu.yml` to the Docker Compose command. The GPU compose layer
uses `docker/worker.gpu.Dockerfile`, requests all available GPUs, and installs
GPU audio-model dependencies. The default CPU compose file remains the base
configuration, but CPU mode must be explicitly selected with
`settings save --compute-mode cpu`.

GPU mode is fail-fast. If the running worker is the CPU flavor, CUDA is not
visible to PyTorch, or ONNX Runtime does not expose `CUDAExecutionProvider`,
audio model processing fails instead of silently using CPU. Frame OCR and frame
visual feature extraction follow TimelineForImage and remain CPU-local
Tesseract/Pillow processing.

## Local Files

- `settings.json`: local runtime configuration, ignored by git.
- `settings.example.json`: committed template.
- `outputRoot`: configured output directory for generated artifacts.
- internal app-data volume: catalog, locks, worker status, and run history.

## Health Check

```powershell
.\cli.ps1 health --json
```

The JSON output reports product, version, Python version, Docker status, and
settings path.

## Run Status

```powershell
.\cli.ps1 runs list
.\cli.ps1 runs show --run-id <RUN_ID>
```

Run metadata is operational state. It is not included in download ZIPs.
For active runs, `status.json` is updated at the current stage (`sample`,
`frame_ocr`, `audio`, `refresh`, or `completed`). Completed runs include
`failedSteps` when a pipeline step did not finish cleanly.
If the worker is stopped mid-run, the next refresh recovers stale lock files and
marks old `running` statuses as `interrupted`.

## OCR And Audio Evidence

Frame OCR uses local Tesseract through `pytesseract`. It does not call an
external image API.

Audio evidence uses local ffmpeg to write a generated MP3 derivative under
`outputRoot`. The generated MP3 is a local review artifact and is excluded from
ZIP exports.

Audio model execution decodes the source-video audio into a temporary
normalized WAV, runs speech candidate detection on that WAV, and then runs the
TimelineForAudio-compatible pyannote/ZIPA model path on the same WAV. The
temporary WAV is removed after the item is processed and is not a master
artifact.
Audio model execution is required by default; the item fails when pyannote/ZIPA
cannot run. Diagnostic commands can still pass `--audio-model-mode auto` or
`--audio-model-mode off` for isolated troubleshooting, but that mode is not a
settings field and is not persisted.

The token can be stored in local `settings.json` with `settings save --token`
or provided through `TIMELINE_FOR_VIDEO_HUGGING_FACE_TOKEN`,
`HUGGING_FACE_HUB_TOKEN`, or `HF_TOKEN`. JSON CLI output redacts the token.

## Current Components

`models list` reports the current execution inventory.

| Component | Current model / backend | Execution |
|---|---|---|
| ffprobe metadata | `ffprobe` | local, read-only |
| Bounded frame sampling | `ffmpeg` | local, generated artifacts only |
| Frame OCR | `tesseract:jpn+eng` | local over generated frame artifacts |
| Frame visual features | Pillow | local over generated frame artifacts |
| Audio derivative | `ffmpeg` MP3 extraction | local generated artifact under `outputRoot` |
| Audio model input | `ffmpeg` normalized WAV extraction | temporary local processing file, removed after processing |
| Speech candidate detection | `ffmpeg` silencedetect | local evidence over normalized WAV |
| Speaker diarization | `pyannote/speaker-diarization-community-1` | GPU by default when `computeMode` is `gpu`; fail-fast if CUDA is unavailable |
| Acoustic units | `anyspeech/zipa-large-crctc-300k` | ONNX `CUDAExecutionProvider` by default when `computeMode` is `gpu`; fail-fast if unavailable |

The Video worker does not import or share TimelineForAudio/Image code. It also
does not silently invent diarization turns or phone-token output when the audio
models cannot run.

Generated frame OCR subpayloads use the same field names as TimelineForImage.
Generated acoustic-unit turns use TimelineForAudio's public `phone_tokens`
field name.
