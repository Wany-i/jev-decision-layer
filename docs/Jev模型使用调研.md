# `typesafe/jev-1.13`（Jev）使用调研 + 连通实测

> 本文档由 **AI 进行调研、整理与提交**（2026-09-19）。证据分级与出处见文内标注；非官方材料，与模型厂商无隶属关系。

**调研与实测日期**：2026-09-19　**执行方**：WorkBuddy　**状态**：✅ 已跑通

---

## 0. 入口（先看这三行）

| 优先级 | 文件 | 一句话 |
|---|---|---|
| **必读** | `docs/Jev模型使用调研.md` | 本文件：它是什么 + 接口形状 + 实测数据 |
| **必读** | `docs/Jev接入指南-IDE浏览器与运行环境.md` | 后续那轮：怎么接进 IDE / 浏览器、要什么环境 |
| **必读（最新）** | `docs/Jev广告关键词决策-状态设计与实测.md` | 落地设计：state 该给什么、问题怎么写、阈值怎么定（含 40 次实测） |
| **参考** | `docs/jev_client.py` | 决策层唯一代码入口（脚本 / MCP / 浏览器共用），`--probe` 即最小连通验证 |

**结论先说**：能连。用你文档里那支 OpenRouter key，`POST https://openrouter.ai/api/alpha/decisions` 返回 **HTTP 200**，中文场景实测 ~1.2 秒/次、每次约 **$0.00002**。
但**它不是一个聊天模型** —— 用 `/chat/completions` 调它会直接 400 报错，这是最容易踩的坑。

---

## 1. 它是什么：决策模型，不是聊天模型

| 项 | 值 |
|---|---|
| 模型 ID | `typesafe/jev-1.13`（别名 `jev-latest`，实际回答版本 `typesafe/jev-1.13-20260917`） |
| 厂商 | TypeSafe AI，2026-09-15 发布，自称首个 "System One" 模型 |
| 输入 / 输出模态 | `text → decisions`（**只进不出文字**） |
| 上下文 | 32,000 tokens（state + 最长那条 question 共享此预算） |
| 价格 | 输入 **$0.042 / 百万 token**，输出**免费** |
| 官方延迟 | 70–500 ms |

**它做的是**：你给它一段状态（state）+ 一组**预先声明好答案范围**的问题（questions），它返回**类型化的选择/分数/概率**——不需要你从自然语言里解析 JSON。

**三种问题原语**：

| 类型 | 问什么 | 返回 | 典型用途 |
|---|---|---|---|
| `choice` | 从你给的选项里选一个 | 选中的 key + 每个选项的概率 + confidence | 分流、路由、打标 |
| `noul` | 一个是/否命题 | 0–1 的概率（= 回答"是"的置信度） | 门禁、判废、是否命中规则 |
| `score` | 在一个有序标尺上打分 | 分数（可落两档之间，如 1.4）+ 概率 + confidence | 紧急度、情绪强度、质量 |

**它不做的**：不写文案、不解释理由、不生成代码、不做开放式规划。答案被**锁死在你声明的范围内**，编不出第四个类别。
→ 所以正确用法是：**Jev 出判断，代码做动作**。阈值、副作用、审计、兜底都在你的代码里。

---

## 2. 怎么调（照抄即可）

**端点**：`POST https://openrouter.ai/api/alpha/decisions`
⚠️ 注意：**没有 `/v1`**。`/api/v1/alpha/decisions` 会 404（我实测过 9 条路径，只有这条通）。

**Headers**：`Authorization: Bearer <key>`、`Content-Type: application/json`

**请求体**（顶层三件，**不套 `input` 外壳**）：

```json
{
  "model": "typesafe/jev-1.13",
  "state":  { "...任意 JSON 对象 / 数组 / 字符串..." },
  "questions": {
    "action": {
      "type": "choice",
      "instructions": "针对这个关键词，下一步最该做的动作是什么",
      "criteria": { "raise_bid": "提高出价", "lower_bid": "降低出价", "pause": "暂停",
                    "keep": "保持观察", "add_negative": "加否定词", "other": "都不合适" }
    },
    "is_waste": { "type": "noul", "instructions": "这个词当前的花费已经属于明显的无效支出" },
    "urgency":  { "type": "score", "instructions": "处理这个词的紧急程度",
                  "criteria": ["可以放着不管", "本周内处理", "今天就该处理"] }
  }
}
```

