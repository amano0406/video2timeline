# Testing

Run from WSL or the local development shell:

```bash
PYTHONPATH=worker/src python3 -m unittest discover -s worker/tests -v
python3 -m compileall -q worker/src worker/tests
git diff --check
docker compose config
docker compose build worker
docker compose run --rm --no-deps worker health --json
```

The test suite covers:

- settings validation
- discovery
- ffprobe parsing with fixture JSON
- bounded sampling
- item record shapes
- ZIP source video exclusion
- remove source-safety behavior
- CLI JSON behavior

For full smoke validation, create a short generated sample video, run sampling,
refresh items, list items, download, dry-run remove, and actual remove. Confirm
the source video still exists after remove.
