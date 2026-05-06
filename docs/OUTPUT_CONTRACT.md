# Output Contract

## Output Root

```text
<outputRoot>/
  items/
    <item-id>/
      video_record.json
      timeline.json
      convert_info.json
      raw_outputs/
        ffprobe.json
        frame_samples.json
      artifacts/
        contact_sheet.jpg
        frames/
          frame-000001.jpg
          frame-000002.jpg
  downloads/
  latest/
```

## Required Item Files

- `video_record.json`
- `timeline.json`
- `convert_info.json`
- `raw_outputs/ffprobe.json`
- `raw_outputs/frame_samples.json`
- `artifacts/contact_sheet.jpg`

## video_record.json

Required top-level keys:

- `schema_version`
- `record_id`
- `asset`
- `timeline`
- `video`
- `audio`
- `processing`
- `segments`
- `frames`
- `text`
- `review`

Schema version:

```text
timeline_for_video.video_record.v1
```

## timeline.json

Required lanes:

- `visual`
- `audio`

Initial event types:

- `video_observed`
- `video_interval`
- `frame_sample`
- `audio_reference`

## convert_info.json

Must include:

- product name and version
- generated timestamp
- source fingerprint
- source file identity
- ffmpeg/ffprobe version
- pipeline version
- generation signature
- sampling parameters
- output files
- counts
- warnings
- `source_video_modified: false`

## Export Rule

ZIP exports must not include source videos.

