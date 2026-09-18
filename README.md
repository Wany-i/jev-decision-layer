# jev-decision-layer

把决策模型包成**业务决策工具**：调用方只说"要做什么判断"，不说"用哪个模型"。

[![CI](https://github.com/Wany-i/jev-decision-layer/actions/workflows/ci.yml/badge.svg)](https://github.com/Wany-i/jev-decision-layer/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Dependencies](https://img.shields.io/badge/dependencies-none-brightgreen.svg)](#依赖与许可)

> ⚠️ **非官方项目。** 第三方封装，与 TypeSafe AI 无任何隶属关系。

---

## 背景：这个项目接的是什么

| 项 | 值 |
|---|---|
| **调用平台** | **OpenRouter** —— 走它的 decisions 端点，不是通用的 `chat/completions` |
| **端点** | `POST https://openrouter.ai/api/alpha/decisions`（注意**没有 `/v1`**，加了会 404） |
| **模型代号** | **`typesafe/jev-1.13`**（别名 `jev-latest`；实测回答版本 `typesafe/jev-1.13-20260917`；厂商标识 `TypeSafe`） |
| **模型类型** | "System One" **决策模型**：输入 `state` + 声明式 `questions`，输出类型化答案 + 概率 + 置信度，**不生成文本** |
| **输出形态** | `answers` 内按问题类型分三种：`choice`（选项 + 概率 + 置信度）/ `score`（分数 + 概率 + 置信度）/ `noul`（是-否概率，**无置信度字段**） |
| **计费** | 按输入 token 计，$0.042 / 百万 token，**输出免费** |
| **上下文** | 64k / 请求；其中 `state` + 单条最长问题 ≤ **32k**（硬上限） |

**为什么需要这一层**：该模型不能按常规"接模型"的方式使用 —— 用 `chat/completions` 协议调它**会直接 400**（实测原文：`typesafe/jev-1.13 is a decisions model and cannot be used with the chat/completions endpoint`）。所以"在模型下拉框里选它"这件事本身不成立，必须有一层把它包成可用的工具。

### 脱敏说明

- **不含任何密钥**：key 只在运行时从环境变量 `OPENROUTER_API_KEY` 读取，不写盘、不进日志、不进报错
- **不含真实业务数据**：`examples/` 与 `registry/` 中的数据均为构造的示例值
- **不含个人路径、账号标识、客户可识别信息**

---

## 这个项目解决什么问题

决策模型和聊天模型是两种东西：

| | 聊天模型 | 决策模型 |
|---|---|---|
| 输入 | 消息 | `state`（素材）+ `questions`（声明式问题） |
| 输出 | 文本 | 类型化答案（选择 / 分数 / 是-否概率）+ 置信度 |
| 用途 | 写、聊、推理 | 分流、打标、门禁、评分、路由 |
| 能不能当"模型"接进 IDE | 能 | **不能** —— 用 `chat/completions` 协议调它会直接 400 |

直接暴露 `model_raw_api(state, questions)` 有三个问题：① 调用方得懂它一堆坑；
② 模型成了硬依赖，换模型要改所有调用点；③ 没人会在调用点做置信度门控。

**这一层解决这三件事。**

```
调用方（Agent / RPA / 脚本）
      │  decide("ad_keyword_action", {…业务字段…})
      ▼
决策层                    返回 结论 + 置信度 + 门控(auto|review)
      │
注册表                    字段白名单 + 问题定义 + 每动作阈值 + 硬约束
      │
适配层                    后端可替换（默认 Jev / OpenRouter）
```

---

## 功能

**决策层**
- 对外唯一入口 `decide(决策名, 业务上下文)` —— 调用方看不到底层模型
- **`state` 按注册表声明的字段白名单裁剪**，被裁掉的字段在返回的 `trimmed` 里列出
- **门控在本层完成**：对外只给 `gate=auto|review`；原始概率要显式 `debug=True` 才给
- **硬约束 `guards`**：注册表可声明高危信号（如"下一步动作不可逆"），命中即强制转人工；
  只允许收紧、不允许放宽
- 缺字段 / 注册表不合法 / 后端非 200 一律显式抛 `DecisionError`，不静默降级
- 对可重试状态码做退避重试

**注册表（不用改代码就能加决策）**
- `registry/*.json` 一份文件 = 一个决策
- 声明：字段白名单、三种问题、按动作的阈值、硬约束

**接入壳（都是薄壳，核心只写一份）**
- `mcp_server.py` —— MCP stdio 服务，工具名 `list_decisions` / `decide`（**不带底层模型名**）
- `decision.py` 自带 CLI —— `list` / `show` / `decide`

**质量**
- 28 项离线单元测试，**不需要 API key、不联网**（CI 就靠它）
- CI 覆盖 Python 3.10 / 3.12 / 3.13
- 零第三方依赖

---

## 项目结构

```
decision.py                 核心层：注册表装载 / 裁剪 / 门控 / 硬约束 / 适配层
mcp_server.py               MCP 壳（工具：list_decisions、decide）
registry/                   决策注册表（一份 JSON = 一个决策）
  ├── ad_keyword_action.json    广告关键词下一步动作（中文）
  ├── browser_step.json         浏览器/桌面自动化的风险闸门（中文，演示 guards）
  └── support_triage.json       客服分流（英文）
examples/
  ├── quickstart.py             三个可直接跑的场景
  └── context_ad_keyword.json   示例输入
tests/test_offline.py       离线单元测试
```

---

## 30 秒上手

```bash
# 1) 只需要一个 key（本仓库任何文件都不含密钥）
export OPENROUTER_API_KEY="sk-or-v1-..."
#   Windows PowerShell:  $env:OPENROUTER_API_KEY = "sk-or-v1-..."

# 2) 看有哪些决策
python decision.py list

# 3) 跑示例
python examples/quickstart.py

# 4) 跑测试（不需要 key）
python -m unittest discover -s tests -v
```

作为库：

```python
from decision import decide

# 注意：需要计算的值先自己算好 —— 这个模型不做算术、计数也不可靠
r = decide("ad_keyword_action", {
    "目标ACOS": 0.30, "关键词": "car phone holder magnetic", "匹配方式": "widened",
    "曝光": 1840, "点击": 11, "花费": 6.85, "销售额": 0.0, "订单": 0,
    "运行天数": 9, "当前出价": 0.62, "实测ACOS": "无成交",   # ← 代码算好的
})

if r["gate"] == "auto":
    apply(r["outcome"])
else:
    queue_for_review(r)      # 低置信度，或命中了硬约束
```

返回：

```json
{
  "decision": "ad_keyword_action",
  "outcome": "pause",
  "confidence": 0.35,
  "gate": "review",
  "signals": { "无效花费": 0.76, "紧迫度": 1.5 },
  "trimmed": [],
  "elapsed_ms": 1637,
  "usage": { "input_tokens": 595, "output_tokens": 95, "cost": 0.00002499 },
  "model": "typesafe/jev-1.13-20260917",
  "version": "0.1.0"
}
```

---

## 三个设计取舍（都来自实测，不是拍脑袋）

**1. 字段白名单就是抗噪器。**
本地实测：同一判断，把 `state` 从 630 tokens 加到 26,200 tokens（41 倍），**答案不变**，
但置信度在清晰案子里 **+0.09**、在模糊案子里 **−0.33**。
无关内容不降智，"降"的是你对结果的判断力。所以白名单之外一律裁掉。

**2. 门控在本层完成。**
对外只给 `gate`，原始概率要显式 `debug=True`。因为置信度这么敏感，裸给调用方等于害人。

**3. 硬约束只能收紧不能放宽。**
有些判断不能只看置信度。示例里客服分流的 `billing` 置信度能到 **1.00**，
但只要 `wants_refund > 0.6`，就必须转人工 —— 路由自动化不该自己回答钱的问题。

---

## 接进 Agent（MCP）

```json
{
  "mcpServers": {
    "decision-layer": {
      "command": "python",
      "args": ["/absolute/path/to/jev-decision-layer/mcp_server.py"],
      "env": { "OPENROUTER_API_KEY": "sk-or-v1-..." }
    }
  }
}
```

不需要 MCP 客户端也能自测：`python mcp_server.py --selftest`

---

## 写一个新决策

在 `registry/` 放一个 JSON 即可，**不用改代码**：

```json
{
  "name": "ticket_priority",
  "description": "工单优先级排序",
  "primary": "优先级",
  "state_fields": ["标题", "正文", "客户等级"],
  "default_threshold": 0.7,
  "thresholds": { "高": 0.85, "中": 0.7, "低": 0.5 },
  "guards": [
    { "signal": "涉及金额", "op": ">", "value": 0.6, "then": "review",
      "why": "涉及金额的判断一律人工复核" }
  ],
  "questions": {
    "优先级": {
      "type": "choice",
      "instructions": "这条工单应该排在哪一档",
      "criteria": { "高": "影响可用性", "中": "影响体验", "低": "咨询类", "other": "都不合适" }
    },
    "涉及金额": { "type": "noul", "instructions": "这条工单涉及退款或赔付" }
  }
}
```

**三种问题原语**（就这三种）：

| type | 问什么 | `criteria` 形状 | 返回 |
|---|---|---|---|
| `choice` | 从你声明的选项里选一个 | **对象** `{key: 说明}` | 选项 + 概率分布 + 置信度 |
| `score` | 在有序标尺上打分 | **数组**（顺序 = 刻度） | 分数（可落两档之间）+ 概率 + 置信度 |
| `noul` | 一个是/否命题 | 可省略 | "是"的概率 0–1（**没有**置信度字段） |

**一定要带 `other` 选项**，否则模型只能在你给的选项里挑个最不坏的。
详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

---

## 别交给它做的事

| 别交 | 为什么 |
|---|---|
| 算术、计数、百分比、差值 | 官方明说"不是计算器"，且**计数不可靠、误差随规模增长** |
| 日期先后与天数 | 日期被当文本读，不当有序量 |
| 生成文本、写文案 | 不生成文本 |
| 开放式推理、多跳、复合判断 | 间接层级越多越不准；要求**一句话一个判断** |
| 看截图、看图 | 仅文本输入，页面状态必须你自己文本化 |
| 拿 `score` 插值还原具体数值 | 官方称其 score 层级"数值校准很弱" |
| 把 `noul` 和 `choice` 的数互相换算 | 同题两者可差 20 倍以上 |

---

## 已知边界

- **阈值不是常量。** 实测同一判断、不同 `state` 形状，置信度可偏 ±0.33 →
  **阈值必须在你自己的数据上标定**，换 `state` 结构要重标。
- **中文可用但不是最优。** 底层模型官方写明英文准确率最高，CJK 等其它语言
  "handled but not equally well"，要求"在你的数据上自测"。
- **上下文 64k/请求**，其中 `state` + 单条最长问题 ≤ 32k。**32k 是硬上限不是推荐值。**
- **速率限制** 250,000 tokens/秒、1,200 请求/分钟，超任一即 429。
- **`state` 是数据不是指令。** 底层模型不把 `state` 当敌意内容处理 → 见 [SECURITY.md](SECURITY.md)。
- **本层不做鉴权、配额、审计**；业务幂等、回滚、审批都在你的代码里。

---

## 贡献与反馈

**Issue 与 PR 均接受。**

- **新增一个决策** → 直接提 PR：在 `registry/` 加一个 JSON 即可，不用改代码
- 提交前读 [CONTRIBUTING.md](CONTRIBUTING.md)（含自查清单与"什么会被拒"）
- Bug / 新功能 → 用对应的 issue 模板
- **安全漏洞或密钥泄露 → 不要开公开 issue**，走 [SECURITY.md](SECURITY.md) 的私密渠道
- 参与即视为同意 [行为准则](CODE_OF_CONDUCT.md)

---

## 基于什么

| 项 | 说明 |
|---|---|
| 调用平台 | OpenRouter（decisions 端点） |
| 模型代号 | `typesafe/jev-1.13`，厂商标识 `TypeSafe` |
| 本项目 | 独立的第三方封装层，**不是** TypeSafe 官方项目，也**未**获得其背书 |
| 运行时 | Python 3.10+，仅标准库 |
| 许可 | MIT |

对底层模型的接口事实、实测数据与局限，见 `registry/*.json` 的 `notes` 字段与本文档各节。

## 依赖与许可

- 仅 Python 标准库（3.10+），**无第三方依赖**
- MIT License，见 [LICENSE](LICENSE)
- 变更记录见 [CHANGELOG.md](CHANGELOG.md)
