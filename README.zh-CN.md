# DS-160 Form AutoFiller

[English](README.md) · **简体中文**

用你自己的证件和文件，让 AI agent 在你真实的浏览器里填写美国签证申请表 DS-160，并在签名之前把每个答案都核实一遍。

每个答案都注明来源和置信度。每填完一页，工具都会从美国国务院网站读回实际保存的内容，和你的档案逐字段对账。最后生成一份可打印的审阅文件，列出每个答案、它的置信度和出处。

![示例申请人的最终审阅文件](docs/review-example.png)

## 为什么做这个

DS-160 大约有 300 个字段，分布在 18 个 section 里。闲置 20 分钟就会超时，而且不会自动保存。它对细小的不一致很敏感，比如某个日期和你的 I-94 对不上，或者地址和 I-765 上的不一样。自动填表脚本能省打字，但省不了信任。这个项目的做法是保留一条完整的证据链：

- **你的文件就是事实来源**：护照、签证、I-20、I-94 出入境记录、EAD、W-2、offer letter 以只读方式导入，计算哈希，提取成文本。
- **每个事实都有出处**：格式是 `{value, confidence, source}`，比如 `raw/I-94/Travel_History.pdf#p1`；如果是你亲口说的，就记为 `user:2026-09-27`。
- **不会悄悄猜测**：未知项会生成一份简短问卷。默认值一律标为 `assumed`，直到你确认为止。
- **核实线上表单**：每个 section 都从 CEAC 拍快照，逐字段对账。
- **控制权在你**：agent 不解验证码，也不会签名或提交。

## 流水线

```
文件 ──ingest──▶ raw/ + sha256 清单 ──digest──▶ 文本 ──agent──▶ 事实（值 · 置信度 · 出处）
                                                                  │ validate：校验位、MRZ、跨字段一致性
表单 spec（CEAC 元素 ID）──────────────────────────────────────▶ sheet：每个字段的期望值
                                                                  │ agent 在 Chrome 里填写 CEAC
线上页面快照 ─────────────────────────────────────────────────▶ recon：一致 / 不一致 / 未知
                                                                  ▼
                       OVERVIEW.md · QUESTIONNAIRE.md · review.html · review.pdf
```

一条命令跑完全程：

```console
$ ds160 run AA00XXXXXX
 ✓ raw integrity      126 documents, sha256 intact
 ✓ digest             up to date
 ✓ validate profile   0 errors, 0 facts to confirm
 ✓ build sheet        288 fields, 0 unknown, 0 invalid
 ✓ recon vs CEAC      288 match, 0 differ, 0 unchecked, 0 open questions
 ✓ review document    review.html + review.pdf
```

## 快速开始

