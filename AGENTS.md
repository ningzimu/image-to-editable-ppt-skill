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

## Skill Documentation Architecture

The skill documentation under `skills/image-to-editable-ppt/` follows a strict ownership model. Future edits must preserve it.

### Design Principles

- **One authoritative home per rule.** Every requirement lives in exactly one file. Other files may carry at most a one-line pointer ("see `page-decision-tree.md` section 3.1") — never a restated list, enumeration, or procedure. Duplicated statements drift apart and inflate the token cost of every run.
- **Reader-role split.** `SKILL.md` is read by the parent/orchestrator agent; the references and the worker prompt are read by page workers. Parent-level rules (orchestration, dispatch, state machine, user interaction) belong in `SKILL.md`; page-level rules (object decisions, field contracts, QA) belong in the references. Do not let worker-level detail leak back into `SKILL.md`.
- **Every rule is a recorded failure.** Each requirement in these documents encodes a real past failure mode. Never delete a requirement during refactoring; when condensing or moving text, map every criterion to its new home first and verify nothing is lost. Tightening wording is welcome; dropping constraints is not.
- **Explain why, not bare musts.** Where a rule has a rationale (over-rounding is a common visible failure; nativizing text first locks in wrong object-source choices), state it briefly. Agents follow rules better when the failure they prevent is named.
- **Reminders, not replacements.** The worker prompt may carry a short hard-rules block (about five lines) restating the highest-risk red lines, each ending with a pointer to its authoritative home. This is the only sanctioned form of duplication.
- **Docs and CLI move together.** All run/page state transitions go through `editppt` commands. If a documented flow changes (for example: every page, including single-page input, is dispatched to a worker), the CLI behavior in `cli/` and the tests in `tests/` must change in the same PR. Docs must never describe a flow the CLI does not enforce.
- **Stable cross-references.** Files refer to each other by section name and number (`page-decision-tree.md` section 2.2, "Fix versus Warning"). When renaming or renumbering a section, grep the whole skill directory and update every referrer in the same change.
- **A reference file over ~300 lines gets a table of contents** at the top.

### File Responsibilities

| Path | Owns | Must not contain |
| --- | --- | --- |
| `SKILL.md` | Trigger description; parent-level Entry Contract; the four-phase workflow (prepare → dispatch → record → finalize); state principles; delivery principles; deck-level structural QA; PaddleOCR token user-interaction policy | Worker-level decision rules, field definitions, hints usage details, command syntax beyond the phase commands |
| `prompts/page-worker.md` | The worker execution template: page ownership boundary, mandatory-read enforcement for the three references, the short hard-rules block, execution order, required output list, return format | Restated decision-tree content, field contracts, or QA criteria — point to the references instead |
| `references/page-decision-tree.md` | Single source of truth for object-source decisions: the three-step process (background → foreground assets → native elements), all object classification lists, text-hints usage, the Final Self-Check, and the Fix versus Warning split | JSON field contracts, command syntax |
| `references/manifest-schema.md` | Single home for JSON field contracts of every run/page artifact: `deck_manifest.json`, `page_jobs.json`, `page_request.json`, `page_result.json`, `validation.json`, `manifest.json`, `imagegen-jobs.json`, `notes_manifest.json`; coordinate layouts; text-fitting fields | Decision rules about *when* to choose an object source |
| `references/cli-helper.md` | Pure command manual: install check, command tree, syntax and one-line purpose per command | Workflow narration, decision rules, user-interaction policy — those live in `SKILL.md` and the decision tree |
| `scripts/` | Skill-local helper scripts (the worker-prompt builder) | — |
| `cli/` | The `editppt` runtime that enforces the state machine and deterministic validation | — |
| `agents/` | Agent-platform metadata | Workflow rules |

When adding a new requirement, first decide which file owns it by the table above, write it there once with its rationale, and add pointers elsewhere only if agents are likely to need it at a different stage of the flow.

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

- This repository uses two release tracks:
  - `beta`: development/pre-release integration branch.
  - `main`: stable release branch.
- Feature branches should usually branch from `beta` and open PRs back to `beta`.
- Stable release PRs should merge `beta` into `main` after beta validation is complete.
- Beta releases use SemVer prerelease tags from commits contained in `beta`, for example `v0.2.0-beta.1`.
- Stable releases use SemVer tags from commits contained in `main`, for example `v0.2.0`.
- Do not create long-lived `develop`, `alpha`, or `stable` branches unless the branch model is explicitly revised.
- Release changes should go through a release PR before tagging.
- Move the relevant `## Unreleased` entries into the exact version section that matches the tag, such as `## 0.2.0-beta.1` or `## 0.2.0`; omit empty subsections.
- Add PR references to release changelog entries before tagging, for example `(#12)`.
- After the release PR is merged, tag the merge commit with the matching SemVer tag, then push the tag.
- Pushing `v*` tags triggers `.github/workflows/release.yml`.
- The release workflow extracts GitHub Release notes from the matching `CHANGELOG.md` version section, marks prerelease tags as GitHub prereleases, and rejects tags created from the wrong branch.
- The release workflow uploads `image-to-editable-ppt-skill-v*.zip`, which contains only the installable `image-to-editable-ppt` skill directory.
- This repository does not use a ClawHub publish flow.

## Verification

- Before opening a PR, run `git status --short` and review the changed file list.
- For Markdown-only changes, inspect rendered structure when practical.
- For GitHub workflow YAML changes, verify YAML parses when practical.
- Do not commit files from `output/`, Python caches, `.DS_Store`, local `.env`, or generated one-off PPT/image artifacts.
