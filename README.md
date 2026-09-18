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

一句话：**调用方只说"要做什么判断"，不说"用哪个模型"。**

### 决策层（`decision.py`）

| 功能 | 说明 |
|---|---|
| **唯一入口** `decide(决策名, 业务上下文)` | 调用方看不到底层模型；换后端时调用代码零改动 |
| **字段白名单裁剪** | `state` 只放注册表声明的那几个字段，其余一律裁掉，裁掉了哪些在返回的 `trimmed` 里列出 |
| **缺字段即报错** | 需要计算的值（比例、差值、计数）必须由调用方先算好；本层不替它算，也不静默填空 |
| **置信度门控** | 在本层完成，对外只给 `gate`；原始概率要显式 `debug=True` 才给 |
| **硬约束 `guards`** | 注册表可声明高危信号（如"下一步动作不可逆"），命中即强制转人工，**只允许收紧、不允许放宽** |
| **显式失败** | 注册表不合法、字段缺失、后端非 200 一律抛 `DecisionError`，不静默降级 |
| **退避重试** | 对 429 / 5xx（`RETRYABLE`）重试，其它状态码直接报错 |

### 注册表（`registry/*.json`）—— 加决策不用改代码

一份 JSON = 一个决策，声明四件事：

1. **`state_fields`** —— 该决策需要哪些字段（白名单，也是抗噪器）
2. **`questions`** —— 要问什么，三种原语 `choice` / `score` / `noul`
3. **`thresholds`** —— **按动作分别定**的放行阈值
4. **`guards`** —— 不看置信度、命中即转人工的硬约束

### 接入壳（都是薄壳，核心逻辑只写一份）

| 壳 | 形态 | 工具名 |
|---|---|---|
| `mcp_server.py` | MCP stdio 服务（手写 JSON-RPC，无依赖） | `list_decisions` / `decide`（**不带底层模型名**） |
| `decision.py` CLI | 命令行 | `list` / `show` / `decide` |

### 质量

- **28 项离线单元测试，不需要 API key、不联网** —— CI 就靠它
- CI 覆盖 Python 3.10 / 3.12 / 3.13
- **零第三方依赖**（仅标准库）

---

## 上游实现逻辑：一次 `decide()` 到底走了哪里

上一节说的是"有什么"，这一节说的是"它是怎么转起来的"。
**关键点在于：本层做的每一步，都对应上游模型的一个真实限制。**

### 全景

```
调用方（Agent / RPA / 脚本 / CLI）
   │   decide("ad_keyword_action", {…业务字段…})
   ▼
① 装载注册表   registry/ad_keyword_action.json
   │           → state_fields / questions / thresholds / guards
   ▼
② 裁剪上下文   context ──(只保留 state_fields)──▶ state
   │                                        └──▶ trimmed（被裁掉的字段名）
   ▼
③ 组装请求体   {"model": …, "state": state, "questions": questions}
   │           ← 顶层就这三个字段，不套 input 外壳
   ▼
④ 发往上游     POST https://openrouter.ai/api/alpha/decisions
   │           Header: Authorization: Bearer $OPENROUTER_API_KEY
   │           ← 是 decisions 端点，不是 chat/completions
   ▼
⑤ 收答案       answers 里每个问题一条，三类原语之一
   │
   ▼
⑥ 抽主结论     primary 问题 → outcome + confidence
   │           其余问题   → signals（供硬约束判读）
   ▼
⑦ 门控         按【选中的那个动作】取阈值 → auto / review
   ▼
⑧ 硬约束       逐条比对 guards，命中即强制 review（只收紧）
   ▼
调用方  { outcome, confidence, gate, signals, … }
```

### 逐段说明（以及每一步为什么必须存在）

**① 装载注册表 —— 业务规则不写在代码里。**
代码只认机制，不认业务。校验三件事：`state_fields` / `questions` / `primary` 必须存在，且 `primary` 必须是 `questions` 里的一个。

