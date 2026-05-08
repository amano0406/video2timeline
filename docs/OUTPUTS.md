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
        frame_ocr.json
        audio_analysis.json
        activity_map.json
      artifacts/
        contact_sheet.jpg
        frames/
          frame-000001.jpg
        ocr/
          frame-000001-ocr.jpg
        audio/
          source_audio.mp3
  downloads/
    timeline-for-video-items-<timestamp>.zip
  latest/
    items.zip
    download_manifest.json
```

## Item Files

- `video_record.json`: source identity, parsed media summary, frame references, frame visual summaries, review pointers.
- `timeline.json`: visual, audio, and text lanes using source-video-relative time.
- `convert_info.json`: product/version, source fingerprint, ffprobe version, sampling parameters, output files, counts, warnings.
- `raw_outputs/ffprobe.json`: ffprobe probe record including raw ffprobe JSON.
- `raw_outputs/frame_samples.json`: bounded sampling record.
- `raw_outputs/frame_ocr.json`: local OCR results and frame visual features for generated frame samples, using Image-compatible OCR fields such as `has_text`, `full_text`, `block_id`, and `bbox_norm`.
- `raw_outputs/audio_analysis.json`: generated audio derivative, temporary normalized-WAV model input metadata, speech candidate evidence, speech-scoped pyannote diarization status, and ZIPA acoustic-unit status. Acoustic-unit turns use `phone_tokens`.
- `raw_outputs/activity_map.json`: source-safe activity map combining merged audio speech candidates and five-minute visual sentinel deltas. Inactive intervals are evidence that detailed analysis can be skipped because the audio is silent and the sampled visual signal is static.
- `artifacts/contact_sheet.jpg`: generated review contact sheet.
- `artifacts/frames/`: generated frame samples.
- `artifacts/ocr/`: generated OCR debug overlays.
- `artifacts/audio/source_audio.mp3`: generated MP3 audio derivative for local review. It is not used as the audio-model input and is not included in ZIP exports.

## ZIP Exports

ZIP exports include generated item records, raw outputs, frame artifacts, OCR
overlays, and contact sheets. They do not include source videos or generated MP3
audio derivatives.
