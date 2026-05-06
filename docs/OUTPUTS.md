# Outputs

All generated files are written under `outputRoot`.

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
  downloads/
    timeline-for-video-items-<timestamp>.zip
  latest/
    items.zip
    download_manifest.json
```

## Item Files

- `video_record.json`: source identity, parsed media summary, frame references, review pointers.
- `timeline.json`: visual and audio lanes using source-video-relative time.
- `convert_info.json`: product/version, source fingerprint, ffprobe version, sampling parameters, output files, counts, warnings.
- `raw_outputs/ffprobe.json`: ffprobe probe record including raw ffprobe JSON.
- `raw_outputs/frame_samples.json`: bounded sampling record.
- `artifacts/contact_sheet.jpg`: generated review contact sheet.
- `artifacts/frames/`: generated frame samples.

## ZIP Exports

ZIP exports include generated item records, raw outputs, and artifacts. They do
not include source videos.
