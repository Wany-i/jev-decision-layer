# Jev 广告关键词决策 —— 状态设计与实测

> 本文档由 **AI 进行调研、整理与提交**（2026-09-19）。证据分级与出处见文内标注；非官方材料，与模型厂商无隶属关系。

**日期**：2026-09-19　**依据**：官方 `model-jaggedness/jev-1.13`、`confidence`、`concepts/state` 三页原文 + 本机 40 次实测
**定位**：把前面三轮的调研，落成"广告优化 skill 里 Jev 这一层具体怎么写"

---

## 0. 入口

| 优先级 | 文件 | 一句话 |
|---|---|---|
| **必读** | `docs/Jev广告关键词决策-状态设计与实测.md` | 本文件：state 该给什么 / 问题怎么写 / 阈值怎么定 |
| **参考** | `docs/示例\jag_context_rot.py` | 实测脚本，`--case clear\|ambiguous`，可换成你的真实数据复跑 |
| **参考** | `docs/jev_client.py` | 决策层封装（含 `gate()` 门控） |
| **留档** | `docs/Jev外网用法调研.md` · `Jev模型使用调研.md` · `Jev接入指南-IDE浏览器与运行环境.md` | 前三轮：外网用法 / 接口契约 / 接入方式 |

---

## 1. 三行结论

1. **别塞全量数据。** 不是"怕超窗口"，是**每一行无关数据都在扭曲你的置信度**（实测：同一判断，只是把 26k tokens 的无关内容加进去，置信度在清晰案子里 **+0.09**、在模糊案子里 **−0.33**）。
2. **选项本身很稳，别担心它选错标签。** 两个案例、各 5 次重复，加入无关内容后**选中的动作 10/10 不变**。真正不稳的是 `confidence`。
3. **阈值必须在"你实际会发的 state 形状"上调**，换了 state 结构就要重标 —— 这是外网那份"ECE 校准审计为负"的机制解释。

---

## 2. 官方承认的 9 类失败模式（逐条对照广告场景）

来源：`docs.typesafe.ai/model-jaggedness/jev-1.13`（最后复核 2026-09-17）

| # | 官方失败模式 | 会不会咬到广告场景 | 该怎么办 |
|---|---|---|---|
| 1 | **字面理解** —— 答你写的问题，不是你想的那个 | ⚠️ 会 | 条件写死在 `instructions`，边界情况写进 `criteria`。"你事后解释的那句话，就是 instructions 缺的那一半" |
| 2 | **数学与数字** —— "不是计算器"，**并且不可靠计数**，误差随规模增长 | 🔴 **一定会** | **ACOS / CTR / CVR / 差值 / 百分比，全部在代码里算好再传** |
| 3 | **日期时间比较** —— 把日期当文本读，不当有序量 | ⚠️ 会（7 天/14 天/环比） | 日期分量用 `choice` 抽取，排序与差值在代码里做 |
| 4 | **多级间接** —— 双重否定、多跳推理 | ⚠️ 会 | 一句话一个判断，别叠 |
| 5 | **state 塞满无关细节** —— "**Jev suffers from context rot**"，无关材料直接吃掉准确率 | 🔴 **一定会** | **先检索、先裁剪，只给这个问题需要的字段** |
| 6 | **对抗性内容** —— state 被当成数据，不默认当敌意 | ⚠️ 会（商品标题/买家消息可能带指令） | criteria 写精确；上量前测边界 |
| 7 | **instructions 与 criteria 互相矛盾** | ⚠️ 会 | 把 criteria 当成 instruction 的延伸，对齐口径 |
| 8 | **结构不变量不成立** | 🔴 会（别指望 `noul` 和 `choice` 的数能换算） | **一个判断只用一种问法**；恒等式在代码里守 |
| 9 | **生成** —— 不生成文本 | ✅ 不影响 | 本来就不该用它写文案 |

**官方原话（值得记住）**：
> "Ask each decision one way; enforce identities in code."
> "Giving it more context in `state` than the question needs... unrelated material in the `state` costs you accuracy."

---

## 3. 核心实测：state 该给多少（40 次调用）

**设计**：同一个关键词、同一组三个问题，逐档往 `state` 里加**真实但与本判断无关**的内容，每档重复 5 次。

