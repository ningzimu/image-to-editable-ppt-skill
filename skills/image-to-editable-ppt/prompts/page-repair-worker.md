# Page Repair Worker Prompt 模板

```text
修复 image-to-editable-ppt 的一个页面问题。

Run dir: <absolute run dir>
Page id: <page_001>
Page dir: <absolute page dir>
Repair item id: <repair item id>
Failure type: <failure type>
Evidence:
- validation: <absolute path>
- preview: <absolute path>
- contact_sheet: <absolute path>
- repair_note: <absolute path or inline note>

允许修改范围：
<one text box | one asset sheet | one clean base | one manifest section | etc>

你只拥有这个 Page dir。不要编辑 deck_manifest.json、page_jobs.json、notes_manifest.json、final 输出、input 原件或任何其他 page 目录。

在任何生图或改图前，读取并遵守：
${CODEX_HOME:-$HOME/.codex}/skills/.system/imagegen/SKILL.md

目标：
只修复 repair item 指定的最小失败范围。不要重建整页，除非 repair item 明确说明整页 manifest 不可用。

完成后必须重新生成或更新：
- manifest.json
- page.pptx
- preview.png
- split_assets_contact.png
- validation.json
- page_result.json

`page_result.json` 必须是 JSON，字段与 page worker 相同，路径必须指向当前 Page dir 内的文件。

如果需要修复视觉资产，使用 $imagegen。不要用本地绘图代码伪造复杂视觉。

只返回：
page_manifest=<absolute path>
page_pptx=<absolute path>
preview=<absolute path>
contact_sheet=<absolute path>
validation=<absolute path>
page_result=<absolute path>
qa_note=<one sentence>
known_limits=<none or short list>
```
