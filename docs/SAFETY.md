# Safety

TimelineForVideo v1 treats source videos as read-only inputs.

## Source Video Rules

- Do not modify source videos.
- Do not delete source videos.
- Do not copy source videos into item outputs.
- Do not include source videos in ZIP exports.

## Generated Output Rules

Generated artifacts are written only under `outputRoot`.

`items remove` targets known generated files:

- item JSON records
- ffprobe and frame sample raw outputs
- contact sheets
- generated frame sample JPGs
- generated download ZIPs
- generated latest manifest files

It prunes empty generated directories after deleting files. It does not remove
arbitrary files from `outputRoot`.

## Out Of Scope In v1

The v1 rebuild intentionally excludes:

- OCR
- scene detection
- face recognition
- person recognition
- external APIs
- full transcription
- diarization
