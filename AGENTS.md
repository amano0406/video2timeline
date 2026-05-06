# AGENTS.md

## Language

Respond in Japanese.

## Project

This repository is `TimelineForVideo`.

The previous implementation was intentionally removed. Treat this repository as
a clean rebuild from an empty product repo.

Do not restore, reuse, or preserve the old TimelineForVideo implementation just
because it existed before. Use the old git history only if explicitly asked.

## Goal

Build a clean v1 product that converts local video files into timeline-oriented
evidence packages for later human review and LLM handoff.

## Reference Sources

Use these as read-only design references:

- `C:\apps\TimelineForAudio`
- `C:\apps\TimelineForImage`
- ChatGPT design thread captured with DockForChatGPT:
  `C:\Codex\workspaces\dockforchatgpt\chat_conversations\snapshots\20260506-114835-69f96218-7de4-83a9-b46b-d660584e0639-a7f37b4b-62b8-443c-905d-c71a0e9c6d78.json`

Do not import code from the reference products. Do not edit the reference
repositories.

## Rebuild Rules

- Breaking changes are allowed.
- Do not keep legacy flags, files, schemas, or compatibility shims unless they
  are useful for the new v1.
- Prefer simple local operation over a shared cross-product framework.
- Keep Windows user-facing commands PowerShell or `.bat` friendly.
- Use Docker-first runtime where practical.

## Safety Rules

- Do not delete, modify, convert in place, or mass-rename source videos.
- Do not copy source videos into item output folders.
- Do not include source videos in export ZIPs.
- Generated artifacts may be deleted by explicit generated-output commands.
- Do not add hosted/cloud dependencies for v1.
- Do not implement person recognition, face recognition, or external API
  analysis in v1.

## Read First

1. `docs/CODEX_HANDOFF.md`
2. `docs/DECISIONS.md`
3. `docs/OUTPUT_CONTRACT.md`
4. `docs/ACCEPTANCE_CRITERIA.md`
5. `docs/IMPLEMENTATION_MILESTONES.md`

