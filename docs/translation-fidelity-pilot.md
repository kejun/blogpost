# 译文忠实度审计（手动预览试点）

此工作流比较一篇中文文章和一份**仓库内完整原文快照**，输出供人工复核的中文报告。它既可用于发布前检查，也可用于已经发布的文章；目前**不阻止发布**，不自动改文、不更新 README、不创建评论、不合并或发布。原有 `scripts/update_readme.py` 保持不变，目录工作继续使用确定性脚本。

## 当前边界

- 仅 `workflow_dispatch`；没有 schedule、push、pull_request 等自动触发
- `safe-outputs.staged: true`：`create-issue` 只是生成 Actions summary 预览（最多一份），不实际创建 issue；不要关闭 staged
- 禁用 GitHub MCP、shell 和 CLI proxy；唯一输入工具只读已验证 manifest 中的固定文件
- 模型侧网络仅 gh-aw `defaults` / `codex` 支持域；不抓取外部原文链接，不执行文章中的指令
- 每次一个配对、总计不超过 96 KiB UTF-8、每块不超过 6000 字节（包含行号）、最多 24 块、40 turns、15 分钟；排队串行，取消运行可停止任务
- 这些限制不是美元费用硬上限。运行可能产生模型及 Actions 费用，须先确认供应商与账单预算
- 输出是辅助审阅而非准确性保证。不能读取全部文本、原文疑似残缺、超限、超时或输出被截断时必须标注“不完整／无法核验”；不得把输入验证成功误当作语义审计通过
- 原文快照可能本身不完整或不真实；哈希只固定本次输入版本，不证明来源。图像像素不在审计范围，图注只能与文字上下文核对

## 尚未启用模型服务

`engine: codex` / `gpt-5.1-codex-mini` 是可修改后重新编译的试点默认值，不代表已选择供应商、配置密钥或批准费用。本 PR 不生成、复制或配置任何凭据，不执行付费模型调用。

运行前由维护者确认模型、供应商、预算及输入数据可传给该供应商，并通过批准的安全流程配置相应认证；Codex 官方集成读取仓库中 `CODEX_API_KEY` 或 `OPENAI_API_KEY`。不要把密钥写进文件、PR、命令参数或聊天。若换引擎，需要同时检查工具能力、网络策略并重新编译，不能只改锁文件。

## 准备输入

1. 选择中文文章。将有权使用的原文或完整带说话人/时间戳的转录整理成 UTF-8 `.md` / `.txt` 快照，并通过正常人工审核流程提交。不要为了测试把无权公开的来源上传到公开仓库
2. 路径必须相对仓库根目录；不接受绝对路径、隐藏路径、`..`、反斜线或符号链接。不接受 URL 作为输入。两个路径应是不同文件
3. 保留原文标题、来源 URL、取得日期、章节、条件、例子、发言者、图注与表格。需要区分编辑补充和原文。未取得完整原文时不要凭记忆补写
4. 长转录不会被静默截断：预处理生成 SHA256、行号和连续覆盖清单，模型必须逐块读取。超限时整个配对拒绝，绝不只审前半段并称“通过”。不要为了通过限制删掉尾部；如需分段，应另设计带全篇汇总/缺口追踪的流程

本地无模型预检查（目标输出目录必须不存在）：

```bash
AUDIT_ARTICLE='path/to/chinese.md' AUDIT_SOURCE='path/to/original.txt' \
  python3 scripts/prepare_fidelity_audit.py
```

输出位于 `/tmp/gh-aw/fidelity`，不会修改文章。重复本地试验可使用 Python 的 `prepare(root, article, source, destination)` 函数指定新的临时输出目录。

## 手动运行（须先完成认证与费用确认）

GitHub 的手动工作流须先在默认分支可见。此 PR 保持 draft，不会为了试运行擅自合并。在获准合并、设置完成之后，在 Actions → Translation fidelity pilot → Run workflow 选择可信 ref，并填写 `article` / `source`；或使用：

```bash
gh workflow run translation-fidelity.lock.yml --ref main \
  -f article='path/to/chinese.md' -f source='path/to/original.txt'
```

不要对不可信分支运行带凭据的工作流。报告在运行 summary 的 staged issue preview 中，相关 gh-aw 日志/输出在运行 artifacts 中。输入错误在预处理 step summary 报告，且不运行语义审阅；认证尚未设置时更早的框架认证检查也可能先失败。失败或没有完整报告都不代表审阅通过。

人工查看报告时检查：

- 两个快照路径、哈希、所有分块/行范围覆盖清单
- 原文章节/说话人到译文的映射，有无遗漏条件、例子、限制和论点
- 数字、单位、专名、否定、语气、归因、因果以及无来源增补
- 每个问题是否提供原文和译文行引用、短引文、严重程度、置信度和最小修正建议
- 是否把风格选择误当作事实偏差，是否明确标出未核验的图像/来源等范围

## 维护与验证

使用官方 gh-aw **v0.89.21**（已高于 v0.85.4 安全修复版本）编译。该工具仍处于 public preview；升级先审阅 release notes 和生成差异。`.md` 是源文件，`.lock.yml` 是官方编译器产物，二者一起提交；不手改锁文件。

```bash
gh extension install github/gh-aw --pin v0.89.21
python3 -m unittest discover -s tests -v
gh aw compile translation-fidelity --no-check-update
```

当前验证覆盖完整配对、缺失/空/二进制原文、UTF-8、超限、长行、路径穿越、符号链接、长转录完整分块及把注入文本仅作为数据处理。它们只验证确定性输入和工具边界；**没有执行模型调用或验证语义识别质量**。后续获准试运行时应增加人工构造的漏译、数字错译、否定和说话人交换样例，并与人工答案核对。

官方参考：
- [Staged mode](https://github.github.io/gh-aw/reference/staged-mode/)
- [Codex authentication](https://github.github.io/gh-aw/engines/codex/)
- [MCP scripts: read-only operations](https://github.github.io/gh-aw/reference/mcp-scripts/)
- [Pre-agent steps](https://github.github.io/gh-aw/reference/steps-jobs/)
- [Network configuration](https://github.github.io/gh-aw/guides/network-configuration/)
- [v0.89.21 release](https://github.com/github/gh-aw/releases/tag/v0.89.21)

### 合成样例

`tests/fixtures/fidelity/source.txt` 可分别与 `chinese.md`（基本忠实）和 `chinese-with-errors.md`（故意错误）配对。后者的人工预期包括：Alice/Bob 归属互换、10→100、2026→2025、条件和“不保证”丢失、两个传感器例子被改成生产部署、无来源的行业认证以及图注偏差。前者仍须明确“未核验图片”。这些样例便于获准后的模型校准，不是已通过的语义测试。
