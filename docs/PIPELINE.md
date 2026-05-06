# Pipeline

## 1. Configure

`settings save` defines input video roots and `outputRoot`.

## 2. Discover

`files list` scans configured input roots for supported video extensions.

Supported extensions:

```text
.avi .m4v .mkv .mov .mp4 .webm .wmv
```

## 3. Probe

`probe list` runs ffprobe read-only and derives source identity, source
fingerprint, and item id from path/stat metadata.

## 4. Sample

`sample frames` extracts a bounded set of review frames and a contact sheet.
It does not extract all frames.

## 5. Refresh Items

`items refresh` writes:

- `video_record.json`
- `timeline.json`
- `convert_info.json`
- `raw_outputs/ffprobe.json`

It references existing sample artifacts when present.

## 6. Export Or Remove

`items download` creates a generated-artifact ZIP and updates `latest`.
`items remove` deletes only known generated artifacts.
