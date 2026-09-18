# jev-decision-layer

把决策模型包成**业务决策工具**：调用方只说"要做什么判断"，不说"用哪个模型"。

> ⚠️ **非官方项目。** 本项目是第三方封装，与 TypeSafe AI 无隶属关系。底层默认调用 `typesafe/jev-1.13`（TypeSafe 的 "System One" 决策模型）。

---

## 为什么需要这一层

决策模型（如 Jev）和聊天模型是两种东西：

| | 聊天模型 | 决策模型 |
|---|---|---|
| 输入 | 消息 | `state`（素材）+ `questions`（声明式问题） |
| 输出 | 文本 | 类型化答案（选择/分数/是-否概率）+ 置信度 |
| 用途 | 写、聊、推理 | 分流、打标、门禁、评分、路由 |
| 能不能当"模型"接进 IDE | 能 | **不能** —— 用 `chat/completions` 协议调它会直接 400 |

直接暴露 `model/model_raw_api(state, questions)` 有三个问题：① 调用方得懂它一堆坑；② 模型成了硬依赖，换模型要改所有调用点；③ 没人会在调用点做置信度门控。

**这一层解决这三件事。**

```
调用方（Agent / RPA / 脚本）
      ↓  decide("ad_keyword_action", {…业务字段…})
决策层          返回 结论 + 置信度 + 门控(auto|review)
      ↓
注册表          字段白名单 + 问题定义 + 每动作阈值 + 硬约束
      ↓
适配层          后端可替换（默认 Jev / OpenRouter）
```

三个设计都来自实测，不是拍脑袋：

1. **字段白名单就是抗噪器。** 本地实测：同一判断，把 state 从 630 tokens 加到 26,200 tokens（41 倍），答案不变，但**置信度在清晰案子里 +0.09、在模糊案子里 −0.33**。无关内容不降智，"降"的是你对结果的判断力。所以白名单之外一律裁掉，并在返回里列出 `trimmed`。
2. **门控在本层完成。** 对外只给 `gate: auto|review`，原始概率要显式 `debug=True` 才给 —— 因为置信度这么敏感，裸给调用方等于害人。
3. **硬约束（guards）只能收紧不能放宽。** 有些判断不能只看置信度：客服分流的 `billing` 置信度能到 **1.00**，但只要 `wants_refund > 0.6`，就必须转人工。把这类不变量写进注册表，纪律才变成机制。

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

## 接进 Agent（MCP）

工具名刻意**不带底层模型名**：agent 看到的是 `list_decisions` 和 `decide`。

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

在 `registry/` 放一个 JSON 即可，不用改代码：

```json
{
  "name": "ticket_priority",
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
      "criteria": { "高": "影响可用性", "中": "影响体验", "低": "咨询类" }
    },
    "涉及金额": { "type": "noul", "instructions": "这条工单涉及退款或赔付" }
  }
}
```

**三种问题原语**（就这三种，没有别的）：

| type | 问什么 | `criteria` 形状 | 返回 |
|---|---|---|---|
| `choice` | 从你声明的选项里选一个 | **对象** `{key: 说明}` | 选项 + 概率分布 + 置信度 |
| `score` | 在有序标尺上打分 | **数组**（顺序 = 刻度） | 分数（可落两档之间）+ 概率 + 置信度 |
| `noul` | 一个是/否命题 | 可省略 | "是"的概率 0–1（**没有**置信度字段） |

**一定要带 `other` 选项**，否则模型只能在你给的选项里挑个最不坏的。

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

- **阈值不是常量。** 实测同一判断、不同 state 形状，置信度可偏 ±0.33 → **阈值必须在你自己的数据上标定**，换 state 结构要重标。
- **中文可用但不是最优。** 官方写明英文准确率最高，CJK 等其它语言"handled but not equally well"，要求"在你的数据上自测"。
- **上下文 64k/请求**，其中 `state` + 单条最长问题 ≤ 32k。**32k 是硬上限不是推荐值**。
- **速率限制** 250,000 tokens/秒、1,200 请求/分钟，超任一即 429。
- **本层不做重试以外的可靠性**：它只做一次判断，业务幂等、审计、回滚都在你的代码里。

## 依赖与许可

- 仅 Python 标准库（3.10+），无第三方依赖
- MIT License