需要 Python ≥ 3.11 和 [uv](https://docs.astral.sh/uv/)。在线填表需要 [Claude Code](https://claude.com/claude-code) 加上 Claude in Chrome。导出 PDF 需要本机装有 Chrome 或 Chromium。

```bash
git clone https://github.com/ChiChasesCheese/DS160-Form-AutoFiller && cd DS160-Form-AutoFiller
uv sync --all-extras
make demo            # 用一个虚构的申请人（examples/）跑完整条流水线
```

如果只要命令行工具：`pipx install "ds160-autofiller[photo] @ git+https://github.com/ChiChasesCheese/DS160-Form-AutoFiller"`。

### 用你自己的文件

```bash
ds160 ingest ~/Documents/immigration            # → raw/（已 gitignore，永不修改）
ds160 digest                                    # → data/digest/；INDEX.tsv 会标出需要人眼看的扫描件
# 对 Claude Code 说：“按 skills/immigration-intake 建我的档案”
ds160 validate                                  # 必须 0 错误
mkdir -p data/applications/AA00XXXXXX
cp examples/data/applications/DEMO0000001/application.yaml data/applications/AA00XXXXXX/
# 对 Claude Code 说：“按 skills/ds160-autofill 填 AA00XXXXXX”
ds160 run AA00XXXXXX                             # 对账 + 生成可打印的审阅文件
```

agent 遇到它无法知道的信息（比如父母的出生日期）时，会生成 `QUESTIONNAIRE.md`。你可以直接在聊天里回答，也可以把文件放进 `raw/inbox/`。它会连同出处一起保存你的答案，然后继续往下填。

## 命令

| 命令 | 作用 |
|---|---|
| `ds160 ingest SRC…` | 把文件复制进 `raw/`，并生成 sha256 清单。可以重复运行，永不覆盖。 |
| `ds160 verify-raw` | `raw/` 里有文件被改动或缺失时报错。 |
| `ds160 digest [--ocr]` | 按页提取文本（PDF、DOCX；图片走 tesseract），输出到 `data/digest/`。 |
| `ds160 validate [--all]` | 检查档案：身份证校验位、护照 MRZ 校验位、身份证里的出生日期和性别、日期先后顺序、电码位数、出处格式。 |
| `ds160 sheet APP` | 生成每个 CEAC 元素的期望值，以及校验结果。 |
| `ds160 recon APP` | 把 sheet 和线上快照对账，生成 `OVERVIEW.md` 和 `QUESTIONNAIRE.md`。 |
| `ds160 answer PATH VALUE` | 保存你的回答，并记下出处和置信度（答案覆盖层）。 |
| `ds160 review APP [--mask]` | 生成 `review.html` 和 `review.pdf`。加 `--mask` 会隐藏 SSN 和身份证号。 |
| `ds160 photo IMG --hair Y --eyes Y --chin Y` | 裁剪并编码合规照片：正方形，600–1200 像素，≤ 240 kB，头部占 50–69%，眼睛离底边 56–69%。支持 HEIC。 |
| `ds160 run APP` | 按顺序执行以上全部步骤，每一步给出通过 / 警告 / 失败。 |

`backhome` 是 `ds160` 的别名。

## 置信度

| 等级 | 含义 |
|---|---|
| `verified` | 有官方文件，**并且**经过独立核实（第二份文件、校验位/MRZ、CEAC 回读） |
| `high` | 从官方文件中直接提取的文本 |
| `medium` | 看图或 OCR 读出来的，或由文件计算得出 |
| `user` | 你亲口说的，没有文件佐证 |
| `low` | 根据间接证据推断 |
| `assumed` | 没有证据的默认值，签名前必须确认 |

出处格式：`raw/<路径>#p<页码>` · `user:YYYY-MM-DD` · `ceac:<页面>` · `derived:<推导方式>`。
`null` 表示未知（需要询问），`__NA__` 表示不适用。

## 使用 agent skills

浏览器里的操作由 Claude Code 按本仓库的两个 skill 完成。把它们链接到你的 skills 目录：

```bash
ln -s "$PWD/skills/immigration-intake" ~/.claude/skills/
ln -s "$PWD/skills/ds160-autofill"     ~/.claude/skills/
```

`skills/ds160-autofill/SKILL.md` 里还记录了这个项目踩过的各种 CEAC 坑：
- 保存和下一步必须用真实点击。
- 有些下拉框要先点 Save 才会展开字段。
- "不知道"复选框必须点击勾选，不能直接设值。
- 每一页的日期格式都不一样。

## 目录结构

```
src/backhome/          model（事实）、validators、docs（ingest/digest）、forms（sheet/recon/问卷）、
                       review（HTML/PDF）、photo、pipeline、cli
src/backhome/forms/ds160/spec.yaml   18 个 section 的全部 CEAC 元素 ID，均从线上页面实测采集
src/backhome/ceac/     snapshot.js、nav.js：在 CEAC 页面里运行
skills/                Claude Code skills（intake、autofill）
examples/data/         虚构申请人，供测试、CI 和演示使用
raw/  data/            你的文件和事实：已 gitignore，永远不会离开你的电脑
```

## 隐私与安全

- `raw/` 和 `data/` 已加入 gitignore。只要有任何一个被纳入版本库，CI 就会失败。
- 所有处理都在本地进行。唯一的网络访问，是你自己的浏览器访问 ceac.state.gov。
- agent 不解验证码，不签名，也不提交。以下几步由你完成：调取申请、Review、签名。在 identix.state.gov 上传照片需要你授权后，agent 才能代劳。
- 详见 [SECURITY.md](SECURITY.md)。

## 免责声明

本项目不构成法律建议，与美国国务院无任何关联。申请内容是否真实由你本人负责。签名前请逐条核对生成的审阅文件。

## 参与贡献

欢迎提 Issue 和 PR，尤其是新的表单 spec（DS-260、I-765……）以及 CEAC 的页面变动。详见 [CONTRIBUTING.md](CONTRIBUTING.md)。许可证：[MIT](LICENSE)。
