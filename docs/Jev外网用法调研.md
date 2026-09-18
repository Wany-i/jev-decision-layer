# Jev 外网用法调研（六路并行 + 第四方独立复核）

> 本文档由 **AI 进行调研、整理与提交**（2026-09-19）。证据分级与出处见文内标注；非官方材料，与模型厂商无隶属关系。

**调研日期**：2026-09-19　**对象**：`typesafe/jev-1.13`（TypeSafe AI，2026-09-15 发布，距今 4 天）
**方法**：六路子代理并行检索不同信源 → 全部产物交**第四方独立复核**（复验 35 条断言）→ 本文按复核结论定稿

---

## 0. 入口（先看这张表）

| 优先级 | 文件 | 一句话 |
|---|---|---|
| **必读** | `docs/Jev外网用法调研.md` | 本文件：外网怎么用、有哪些调用方式、宣称与实测差多少 |
| **必读** | `docs/Jev接入指南-IDE浏览器与运行环境.md` | 怎么接进 IDE / 浏览器，要什么环境 |
| **必读** | `docs/Jev模型使用调研.md` | 接口形状 + 我的一手实测数据 |
| **参考** | `docs/调研原始/00-复核报告.md` | **先看这份**：35 条复核，含 5 条已证伪、16 条无法复验 |
| **必读（最新）** | `docs/Jev广告关键词决策-状态设计与实测.md` | 落地设计：state 该给什么、问题怎么写、阈值怎么定（含 40 次实测） |
| **留档** | `docs/调研原始/01~06-*.md` | 六路原始产物（含出处 URL 与代码片段） |

---

## 1. 待你裁决（带我的推荐）

| # | 事项 | 我的推荐 | 理由 |
|---|---|---|---|
| 1 | **要不要用它做广告优化的决策层** | **先做影子测试，别直接上生产** | 外网唯一的公开校准审计是**负面**的：Jev 的 ECE 0.154 vs Claude Haiku 4.5 的 0.097；置信度只在两端可信、中间区间接近抛硬币。这是**必须自己复现**才能采信的一个数（第五节） |
| 2 | **中文场景能不能用** | **可以试，但必须自建评测** | 官方文档自己承认 **CJK 准确率更低**；中文圈**零实测数据**。我实测的 3 条中文用例表现好，但 3 条不构成证据 |
| 3 | **走哪条通道** | **保留 OpenRouter**（你已有 key），**备一条 TypeSafe 直连** | OpenRouter 是唯一已上架且你已跑通的；TypeSafe 直连需候补，但官方另有 `system-one-adapter-python` 可先把代码跑通 |
| 4 | **要不要接进 IDE** | **接**，但只当工具不当模型 | 官方**没有** MCP server，官方路径是 `typesafe-ai/skills`（教 agent 写代码）；社区有 `jkudish/jev-mcp`。我们已经自己写好了 `jev_mcp_server.py` |
| 5 | **要不要抄社区的执行层** | **值得看** `browser-use/jev-ultrafast` 的范式 | 它是"Jev 选操作+元素"的真实实现，且是三天下来的最高热度项目 |

---

## 2. 结论摘要

