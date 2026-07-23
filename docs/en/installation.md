# Installation and Configuration

## One-Sentence Installation

We recommend sending the following sentence directly to your agent and letting it install the skill:

```text
Install the image-to-editable-ppt skill from https://github.com/ningzimu/image-to-editable-ppt-skill
```

After installation, the AI checks and handles normal conversion requirements, image API fallback, and OCR Token configuration as part of the workflow. You only need to provide third-party API details or an OCR Token when asked.

## Manual Installation

Download `image-to-editable-ppt-skill-v*.zip` from [GitHub Releases](https://github.com/ningzimu/image-to-editable-ppt-skill/releases). Extract it, place the included `image-to-editable-ppt` folder in your agent's skills directory (`~/.codex/skills/image-to-editable-ppt` for Codex), and restart the agent.

If you are developing this repository locally, you can symlink the skill directory into your skills directory so changes are available immediately:

```bash
mkdir -p ~/.codex/skills
ln -s /path/to/image-to-editable-ppt-skill/skills/image-to-editable-ppt ~/.codex/skills/image-to-editable-ppt
```

## Updating the Skill

We recommend sending the following sentence directly to your agent:

```text
Update the image-to-editable-ppt skill from https://github.com/ningzimu/image-to-editable-ppt-skill
```

To update manually, download the latest zip from [GitHub Releases](https://github.com/ningzimu/image-to-editable-ppt-skill/releases), extract it, and replace the existing `image-to-editable-ppt` directory. Restart the agent when the update is complete.

Updates are safe: image API credentials and the OCR Token are stored outside the skill installation directory in `~/.editppt/config.yaml` (`%USERPROFILE%\.editppt\config.yaml` on Windows), so updates and reinstalls will not remove them. See the [Releases page](https://github.com/ningzimu/image-to-editable-ppt-skill/releases) or the repository's `CHANGELOG.md` for changes in each version.

## Recommended Permissions

**We recommend running this skill in Codex with Full Access enabled.**

The skill can run for a long time and automatically performs OCR, image generation and editing, file operations, subagent dispatch, and long polling. Ask for Approval mode can repeatedly interrupt execution and may block some steps, especially in subagent environments. Auto Approval mode is also known to stop requests during OCR, image generation or editing, or third-party API calls and require manual approval. If you are away from your computer, the conversion will stop.

![Codex Full Access setting](https://raw.githubusercontent.com/ningzimu/image-to-editable-ppt-skill/main/assets/codex-full-access-permission.png)

## Runtime Requirements

- Single-page or single-image input does not require a page worker. The main agent runs the same page reconstruction workflow locally.
- Multi-page input requires an agent capable of dispatching page workers/subagents. If the current environment cannot create page workers, run the task in an environment that supports them.
- The AI automatically installs the `editppt` command-line tool required by this skill during execution. You do not need to run any installation commands yourself.
- Because results depend on the model's underlying reasoning and its ability to follow the skill, performance is not guaranteed with models below gpt-5.5.

## OCR Token (Recommended)

This skill uses a third-party OCR service (Baidu PaddleOCR-VL) to correct text size and position, substantially improving text reconstruction quality. See [Design Principles](/en/design.md) for how it works.

**You only need to do one thing—obtain a Token**: request an Access Token from Baidu AI Studio at <https://aistudio.baidu.com/account/accessToken>. The current free allowance is more than sufficient for personal use, with no additional charge.

If no Token has been configured on first use, the AI will ask for it once. Send it the Token, and the AI will store it in the masked user-level configuration at `~/.editppt/config.yaml`. The setting persists, so you will not be asked again.

The skill also works without a Token by falling back to its built-in offline detector. This detector performs geometric measurement only and does not recognize text content, so text reconstruction quality will be lower.

## Image Backend and Third-Party API Configuration

Image generation and editing prefer the current agent's built-in `image_gen.imagegen` tool. Only when a defined fallback condition is met does the workflow invoke the `editppt image` CLI, which prefers local Codex OAuth (`~/.codex/auth.json`) and, if that is unavailable, reads OpenAI-compatible API configuration from `~/.editppt/config.yaml` or environment variables.

You normally do not need to configure anything yourself. Ask the AI to configure an API fallback only when:

- You explicitly want to use a third-party API or an OpenAI-compatible proxy.
- You are using a non-Codex environment such as Claude Code, OpenClaw, or Hermes Agent without usable Codex OAuth authentication.
- `editppt image` reports that neither Codex OAuth nor `OPENAI_API_KEY` is available.

When a third-party API fallback is needed, provide the AI with the service name, base URL, model name, and API key. The AI will check the environment and save the configuration to the user-level `~/.editppt/config.yaml`, masking sensitive values in its output. Do not place an API key in the project directory, run directory, or skill directory.

The Codex OAuth path depends on local Codex authentication and your subscription's image allowance. API fallback depends on the image generation and editing capabilities of the chosen OpenAI-compatible service.