**② 裁剪上下文 —— 这一步是抗噪器，不是省 token。**
注册表声明该决策需要哪些字段，其余全部剔除。实测：同一判断，把 `state` 从 630 tokens 加到 26,200 tokens 的**无关内容**，
答案不变，但置信度在清晰案子里偏高 0.09、在模糊案子里偏低 0.33。
**无关内容不会让它答错，会让它"没有根据地自信"** —— 而置信度正是你以为用来判断该不该信的那个数。裁掉哪些字段会记在 `trimmed` 里，可核对。

**③ 组装请求体 —— 顶层就是 `model` / `state` / `questions`。**
不套 `input` 外壳（套了上游读不到 `state` 与 `questions`，直接 400）。

**④ 发往上游 —— 走 decisions 端点。**
同一个模型**不能**用 `chat/completions` 协议调用（会 400，原文见上文「背景」）。
key 只从环境变量 `OPENROUTER_API_KEY` 读，放在请求头，**不落在任何文件、日志或报错里**。

**⑤ 收答案 —— 上游返回的是类型化答案，不是文本。**
`answers` 里按问题名逐条返回，形状取决于问题类型（`choice` / `score` / `noul`）。

**⑥ 抽主结论 —— 一个决策只有一个"结论"，其余是"信号"。**
`primary` 指定的那个问题决定 `outcome`；其余问题（如"是否不可逆""涉及金额"）折算成 `signals`，
它们不参与结论，只服务于下一步的硬约束。

**⑦ 门控 —— 阈值按选中动作取，不是全局一个数。**
注册表的 `thresholds` 按动作分开（示例里 `keep` 是 0.50，`pause` 是 0.90）——
因为**做错的代价不同**：放着不动只是少赚，暂停投放直接丢流量。
`choice` / `score` 用 `confidence`；`noul` 没有 `confidence` 字段，用"离 0.5 的距离"折算。

**⑧ 硬约束 —— 有些判断不能只看置信度。**
示例里客服分流的 `billing` 置信度能到 **1.00**，但只要 `wants_refund > 0.6`，仍然必须转人工 ——
路由自动化不该自己回答钱的问题。把这类不变量写进注册表，等于**把纪律变成机制**。
规则**只能把 `auto` 收紧为 `review`**，反向放宽在代码里被禁止。

### 真实一次调用长什么样

以下三块是同一次调用的原样快照（示例数据、非真实业务），可以直接对着看字段是怎么流的。

**发出去的上游请求体**（key 在 header，不在 body）：

```json
{
  "model": "typesafe/jev-1.13",
  "state": {
    "目标ACOS": 0.3, "关键词": "car phone holder magnetic", "匹配方式": "widened",
    "曝光": 1840, "点击": 11, "花费": 6.85, "销售额": 0.0, "订单": 0,
    "运行天数": 9, "当前出价": 0.62, "实测ACOS": "无成交"
  },
  "questions": {
    "动作": {
      "type": "choice",
      "instructions": "按目标 ACOS 口径，这个词下一步最该做的动作是哪一个",
      "criteria": {
        "raise": "提高出价以抢更多流量", "lower": "降低出价", "pause": "暂停投放该词",
        "keep": "保持现状继续观察", "negate": "加为否定词", "other": "以上都不合适"
      }
    },
    "无效花费": { "type": "noul", "instructions": "该词到目前的花费已经属于明显的无效支出" },
    "紧迫度": {
      "type": "score", "instructions": "处理这个判断的紧迫程度",
      "criteria": ["放着不管", "本周内处理", "今天就该处理"]
    }
  }
}
```

**上游返回的原始响应体**：

```json
{
  "model": "typesafe/jev-1.13-20260917",
  "answers": {
    "动作": {
      "type": "choice", "choice": "pause",
      "probabilities": { "other": 0.01, "keep": 0.05, "negate": 0.05,
                         "pause": 0.46, "raise": 0.01, "lower": 0.42 },
      "confidence": 0.36
    },
    "无效花费": { "type": "noul", "noul": 0.74 },
    "紧迫度": {
      "type": "score", "score": 1.45,
      "legend": { "0": "放着不管", "1": "本周内处理", "2": "今天就该处理" },
      "probabilities": { "0": 0.03, "1": 0.49, "2": 0.48 },
      "confidence": 0.23
    }
  },
  "usage": { "input_tokens": 595, "output_tokens": 95, "cost": 0.00002499 },
  "id": "gen-dec-…",
  "provider": "TypeSafe"
}
```