**响应**：

```json
{
  "model": "typesafe/jev-1.13-20260917",
  "answers": {
    "action":   { "type": "choice", "choice": "lower_bid",
                  "probabilities": {"lower_bid":0.46,"keep":0.09,"add_negative":0.17,"other":0.03,"pause":0.24,"raise_bid":0.01},
                  "confidence": 0.36 },
    "is_waste": { "type": "noul", "noul": 0.5 },
    "urgency":  { "type": "score", "score": 0.9,
                  "legend": {"0":"可以放着不管","1":"本周内处理","2":"今天就该处理"},
                  "probabilities": {"0":0.24,"1":0.62,"2":0.14}, "confidence": 0.44 }
  },
  "usage": { "input_tokens": 603, "output_tokens": 96, "cost": 2.5326e-05 },
  "id": "gen-dec-1789752507-MJVDxIpnUJJmw66UKZ9T",
  "provider": "TypeSafe"
}
```

**三个字段必须一起读，不能只看答案**：
- `probability` = 模型对各选项的信念分布；
- `confidence` = 分布有多"尖"。**confidence 低 = 它自己也没把握**（上面 `action` 的 0.36 就是"candidates 咬得很紧"）；
- 工程写法：`confidence` 高于阈值 → 自动执行；低 → 转人工/转大模型复核。

**一个请求里塞多个问题几乎不加钱**（并行评估），所以**多问几个判据比反复调一次更划算**。

---

## 2.5 输入/输出的精确契约（2026-09-19 补测，全部一手实测）

### 输入：只有三个顶层字段，且**全部必填**

| 字段 | 必填 | 是什么 | 你要给的三类信息各自落在哪 |
|---|---|---|---|
| `model` | ✅ | 用哪个模型 | —— |
| `state` | ✅ | **给它看的素材**（可以是字符串 / 对象 / 数组，三种都实测通过） | **背景信息（知识库）+ 场景信息，都放这里** |
| `questions` | ✅ | **给它出的题**（`名字 → 问题定义` 的映射） | 判断标准放 `instructions`；**选项放 `criteria`** |

**关键区分（最容易混、混了直接改变答案）**：
- `state` = 「看什么」（事实与素材）
- `questions[].instructions` = 「按什么口径判」（**不是问题的措辞，是判断标准**）
- `questions[].criteria` = 「可选的答案空间」（**声明式**：答案被锁死在你声明的范围内，编不出第四项）

### 输出：顶层五个字段 + answers 里三种形状

顶层：`model` · `answers` · `usage` · `id` · `provider`

| 问题类型 | 返回字段 |
|---|---|
| `choice` | `choice`（选中的 key）+ `probabilities`（每项概率）+ `confidence` |
| `score` | `score`（**可落两档之间**，如 1.48）+ `legend`（档位文案）+ `probabilities` + `confidence` |
| `noul` | `noul`（回答"是"的概率 0–1）—— **没有 confidence 字段**，概率本身就是信念 |

### 三组对照实测：背景信息该给多少

同一份关键词数据、同一组问题，只改 `state` 与 `instructions`：

| 组 | 做法 | 动作 | 无效花费(noul) |
|---|---|---|---|
| **A** | 精简背景（只给本次判断相关字段） | pause 0.62 / conf 0.55 | 0.68 |
| **B** | A + 一大段**无关**公司背景（约 380 token） | pause 0.63 / conf 0.55 | **0.80 ↑** |
| **C** | **只给无关背景，不给本次判断数据** | **lower 0.63（答案翻转）** | **0.29 ↓**，`other` 升到 0.24 |

另有一组（同一 state，只把"按目标 ACOS 口径"这句判断标准从 `instructions` 里删掉）：`noul` 从 **0.59 变 0.33**。