| 档位 | 大约 tokens | clear 案例（高花费零成交） | ambiguous 案例（有成交但 ACOS 超目标） |
|---|---|---|---|
| **L0** 只给所需字段 | ~630 | pause 5/5 · conf **0.57** | lower 5/5 · conf **0.85** |
| L1 +多余报表列 | ~750 | pause 5/5 · conf 0.60 | lower 5/5 · conf 0.63 |
| L2 +同组 30 词 | ~3.9k | pause 5/5 · conf 0.62 | lower 5/5 · conf 0.52 |
| L3 +全店 120 词 | ~16.5k | pause 5/5 · conf 0.64 | lower 5/5 · conf 0.55 |
| **L4** +其它店铺干扰 | **~26.2k** | pause 5/5 · conf **0.66（+0.09）** | lower 5/5 · conf **0.52（−0.33）** |

**读出来的三件事**：

**① 选中的动作极稳。** 两个案例、每档 5 次、state 从 630 涨到 26,200 tokens（**41 倍**），**选中的答案一次都没变**。→ 拿它做分流/打标是可靠的。

**② 但 `confidence` 会大动，而且方向取决于案子清晰不清晰：**
- **清晰案子 → 虚高**（+0.09）：噪声给它制造了没有根据的自信 → 你会**把本该复核的判断自动执行**。
- **模糊案子 → 崩**（−0.33）：本来 0.85 的明确把握被噪声淹没 → 你会**把本该执行的判断推进人工队列**。

两种方向都在毁你的自动化率，而且你看不出来 —— 因为置信度本身就是你以为用来判断"该不该信"的那个数。

**③ 这解释了外网那份校准审计为什么是负的**（ECE 0.154 差于 Claude Haiku 4.5 的 0.097）：置信度对无关上下文如此敏感，**任何跨 state 形状通用的阈值都站不住**。

**诚实边界**：合成数据、每案例 1 个关键词、每档 5 次、单一模型版本（`jev-1.13-20260917`）。这是**机制证据，不是统计结论**。你的真实数据必须自己复跑：
```bash
python "docs/示例/jag_context_rot.py" --case clear --reps 5
```

---

## 4. state 模板（广告关键词判断）

**官方口径**：*"Think of state as the material you would present to a panel of experts before asking them to make a judgment."*
**官方建议**：用对象（每个字段有名字、关系清楚），并把**答案需要的部分放一起**。

### ✅ 该给（精简版，实测 ~630 tokens）

```json
{
  "店铺": "示例店铺A",
  "站点": "US",
  "品类": "汽车手机支架",
  "目标ACOS": 0.30,
  "本次判断对象": {
    "关键词": "car phone holder magnetic",
    "匹配方式": "widened",
    "曝光": 1840,
    "点击": 11,
    "花费": 6.85,
    "销售额": 0.0,
    "订单": 0,
    "运行天数": 9,
    "当前出价": 0.62,
    "实测ACOS": "无成交"
  }
}
```

**关键点**：`实测ACOS` 是**代码算好的**，不是让模型去算 —— 官方明说它不是计算器、且**不可靠计数**。

### 🚫 不该给

| 别给 | 为什么 |
|---|---|
| 全店/全组关键词列表 | 实测让置信度 **±0.33 失真** |
| 其它店铺的数据 | 同上，纯干扰 |
| 一整个 Excel 导出的原始行 | 官方点名 "state 塞满无关细节" 是失败模式 #5 |
| 让它自己算 ACOS/CTR/差值 | 失败模式 #2：算术与计数都不该给模型 |
| 把日期当文本让它比先后 | 失败模式 #3 |

### 如果确实没法在代码里过滤
官方给了个兜底：**用一个 `noul` 先做相关性过滤**（问"这段材料跟本次判断相关吗"），代码据此裁掉不相关的再发第二次。官方有 `classifying_rag_passages` cookbook 做这件事。

---

## 5. questions 模板（对照官方避坑）

```json
{
  "动作": {
    "type": "choice",
    "instructions": "按目标 ACOS 口径，这个词下一步最该做的动作是哪一个",
    "criteria": {
      "raise":  "提高出价以抢更多流量",
      "lower":  "降低出价",
      "pause":  "暂停投放该词",
      "keep":   "保持现状继续观察",
      "negate": "加为否定词",
      "other":  "以上都不合适"
    }
  },
  "无效花费": { "type": "noul", "instructions": "该词到目前的花费已经属于明显的无效支出" },
  "紧急度": {
    "type": "score",
    "instructions": "处理这个判断的紧迫程度",
    "criteria": ["放着不管", "本周内处理", "今天就该处理"]
  }
}
```

