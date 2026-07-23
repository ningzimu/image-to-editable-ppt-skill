# 常见问题

## Q：为什么这么费 token？Plus 会员能用吗？

本 skill 采用多智能体协作复原流程，AI 会对每一页执行「重建 → 自我检查 → 页面内修正」的循环，page worker 可能对一页做很多轮尝试，直到结果足够接近原图。把一个图片 PPT 转成可编辑 PPT 的成本，可能是生成图片 PPT 成本的 2-3 倍。

**推荐 ChatGPT Pro 用户使用；Plus 用户请谨慎使用。** 复原一个 10 页 PPT 有可能消耗完 5 小时额度，单页复原时间可能在 10 分钟以上。Plus 用户建议先拿单页试水。

## Q：什么情况下不该用这个 skill？

如果没有强烈的可编辑需求，请不要使用。更轻量的做法是直接使用 `gpt-image-2` 的图像编辑能力：把你不满意的那一页 PPT 图片发给它，让它针对性修改并返回修改后的图片。

另外，本 skill 不负责从文章、报告、大纲或想法生成全新 PPT——那是 [codex-ppt-skill](https://github.com/ningzimu/codex-ppt-skill) 的职责。

## Q：为什么建议使用「完全访问权限」？

本 skill 运行时间较长，会自动执行 OCR、图片生成/编辑、文件读写、子 agent 分派和长时间轮询。「请求批准」模式会频繁打断执行；「替我审批」模式已知仍可能在 OCR 或图片生成阶段拦截请求——如果你不在电脑旁，转换流程会停住。详见[安装与配置](installation.md)。

## Q：OCR Token 是什么？必须配置吗？

不是必须，但强烈推荐。本 skill 通过百度 PaddleOCR-VL 校正文字的框坐标、字号和字号分组，让文字还原以测量值为准而不是目测。Token 到百度 AI Studio 免费申请：<https://aistudio.baidu.com/account/accessToken>，个人使用免费额度完全够用。

首次使用时 AI 会主动询问你一次，把 Token 发给它即可，一次配置长期生效。不配置也能运行，skill 会退化为内置离线检测（知道文字在哪、多大，但不识别内容），文字还原质量会打折扣。

## Q：支持哪些输入？

单张图片、多张图片、多页 PDF、图片版 `.pptx`，统一输出可编辑 `.pptx`。多张图片按提供顺序生成页面，PDF 和 `.pptx` 保留原页码顺序。`.pptx` 输入的页面备注会原样复制到输出对应页。

## Q：转换结果能 100% 还原原图吗？

不能保证。可读文字、简单形状会尽量恢复为可编辑对象，但部分图片元素和文字位置可能有轻微偏移。对照片、插画、纹理等复杂视觉元素，通常只能作为独立图片资产整体移动，不保证内部可编辑。判断质量时建议同时看 PPTX 结构、文本覆盖、资产来源和预览对比，参见[标准工作流](workflow.md)的能力边界一节。

## Q：支持 Codex 以外的 agent 吗？

有条件支持。agent 需要支持 skill 加载、文件读写和 CLI 执行；多页任务还需要 page worker/subagent 分派机制。如果当前环境不能创建 page worker，多页任务应换到支持的环境执行。

非 Codex 环境（如 Claude Code、OpenClaw、Hermes Agent）通常没有 Codex OAuth，需要配置 OpenAI-compatible 的图片 API fallback，参见[安装与配置](installation.md)。

另外，受限于模型基础理解能力和对 skill 的遵循能力，不保证 gpt-5.5 以下模型的使用效果。

## Q：图片生成用的是什么？需要配 API key 吗？

图片生成和编辑优先调用当前 agent 的内置 `image_gen.imagegen`。只有内置工具不可用、调用失败、无法读取编辑输入或没有返回有效本地图片等约定情况，才降级到 `editppt image`；CLI 会先尝试本机 Codex OAuth（走订阅侧图片额度），再读取 `~/.editppt/config.yaml` 里的 OpenAI-compatible API 配置。Codex 会员通常不需要配置 API key。需要第三方 fallback 时，把服务的 base URL、模型名和 API key 告诉 AI，它会帮你写入用户级配置并遮蔽敏感值。

## Q：如何更新 skill 到最新版本？

直接让 agent 帮你更新（发一句「更新 image-to-editable-ppt 这个 skill，地址是 https://github.com/ningzimu/image-to-editable-ppt-skill」），或从 Releases 下载最新 zip 替换原目录，然后重启 agent 生效。API 凭据和 OCR Token 保存在 `~/.editppt/config.yaml`，在 skill 目录之外，更新不会丢失。详见[安装与配置](installation.md)。

## Q：转换到一半停住了怎么办？

先检查是不是权限模式在等待你审批（见上文完全访问权限问题）。每页的分派和完成状态记录在任务目录的 `page_jobs.json` 和 `run_state.json` 里，可以让 AI 检查当前运行状态并继续未完成的页面。