**三条推论**：
1. **决定答案的是「本次判断相关的数据」，不是「背景知识」**。C 组背景给了一大段，答案照样翻转、信念腰斩。
2. **无关内容不会让它变笨，会让它变得没有根据地自信** —— B 组答案没变，但 `noul` 从 0.68 涨到 0.80。这比"掉准确率"更危险。
3. **判断标准必须写进 `instructions`**。同一份数据，换个问法口径，数值能差一倍。

### 报错契约（缺什么会怎样，全是实测原文）

| 情形 | 结果 |
|---|---|
| 不传 `state` | **400** `invalid_union`：期望 `string` / `record` / `array` |
| `state` 传空对象 `{}` | **200 但答 `other` 0.75** —— 它会说"都不合适"，**这是信息不足的兜底信号，别当正常结果用** |
| `choice` 不传 `criteria` | **400** `expected record, received undefined`，path = `questions.<名>.criteria` |
| `type` 写成别的值 | **400** 明确列出：`'noul' \| 'choice' \| 'score'` |
| 请求体套 `input` 外壳 | **400** `invalid_union`（顶层读不到 `state`/`questions`） |

### 另外两条边界
- **没有记忆**：每轮都要重发背景；想延续上下文，**自己把上一轮结论塞进新的 state**。

### 上下文窗口（官方原文 + 我的边界实测，两相吻合）

官方 `docs.typesafe.ai/models.md` 原文：
> **Context length**: `64k tokens per request; 32k tokens for state plus the longest question`
> *"The 64k budget covers the `state` plus all questions combined; the 32k budget applies to the `state` plus the single longest question."*

| 项 | 值 | 来源 |
|---|---|---|
| **总预算** | **64,000 tokens / 请求**（`state` + **全部问题**合计） | `[官方原文]` |
| **子预算** | **32,000 tokens**（`state` + **单条最长问题**） | `[官方原文]` |
| OpenRouter 暴露值 | `context_length: 32000`、`max_completion_tokens: 28800` | `[我实测端点元数据]` |
| 输入模态 | 仅文本（字符串 / JSON 对象 / 数组三者均可） | `[官方 + 我实测]` |
| 速率限制 | **250,000 tokens/秒**、**1,200 请求/分钟**，超任一即 `429` | `[官方原文]` |

**边界实测（英文填充文本，约 4.4 字符 / token）**：

| state 大小 | input_tokens | 结果 |
|---|---|---|
| 40,000 字符 | 9,171 | ✅ 200 |
| 140,000 字符 | 31,394 | ✅ 200 |
| **143,000 字符** | **32,060** | ✅ **200（上限之上仍通过）** |
| 155,000 字符 | 约 34.7k | ❌ 400 `{"error_type":"max_tokens_exceeded"}` |
| 200,000 字符 | — | ❌ 429（撞到速率限制） |

**读法**：32k 子预算这条线**是真的**，实测通过点（32,060）就压在线上；越过后直接被拒。
⚠️ 注意口径差别：**子预算卡的是"state + 单条最长问题"，不是"所有问题之和"** —— 所以把判断拆成多个**短**问题、一次性塞进同一个请求，比写一条超长问题更省预算（这也是官方 Speculative Fan-out 的用法）。
⚠️ 官方另有 `model-jaggedness/jev-1.13` 专页讲 **state 变长时准确率怎么漂** —— 也就是"能塞进去"不等于"塞进去还准"。


---

## 3. 实测记录（本机、真实 key、真实计费）

| # | 用例 | 结果 | 耗时 | 成本 |
|---|---|---|---|---|
| 1 | 广告关键词该不该动（state=词/曝光/点击/花费/出价） | `lower_bid` 0.46 · waste 0.50 · urgency 0.9 | 5.24s（首连） | $0.0000253 |
| 2 | 客服中文消息分流 | `billing` **confidence 1.00** · urgent 0.72 · 情绪 0.94 | 1.60s | $0.0000194 |
| 3 | 同上（复测） | `billing` 1.00 · urgent 0.71 · 情绪 0.94 | 1.19s | $0.0000194 |
| 4 | 同上（复测） | `billing` 1.00 · urgent 0.71 · 情绪 0.94 | 1.21s | $0.0000194 |

