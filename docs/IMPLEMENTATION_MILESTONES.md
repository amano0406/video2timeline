# Implementation Milestones

## Milestone 0: Read-Only Plan

- inspect the empty repo state
- read the handoff docs
- inspect reference products only as needed
- propose implementation plan
- do not modify code

## Milestone 1: Scaffold

- Python package
- Dockerfile
- docker-compose
- Windows launcher
- settings file
- `health`
- `settings init/status/save`

## Milestone 2: Discovery And Doctor

- input file and directory support
- recursive discovery
- supported video extensions
- `files list`
- `doctor`

## Milestone 3: ffprobe And Source Identity

- ffprobe execution
- `raw_outputs/ffprobe.json`
- metadata parsing
- source hash
- item id

## Milestone 4: Visual Sampling

- bounded sampling
- frame extraction
- `raw_outputs/frame_samples.json`
- frame artifacts
- contact sheet

## Milestone 5: Records And Items

- `video_record.json`
- `timeline.json`
- `convert_info.json`
- `items refresh`
- `items list`

## Milestone 6: Export And Remove

- `items download`
- `latest/`
- `items remove --dry-run`
- `items remove`
- source-safety tests

## Milestone 7: Docs And Validation

- unit tests
- smoke test
- README
- docs
- final validation report

