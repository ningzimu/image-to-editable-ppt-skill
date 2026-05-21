# AGENTS.md

Scope

This repository packages the `image-to-editable-ppt` skill.

- Repository-level docs, examples, CI, and release metadata live at the repository root.
- The installable skill lives under `skills/image-to-editable-ppt/`.
- Generated conversion outputs belong in `output/` and must not be committed.
- Curated images or decks used by README/docs belong in `assets/`.

## Editing Rules

- Do not edit files under `skills/image-to-editable-ppt/` unless the task explicitly asks to change the skill itself.
- Keep public docs focused on user-facing facts: what the skill does, how to install it, how to use it, and its real limits.
- Keep `README.md` and `README_en.md` synchronized. When changing one README, update the other in the same change so headings, examples, capabilities, limitations, install steps, and output structure stay equivalent across languages.
- Do not copy internal discussion notes, temporary decisions, or unpublished release plans into README files.

## Contribution Flow

- Non-trivial changes should go through a pull request.
- PR titles should follow Conventional Commit style, for example:
  - `docs: add installation notes`
  - `fix: ignore generated previews`
  - `feat: add example assets`
- Commit messages, PR titles, changelog entries, and release notes should be written in English.

## Changelog

- User-visible changes should update `CHANGELOG.md`.
- Add unreleased entries under `## Unreleased`.
- Use one of these sections:
  - `### Features`
  - `### Improvements`
  - `### Fixes`
  - `### Documentation`
- Changelog entries should be written in English.
- Add the PR reference after the PR is opened, for example `(#12)`.

## Release Flow

- Release changes should go through a release PR before tagging.
- Move the relevant `## Unreleased` entries into a version section such as `## 0.1.0`; omit empty subsections.
- After the release PR is merged, tag the merge commit with a SemVer tag such as `v0.1.0`, then push the tag.
- Pushing `v*` tags triggers `.github/workflows/release.yml`.
- The release workflow extracts GitHub Release notes from the matching `CHANGELOG.md` version section.
- The release workflow uploads `image-to-editable-ppt-skill-v*.zip`, which contains only the installable `image-to-editable-ppt` skill directory.
- This repository does not use a ClawHub publish flow.

## Verification

- Before opening a PR, run `git status --short` and review the changed file list.
- For Markdown-only changes, inspect rendered structure when practical.
- For GitHub workflow YAML changes, verify YAML parses when practical.
- Do not commit files from `output/`, Python caches, `.DS_Store`, local `.env`, or generated one-off PPT/image artifacts.