**本层最终返回给调用方的**：

```json
{
  "decision": "ad_keyword_action",
  "outcome": "pause",
  "confidence": 0.36,
  "gate": "review",
  "signals": { "无效花费": 0.74, "紧迫度": 1.45 },
  "model": "typesafe/jev-1.13-20260917",
  "request_id": "gen-dec-…",
  "elapsed_ms": 1673,
  "usage": { "input_tokens": 595, "output_tokens": 95, "cost": 0.00002499 },
  "trimmed": [],
  "version": "0.1.0"
}
```

### 字段映射：上游给什么，本层留什么

| 上游字段 | 本层输出 | 怎么处理 |
|---|---|---|
| `answers[primary].choice` / `.score` / `.noul` | `outcome` | 按问题类型取对应的那个值 |
| `answers[primary].confidence`（`noul` 则用 `.noul`） | `confidence` | 按类型取 |
| `answers[其它问题]` | `signals` | 取 `noul` 或 `score` 的标量值，供 `guards` 判读 |
| `id` | `request_id` | 改名，用于对账与排障 |
| `usage`（含 `cost`） | `usage` | 原样透出，便于核算 |
| `model` | `model` | 原样透出（实际回答版本号） |
| `answers[*].probabilities` | — | **默认不透出**，只有 `debug=True` 才给 |
| `answers[*].legend` | — | **丢弃**（`score` 的刻度文案） |
| `provider` | — | **丢弃** |
| — | `gate` | **本层计算**：阈值门控 + 硬约束 |
| — | `trimmed` | **本层计算**：被白名单裁掉的字段 |
| — | `elapsed_ms` / `version` | **本层计算** |

### 上游没给你、由本层补上的东西

| 上游不提供 | 本层怎么补 |
|---|---|
| 置信度阈值判断 | 按动作取阈值，折成 `auto` / `review` 两档 |
| 上下文裁剪 | 用注册表 `state_fields` 机械裁剪，并回报 `trimmed` |
| 高危信号拦截 | 注册表 `guards`，命中即强制转人工 |
| 失败重试 | 对 429 / 5xx 退避重试 |
| 错误归一 | 一律折成 `DecisionError`，带上游原文，不静默吞 |
| 稳定的结果 | **补不了** —— 同一输入重复调用，数值会有小波动（实测同一用例两次：`confidence` 0.35 / 0.36，`无效花费` 0.76 / 0.74）。所以**判定必须靠门控，不能靠记结果** |

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
docs/                       调研文档：接口契约、场景清单、实测数据、外网复核
  └── README.md               文档索引与来源声明
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

返回（**同一次调用的完整三段快照见下文**「真实一次调用长什么样」）：

```json
{
  "decision": "ad_keyword_action",
  "outcome": "pause",
  "confidence": 0.36,
  "gate": "review",
  "signals": { "无效花费": 0.74, "紧迫度": 1.45 },
  "trimmed": [],
  "elapsed_ms": 1673,
  "usage": { "input_tokens": 595, "output_tokens": 95, "cost": 0.00002499 },
  "model": "typesafe/jev-1.13-20260917",
  "version": "0.1.0"
}
```

`gate=review` 的含义：`pause` 这个动作的阈值是 0.90，而 `confidence` 只有 0.36 —— **不该自动执行**。

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

## 调研文档

本仓库为什么这么做、阈值从哪来、哪些事不该交给决策模型 —— 都在 [`docs/`](docs/) 里。

- 接口契约与实测数据（端点、请求形状、上下文边界、成本、置信度敏感性）
- 场景清单：它能干什么、不能干什么
- 六路并行调研 + **第四方独立复核**的原始产物（含出处 URL）
- 来源声明与完整索引见 [`docs/README.md`](docs/README.md)

---

## 依赖与许可

- 仅 Python 标准库（3.10+），**无第三方依赖**
- MIT License，见 [LICENSE](LICENSE)
- 变更记录见 [CHANGELOG.md](CHANGELOG.md)