1. **调用通道确认 6 条**：TypeSafe 直连、OpenRouter（你在用）、Vercel AI Gateway、Cloudflare AI、Netlify AI Gateway、Braintrust（可观测）。**注意：没有 `:free` 档位**。
2. **官方推荐给 Agent 的路径不是 MCP，而是"技能包"**：`typesafe-ai/skills`（219★）——它教 agent **怎么写 TypeSafe 代码**，而不是把 Jev 变成可调用的工具。官方**没有** MCP server。
3. **现成集成比预期多**：LangChain（`TypeSafeClassifier` + 两个中间件）、Vercel AI SDK（`experimental_evaluate`）、Braintrust tracing，另有 **Pydantic-AI / Rig(Rust) / Effect / elizaOS / Composio / LangChain.js 已把集成代码合进各自主仓**。
4. **官方宣称的倍数打了几折**：官方口径 193.6× 更快 / 444.6× 更便宜；**三方独立实测只有 4–6× 更快、8.6–40× 更便宜**；官方说的 70–500ms，**公开实测中位数在 150–850ms**，**70ms 无人复现**。
5. **外网最锋利的一击是"HN 帖子里的战斗力全在 can't hallucinate"**：HN 1885 分、约 492 条讨论，CEO 当场让步承认"**也可能自信地错**"，并同意"这本质上就是个 zero-shot classifier"。
6. **中文圈：图文热、视频空白、实测为零**。并有三个流传较广的中文说法**全部被夸大**（第六节，出处已核到）。
7. **我上一轮给你的"官方字段"口径需要补充**：TypeSafe 官方 API 顶层**只有** `model`/`state`/`questions`，`session_id`/`trace`/`user`/`provider` 是 **OpenRouter 侧**的参数层字段（其中只有 2 个被复验到）；我实测响应里的 `provider` 应标为**代理层附加**。

---

## 3. 有哪些方式可以调用（你问的核心）

| 通道 | 入口 / 模型 id | 鉴权 | 前提 | 证据 |
|---|---|---|---|---|
| **TypeSafe 直连** | `POST https://api.typesafe.ai/v1/systemone` | Bearer `TYPESAFE_API_KEY` | **需候补**（早期访问） | `[官方]` |
| **OpenRouter** | `POST https://openrouter.ai/api/alpha/decisions`（**无 /v1**）；id `typesafe/jev-1.13` / `jev-latest` | Bearer | 有额度即可 | `[我实测]` + `[复核复现]` |
| **Vercel AI Gateway** | 模型 id `typesafe-ai/jev`；AI SDK **7.0.105+** `experimental_evaluate` | Vercel 额度 | 需 ZDR 选项可配 | `[官方页]` |
| **Cloudflare AI** | `/ai/run` 或 Worker `env.AI.run('typesafe/jev', …)` | Cloudflare 统一计费 | 无 key 也能走统一计费 | `[官方页]` |
| **Netlify AI Gateway** | `@typesafe-ai/sdk` 零配置 | Netlify credits | Node 20+ | `[官方页]` |
| **Braintrust**（可观测，非独立通道） | `wrapTypeSafe()`，v3.34.0+ | 需申请 | 用于 trace 与 judge | `[官方页]` |
| 官方 SDK | `pip install typesafe-sdk`（Py 3.10+）/ `npm install @typesafe-ai/sdk`（Node 20+） | — | 默认读 `TYPESAFE_API_KEY` | `[官方]` |
| **反向适配器** | `typesafe-ai/system-one-adapter-python` | — | **可换成 OpenAI/Anthropic 后端** —— 没排到候补也能先跑通代码 | `[复核复现]` |

**明确没有的通道**（用对照词验证过检索有效）：Portkey、Requesty、LiteLLM、Helicone、Together、Fireworks、Groq 均未上架；`typesafe/jev-1.13:free` 不存在；AnyRouter 虽列出但**仅支持自带 key（BYOK）**，不是独立通道。

---

## 4. 别人实际怎么用它

### 4.1 官方自己的四个范式（不是二手说的五个）
`[官方，已复核]` 官方 patterns 页恰好 4 个：**Speculative Fan-Out**（一次性问全部，含只在某分支才用的问题）、**Confidence-Gated Routing**（按置信度分流）、**Composite Scoring**（拆成原子 Score 再在代码里加权）、**Intent Routing**（意图路由）。
⚠️ 二手文章流传的"五种模式"里的 **the cascade、retrieve-then-judge 没有官方页面**——前者只是个 cookbook 名。**官方 cookbook 是 18 个，不是二手说的 21 个。**