**读出来的几件事**：
- ✅ **中文可用**：instructions 和 criteria 写中文，判断准确，选项 key 原样返回。官方文档说训练以英文为主、其他语言需自测——本地这 3 条中文用例表现正常。
- ✅ **稳定**：三次复测结果几乎一致（0.71/0.72），不是掷骰子。
- ⚠️ **延迟实测 1.2 s，高于官方宣称的 70–500 ms**。若走对延迟敏感的路径，需要在你自己的网络下另测，别直接信 500ms。
- ⚠️ **计费极低但非零**：按 $0.042/M 计，462 token 的调用约 $0.00002。key 当前额度 $5、已用 $0.0302。

---

## 4. 坑（都踩过了）

1. **别用 chat/completions 调它** —— 报错 `typesafe/jev-1.13 is a decisions model and cannot be used with the chat/completions endpoint`。
2. **端点没有 `/v1`** —— `/api/alpha/decisions` 对，`/api/v1/alpha/decisions` 404。
3. **body 不套 `input`** —— 顶层直接 `model` / `state` / `questions`；套了会被拒。
4. **`choice` / `score` 的 `criteria` 是必填**；`choice` 的 criteria 是**对象**（key→说明），`score` 的是**数组**（有序，顺序即分数刻度）。`noul` 只要 `instructions`。
5. **`choice` 建议总带一个 `other`** —— 否则它只能在你给的选项里挑个最不坏的。
6. **备选答案是"声明"不是"提示"** —— 声明什么就只能返回什么，这正是它比"让 LLM 输出 JSON 再解析"可靠的地方。
7. **`jev-latest` 会漂** —— 要对阈值负责的场景，把版本号写死，并把响应里的 `model` 字段记进日志。

---

## 5. 和你手上这事的关系（我的判断）

你 `环境变量 OPENROUTER_API_KEY（本仓库不含密钥）` 第一行写着「**亚马逊广告优化学习及总结并落地 skill**」。Jev 这类模型正好卡在那个 skill 最容易出问题的一层：

- 现在广告优化里的判断（**该加价/降价/暂停/否词**）要么写死成规则，要么交给 LLM 出文字再正则解析——前者僵，后者脆。
- Jev 的契约更窄：**动作只能是你声明的那些，还附带概率和置信度**。`confidence` 低的那部分直接推给人看，刚好对上你的 v3.14 规则文档里"人工兜底"的位置。
- **成本可以忽略**：一次判断 $0.00002，一条广告计划跑上百个关键词也就几厘钱。

**但它不能替代你的规则引擎**：金额计算、阈值、优先级排序、批量动作的副作用，仍然应该在代码里。Jev 只负责"这个词算不算废""该往哪个方向动"这类语义判断。

**建议的下一步（等你定）**：先拿你的广告数据表挑 20–50 个关键词，用 `jev_probe.py` 批量跑一遍 `choice/noul/score`，把它的判断和你 v3.14 规则的人工判断做对照表 —— 有对照数据，再决定要不要进 skill。

---

## 6. 安全提醒

- 那支 OpenRouter key 现在**明文躺**在 `环境变量 OPENROUTER_API_KEY（本仓库不含密钥）`。桌面文件夹容易被同步/截图/误传，**建议移到环境变量或密钥管理里**。
- 本次所有调用都是**从该文件读取 key**，没有把 key 写进任何脚本或命令行参数，也没有写进本报告。
- 该 key 目前 `usage=0.0302 / limit=5`，`rate limit: 每 10 秒不限次`，免费模型额度 50 次/天（Jev 是付费模型，不占这个额度）。

---

## 附：可复跑命令

```bash
python "docs/jev_client.py" --probe
```

> 变更记录：原 `jev_probe.py` 已删除 —— 功能被 `jev_client.py --probe` / `--demo` 完整取代，避免两份重复实现。