设计要点，逐条对着官方文档：

| 要点 | 官方依据 |
|---|---|
| `criteria` 里的 `other` **必须留** | 否则模型只能在给定选项里挑个最不坏的（也正是"state 空时它答 other 0.75"那种诚实的兜底） |
| **一句话一个判断**，别把"该不该降价、该不该加否词"合成一题 | "Ask each decision one way"；复合问题会被拆错 |
| **判断标准写进 `instructions`，不要写进 `state`** | 实测：只删掉 instructions 里的口径，`noul` 从 0.59 变 0.33 |
| **别把金额/阈值算给它** | 失败模式 #2：算术在代码里 |
| 别用 `score` 去插值还原具体数值 | 官方："score levels are weak in numerical calibration" |
| **同一个判断只用一种问法** | 失败模式 #8：同题 `noul` 与 `choice` 的数不能换算（官方例 0.22 vs 0.01；两 `noul` 相加 1.19） |
| 中文可写、但**必须自测** | 官方："English is the primary training language... CJK scripts are handled but not equally well; test on your own content" |

---

## 6. 代码侧必须自己算的（别交给它）

| 事项 | 在代码里 |
|---|---|
| ACOS / CTR / CVR / 环比 / 差值 | 算完把**结果或命名分档**塞进 state（"实测ACOS: 0.449" 或 "偏高/正常"） |
| 计数（有多少个词超阈值） | 代码循环 + 每个词一个问题，然后自己加总（官方给了范式） |
| 日期先后 / 天数 / 周几 | 代码算，别让它比 |
| 阈值判断、排序、批量动作的副作用 | 全在代码里，模型只出"语义判断" |

---

## 7. 置信度门控：怎么写才不会翻车

**官方三段式**（原文）：高置信度 → 自动执行；中 → 谨慎推进/请人确认；低 → **不要行动**，转人工或澄清。
**官方也明确**：*"A confidence threshold is not one number. Different actions within the same system should be gated at different levels depending on the consequences of getting it wrong."*

```python
action = resp["answers"]["动作"]
conf = action["confidence"]
pick = action["choice"]

if conf < 0.50:                      # 模型自己说没把握 -> 别猜
    route_to_human()
elif pick == "keep":                 # 低风险：错了只是少赚
    apply(pick)
elif pick == "negate":               # 中风险：错了少拿流量，可回收
    apply(pick) if conf > 0.70 else queue_for_review(pick)
elif pick == "pause":                # 高风险：错了直接丢流量
    apply(pick) if conf > 0.90 else queue_for_review(pick)
```

**两条本次实测带来的硬约束**：
1. **阈值必须在"你实际会发的 state 形状"上调**。实测同一判断、不同 state 规模，置信度能差 0.33。
2. **上线前先做影子测试**：旁路跑，和 v3.14 规则的人工判断比对，**扫多个阈值**看准确率/覆盖率曲线，再定数。这一步不可跳过 —— 上面那个 ±0.33 就说明拍脑袋定的阈值不可靠。

---

## 8. 下一步（我的建议，等你定）

1. **影子对照表**：挑 20–50 个真实关键词（**用你导出的真实数据，不是合成数据**），Jev 跑一遍 vs v3.14 规则的人工判断，产出准确率/覆盖率曲线。**这是进 skill 的前置条件。**
2. **state 裁剪器**：一个小函数，从你的广告导出里抽出第 4 节那 10 个字段 —— 这是"过滤在代码里做"的落地物。
3. **阈值表**：把每个动作的 `confidence` 阈值写进配置，而不是散在代码里（换模型版本/换 state 形状时只改这张表）。

---

## 附：复跑

```bash
P=/c/Users/WY/.workbuddy/binaries/python/versions/3.13.12/python.exe
S="docs/示例/jag_context_rot.py"

$P "$S" --case clear     --reps 5          # 清晰案子
$P "$S" --case ambiguous --reps 5          # 模糊案子
$P "$S" --case ambiguous --levels 0,1,2,3,4 --reps 3   # 看全档曲线
```
换成你的真实数据：改 `示例\jag_context_rot.py` 里的 `CASES` 与 `KB` 即可。