### 4.2 官方给 Agent 的接入路径：`typesafe-ai/skills`
`[官方，已复核]` 这是一个**技能包**，不是 MCP：
```
claude plugin marketplace add typesafe-ai/skills
claude plugin install typesafe@typesafe-ai
# 其它 agent：
npx skills add typesafe-ai/skills --skill typesafe-ai
```
它做的是**教你的 agent 如何写 TypeSafe 代码**（含 `agent-skill` 专页）。→ **官方没有把 Jev 变成工具，而是教 agent 去调 API。** 这一点和我们的判断一致：**它是工具级能力，不是对话模型**。

### 4.3 社区在做的事：执行层最热
| 项目 | 星数 / 创建日 | 干什么 |
|---|---|---|
| `browser-use/jev-ultrafast` | **4992★** / 2026-09-16 | **Jev 选 operation + element** 的浏览器执行层（三天下来的最高热度） |
| `tamaratran/fast-jev-compaction` | **2860★** / 2026-09-17 | 25k/30k/32k 分片策略，对付长输入 |
| `jarrodwatts/jev-trader` | 814★ / 2026-09-16 | 交易判断 demo（**默认 mock + dry-run**） |
| `fhshaik/typesafe-mario` | 260★ / 2026-09-16 | 马里奥控制器（**实验性**） |
| `awlevin/typesafe-computer-use` | 204★ / 2026-09-16 | OCR + Jev 的计算机操作，单步约 $0.0002 |
| `droidrun/mobile-jev` | 109★ / 2026-09-17 | 移动端操作 |
| `jkudish/jev-mcp` | 71★ / 2026-09-17 | 社区 MCP server |
| `kitze/skillbox` | 154★ / 2026-09-17 | 含 OpenRouter decisions 端点的独立复现 |

**星数我已三重核验**（公开 API + 复核方 + 我自己）：数字为真、`created_at` 都在发布日之后。
⚠️ **但 `Anil-matcha/awesome-jev-by-typesafe`（501★）的 `created_at` 是 2023-05-17** —— 旧仓库改名，**不能当新模型热度**。

### 4.4 生态集成现状（修正后口径）
- ✅ **现成可用**：LangChain（`TypeSafeClassifier` + `ModelRouterMiddleware`/`AutoModeMiddleware`，后者能在**工具执行前拦截**）、Vercel AI SDK、Braintrust。
- ✅ **已合并进主仓**（复核方用源码逐个确认）：**Pydantic-AI、Rig(Rust)、Effect、elizaOS、Composio、LangChain.js**。
  → 此处纠正：六路中的第 6 路曾报这些"全部零命中"，复核方用 `gh api contents` 逐个查，**6 条全被证伪**（路径均 HTTP 200 且内容确为 Jev 集成）。
- ❌ **确认没有**：LlamaIndex、CrewAI、AutoGen、LangGraph（`gh search code` 0 命中）；Langfuse、Arize Phoenix、W&B Weave、OTel GenAI 约定；影刀RPA、Power Automate。

---

## 5. 外网实测把官方宣称打了几折（**最该看的一节**）

| 官方宣称 | 外网独立实测 | 差距 |
|---|---|---|
| 193.6× 更快 | **4–6× 更快**（三方独立：Near Here / altryne / Isaac Flath） | 约打 3 折 |
| 444.6× 更便宜 | **8.6–40× 更便宜** | 大幅缩水 |
| 70–500 ms | **公开中位数 150–850 ms，70ms 无人复现** | 下限不成立 |
| "零结构化输出错误" | **打字安全为真，但"不会答错"为假** | CEO 在 HN 当场让步 |
| — | **唯一公开校准审计**：ECE **0.154**（Jev）vs **0.097**（Claude Haiku 4.5） | **Jev 更差** |
| — | 置信度**只在两端可信，中间区间接近抛硬币** | 直接影响阈值设计 |
| — | **长输入 / 整文档是天花板**（"no prompt fixed that"） | 与 32k state 预算一致 |

