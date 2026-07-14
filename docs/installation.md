# 安装与配置

## 一句话安装

推荐直接把下面这句话发给你的 agent，让它帮你安装：

```text
安装 image-to-editable-ppt 这个 skill，地址是 https://github.com/ningzimu/image-to-editable-ppt-skill
```

安装后，正常转换、图片 API fallback 和 OCR Token 配置都由 AI 在执行过程中检查和处理；你只需要在 AI 询问时提供第三方 API 信息或 OCR Token。

## 手动安装

从 [GitHub Releases](https://github.com/ningzimu/image-to-editable-ppt-skill/releases) 下载 `image-to-editable-ppt-skill-v*.zip`，解压后把其中的 `image-to-editable-ppt` 文件夹放到 agent 的 skills 目录（Codex 为 `~/.codex/skills/image-to-editable-ppt`），然后重启 agent。

如果你在本地开发这个仓库，可以把 skill 目录软链接到 skills 目录，方便实时调试修改：

```bash
mkdir -p ~/.codex/skills
ln -s /path/to/image-to-editable-ppt-skill/skills/image-to-editable-ppt ~/.codex/skills/image-to-editable-ppt
```

## 更新 skill

推荐直接把下面这句话发给你的 agent：

```text
更新 image-to-editable-ppt 这个 skill，地址是 https://github.com/ningzimu/image-to-editable-ppt-skill
```

手动更新时，从 [GitHub Releases](https://github.com/ningzimu/image-to-editable-ppt-skill/releases) 下载最新 zip，解压后替换原来的 `image-to-editable-ppt` 目录。更新完成后重启 agent 生效。

更新是安全的：图片 API 凭据和 OCR Token 都保存在 `~/.editppt/config.yaml`（Windows 下为 `%USERPROFILE%\.editppt\config.yaml`），在 skill 安装目录之外，更新或重装不会丢失。每个版本的变更内容可以查看 [Releases 页面](https://github.com/ningzimu/image-to-editable-ppt-skill/releases)或仓库的 `CHANGELOG.md`。

## 运行权限建议

**建议在 Codex 中使用「完全访问权限」执行本 skill。**

本 skill 运行时间较长，并且会自动执行 OCR、图片生成/编辑、文件读写、子 agent 分派和长时间轮询等步骤。「请求批准」模式会频繁打断执行，可能阻塞部分步骤，尤其是在子 agent 环境里。「替我审批」模式已知仍可能在 OCR 阶段、图片生成/编辑阶段或第三方 API 调用阶段拦截请求，要求你手动审批；如果你不在电脑旁，转换流程会停住。

![Codex 完全访问权限设置示意](https://raw.githubusercontent.com/ningzimu/image-to-editable-ppt-skill/main/assets/codex-full-access-permission.png)

## 运行要求

- 单页/单图输入不需要创建 page worker，由主 agent 本地执行同一页面重建流程。
- 多页输入需要 agent 能分派 page worker/subagent；如果当前环境不能创建 page worker，应换到支持 page worker 的环境执行。
- 本 skill 依赖的 `editppt` 命令行工具是 AI 在执行 skill 的过程中自动安装的，不需要你手动执行任何命令。
- 受限于模型基础理解能力和对 skill 的遵循能力，不保证 gpt-5.5 以下模型的使用效果。

## OCR Token（推荐配置）

本 skill 通过第三方 OCR 服务（百度 PaddleOCR-VL）来校正文字的大小和位置，显著提升文字还原质量，原理参见[设计理念](design.md)。

**你只需要做一个动作——申请 Token**：到百度 AI Studio 申请 Access Token：<https://aistudio.baidu.com/account/accessToken>。对个人使用来说，目前免费额度完全够用，可以放心申请，无额外费用。

首次使用时如果还没配置 Token，AI 会主动询问你一次——把申请到的 Token 发给它即可，AI 会帮你写入用户级配置（`~/.editppt/config.yaml`，遮蔽存储），一次配置长期生效，之后不再提示。

不提供 Token 也能运行：skill 会退化为内置的离线检测器（纯几何测量，不识别内容），文字还原质量会有折扣。

## 图片 Backend 与第三方 API 配置

`editppt image` 会自动选择图片后端：优先使用本机 Codex OAuth（`~/.codex/auth.json`）；如果不可用，再读取 `~/.editppt/config.yaml` 或环境变量里的 OpenAI-compatible API 配置。

通常不需要你自己配置。只有这些情况才需要让 AI 帮你配置 API fallback：

- 你明确要求使用第三方 API 或 OpenAI 兼容中转站。
- 在 Claude Code、OpenClaw、Hermes Agent 等非 Codex 环境中使用，并且没有可用的 Codex OAuth auth。
- `editppt image` 报告 Codex OAuth 和 `OPENAI_API_KEY` 都不可用。

如果需要第三方 API fallback，告诉 AI 你要使用的服务、base URL、模型名和 API key 即可。AI 会在执行过程中完成环境检查和配置写入，把凭据保存在用户级配置 `~/.editppt/config.yaml`，并在输出里遮蔽敏感值。不要把 API key 写进项目目录、run 目录或 skill 目录。

Codex OAuth 路径依赖本机 Codex auth 和订阅侧图片额度；API fallback 依赖所选 OpenAI-compatible 服务的图片生成/编辑能力。
