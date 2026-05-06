# Acceptance Criteria

## Required Behavior

- `settings init/status/save` work.
- `health` works.
- `doctor` checks runtime and configured paths.
- `files list` discovers video files from file and directory inputs.
- `items refresh --max-items 1` processes one sample video.
- `items list` shows generated items.
- `items download` creates a ZIP.
- ZIP exports do not include source videos.
- `items remove --dry-run` reports generated artifacts only.
- `items remove` removes generated artifacts only.
- Source videos remain after remove.

## Required Tests

- settings tests
- discovery tests
- sampling tests
- ffprobe parsing tests using fixture JSON
- output record shape tests
- ZIP source video exclusion tests
- remove source-safety tests
- generated sample video smoke test

## Required Docs

- `README.md`
- `README.ja.md`
- `docs/CLI.md`
- `docs/OUTPUTS.md`
- `docs/PIPELINE.md`
- `docs/RUNTIME.md`
- `docs/SAFETY.md`
- `docs/TESTING.md`