**厂商自报、未经复现**：`250,000 tok/s`、`1,200 req/min`。
**官方技术事实（复核通过、可直接引用）**：仅文本输入、64k 总上下文（state+全部问题）/ 32k（state+最长单问题）、`GET /v1/models`、无 key 实测 **403**（文档写 401）、4 个错误码（401/422/429/529）、指数退避、`choice` ≤255 选项、`score` 2–10 级、**9 类失败模式**、`confidence` 是分布统计量且 **Noul 无 confidence**、**state 的 CJK 准确率更低**。

**结论**：**快和便宜是真的，倍数不是。** 把它当"比 LLM 便宜 400 倍"来做成本模型会翻车；当"便宜 10 倍、快 5 倍的分类器"是安全的。

---

## 6. 中文圈：三个流传较广的说法，出处核查

中文圈（36氪、极客公园、机器之心、量子位、AIHub、网易、53AI、DataLearner 等）图文不少，**B站/抖音/小红书/知乎定向检索全部零命中**（用 DeepSeek 做对照词验证通道有效）。三个说法**都找到了原始出处，但转述都夸大了**：

| 说法 | 原始出处 | 实际是什么 |
|---|---|---|
| 马里奥"效果出奇的好" | `github.com/fhshaik/typesafe-mario`（260★） | **实验性控制器**，非成品 |
| "7 秒订完机票" | `browser-use/jev-ultrafast` | 实为 **7.073 秒、且只"搜出结果页"、不订票**；作者自陈 **p=0.25** |
| "交易机器人" | `jarrodwatts/jev-trader`（814★） | **默认 mock 模型 + dry-run，无盈亏验证**，作者自认 rough |

**中文可用性**：无任何中文实测数据；无 Jev 专属的国内中转/代理教程；国产 MaaS 未见上架。唯一线索是二手转述"英文最好、CJK 不均衡"——**这条其实在官方文档里能找到**（官方承认 CJK 准确率更低）。

---

## 7. 已被证伪 / 不能用的结论（复核方产出，务必避开）

**必须弃用的 6 条**：
1. "Pydantic-AI / Composio / elizaOS / Rig / Effect 全部无集成" —— **6 条全被源码证伪**
2. "JS/TS 侧 LangChain.js 集成未找到" —— 存在
3. "官方 21 个 cookbook" —— 实测 **18**
4. "HN 主帖 1,865 点" —— 实测 **1885**
5. "`razorsharp16/openjev` 404 → 仓库已消失" —— 是**笔误**，真仓库 `razorback16/openjev` 存在
6. "Jev 架构以 arXiv 2503.23303 公开" —— 该编号是**无关论文**

**无法复验、引用时必须降级**：X 官方帖浏览量（三个数字互不一致，2000 万–3400 万）、Sam Witteveen / TheAIGRID 视频（无直链）、Michael Lee 的 p50/p95、"800 项难度阶梯"、"777 次判断"、Forbes 的 $200M 估值、AnyRouter 的 128K context（与官方 64k 冲突）、OpenRouter 模型页"写了 decisions 端点"（页面里并没有）。

---

## 附：复核是怎么做的（可信度说明）

复核方独立完成了：完整读完 6 份共约 3200 行产物 → **GitHub API 逐个复验 20 个仓库**（stars/created_at/fork/parent）→ 抓取官方一手材料逐字比对（`docs.typesafe.ai/llms.txt` 16348 字节 + 12 个 `.md` 页 + `sitemap.xml` + OpenRouter 模型页 348105 字节）→ 实测 5 个 URL 状态 → 对 OpenRouter decisions 端点做**无鉴权探测**（401 存在 / `/v1` 版本 404）→ **HN Algolia 原始 JSON 全树解析**（253060 字节、493 节点）→ 第三方实测页直抓命中关键数字 → PyPI/arXiv 交叉验证。

**抽验 35 条：✅ 25 / ⚠️ 5 / ❌ 5。**

**本文的证据分级**：`[我实测]` = 我在本机真实调用过；`[官方]` = 官方一手页面且经复核；`[复核复现]` = 复核方独立验证过；`[外网实测]` = 第三方公开实测；`[厂商自报]` = 厂商数字未经复现；`[无法复验]` = 已降级。
