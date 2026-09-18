# 03 GitHub 与开源实现

> 本文档由 **AI 进行调研、整理与提交**（2026-09-19）。证据分级与出处见文内标注；非官方材料，与模型厂商无隶属关系。

> 调研日期：2026-09-19（周六）
> 唯一检索通道：`gh` CLI 2.89.0（已登录 github.com，token scopes: gist / read:org / repo）+ WebSearch + WebFetch
> 所有 URL 均由 `gh api` 实际返回，非搜索页 URL；除非另行标注，均为 2026-09-19 当日抓取。

## 结论摘要（≤10 行）

1. **任务书里"第三方实现很可能极少甚至为零"的假设不成立。** 实测 GitHub 上 Jev/TypeSafe 相关仓库数量很大，且有大厂框架一手合入的代码（Vercel AI SDK、LangChain、Pydantic-AI、Rig/Rust、Effect、elizaOS、Composio、Cloudflare docs）。
2. **官方 SDK 有 3 个**：`typesafe-ai/typesafe-sdk-python`（MIT）、`typesafe-ai/typesafe-sdk-js`（MIT）、`typesafe-ai/system-one-adapter-python`（MIT），外加 `typesafe-ai/skills`（Agent Skill）。组织 `typesafe-ai` 成立于 2024-05-28，共 10 个公开仓库。
3. **非官方语言 SDK 至少有 Go / Java / PHP / C# / Swift / Scala / Rust 七种**，但基本都是 0–7★ 的新仓库，除 `Tangerg/typesafe-sdk-go` 外质量未经验证。
4. **MCP server 生态非常拥挤**：仅 `gh search repos` 就返回 8+ 个独立 `jev-mcp` 仓库，最高 71★（`jkudish/jev-mcp`）。但 **mcp.so 与 smithery 都搜不到 Jev MCP**，`punkpeye/awesome-mcp-servers` 也未收录。
5. **主流 awesome list 全部未收录**：Awesome-LLM / awesome-ai-agents / awesome-mcp-servers / awesome-openrouter 均为 0 命中（每个都用有效对照词验证过通道）。
6. **官方 SDK 仓库的 issue 是最高价值的一手坑源**：已摘录 6 条真实缺陷，含 400/422 参数陷阱、Node 20/22 进程被 AbortError 杀掉、numpy.str_ 静默损坏。
7. **最实用的 OpenRouter 端点情报**来自 `kitze/skillbox#4`：独立复现了 `/api/alpha/decisions`（无 `/v1`）+ 150–200 candidates 会触发 `max_tokens_exceeded` / HTTP 520。
8. **决策层真实项目很多**：浏览器（`browser-use/jev-ultrafast` 4946★）、手机（`droidrun/mobile-jev`）、桌面 OCR（`awlevin/typesafe-computer-use`）、Claude Code 压缩（`tamaratran/fast-jev-compaction` 2821★）、代码评审、Postgres、链上交易、游戏自动驾驶。
9. **"开源复现"路线已出现**：`TheoLeeCJ/SemIf` 1508★、`TianyuCodings/NanoJev` 319★、`ekzhang/openjev-sglang` 131★、`razorback16/openjev` 17★。
10. **未找到**：中文/多语言场景的 issue、429/限流的具体 issue、mcp.so/smithery 上的 Jev MCP、以及被 Awesome-LLM 等收录的证据。

---

## 仓库清单

### A. 官方仓库（组织 `typesafe-ai`）

`gh api /users/typesafe-ai` → `{"login":"typesafe-ai","type":"Organization","name":"TypeSafe","blog":"https://typesafe.ai/","created_at":"2024-05-28T20:57:18Z","public_repos":10}`
**注意**：`typesafeai` 组织不存在（404）；`typesafe` 是 2009 年注册的个人用户 Gino Heyman，与本项目无关——检索时注意区分噪声。

| 仓库 URL | 是什么 | 语言 | License | ★ | created | pushed | 能不能直接用 |
|---|---|---|---|---|---|---|---|
| https://github.com/typesafe-ai/typesafe-sdk-python | 官方 Python SDK | Python | MIT | 80 | 2026-09-04 | 2026-09-18 | ✅ 可直接用 |
| https://github.com/typesafe-ai/typesafe-sdk-js | 官方 JS/TS SDK | TypeScript | MIT | 116 | 2026-09-04 | 2026-09-15 | ✅ 可直接用（Node 20+） |
| https://github.com/typesafe-ai/system-one-adapter-python | `system_one` 的 drop-in 替代实现，后端接 OpenAI/Anthropic/自建端点 | Python | MIT | 111 | 2026-08-08 | 2026-09-18 | ✅ 可用于接口先行开发 |
| https://github.com/typesafe-ai/skills | 官方 Agent Skill（Claude Code plugin + `npx skills add`） | — | MIT | 216 | 2026-08-24 | 2026-09-12 | ✅ 可直接用 |

其余 6 个仓库为基础设施（`daggerverse`、`LLaDA`、`Overwatch`、`pulumi-clickhouse`、`typesafe-ai.github.io`、`vllm`），与 Jev 接入无关。

**上架证据（一手）**：
- PyPI `typesafe-sdk`：`author: TypeSafe AI`，classifiers 含 `License :: OSI Approved :: MIT License`、`Programming Language :: Python :: 3.10 ~ 3.14`。
- npm `@typesafe-ai/sdk`：`dist-tags.latest = 0.6.0`，maintainers `alliesafe <allie@typesafe.ai>`、`diogo149 <diogo@typesafe.ai>`，homepage `https://docs.typesafe.ai`。

### B. 主流框架内的一手集成代码（**这是"能直接抄"的最佳来源**）

| 文件 URL | 是什么 | 语言 | 最后更新 | 能不能直接用 |
|---|---|---|---|---|
| https://github.com/vercel/ai/blob/main/content/providers/01-ai-sdk-providers/105-typesafe-ai.mdx | 官方 Vercel AI SDK TypeSafe provider 文档（4606 B） | MDX | 在 main 分支 | ✅ 文档级可直接抄 |
| https://github.com/langchain-ai/langchain/tree/master/libs/partners/typesafe | LangChain 官方 `langchain-typesafe` 包（含 `TypeSafeClassifier` Runnable） | Python | 在 master 分支 | ✅ 可直接用 |
| https://github.com/langchain-ai/langchainjs/blob/main/libs/providers/langchain-typesafe/README.md | LangChain.js 对应实现 | TS | 在 main 分支 | ✅ |
| https://github.com/pydantic/pydantic-ai/blob/main/docs/models/typesafe.md | Pydantic-AI 的 TypeSafe 模型文档（26731 B） | MD | 在 main 分支 | ✅ |
| https://github.com/0xPlaygrounds/rig/tree/main/crates/rig-typesafeai | Rust 主流框架 Rig 的 TypeSafe/Jev crate | Rust | 在 main 分支 | ✅ 实验性 |
| https://github.com/Effect-TS/effect/tree/main/packages/ai/typesafe | Effect（TS）的 TypeSafe 客户端 | TypeScript | 在 main 分支 | ⚠️ 未细读 |
| https://github.com/elizaOS/eliza/tree/main/packages/agent/src/services/typesafe | elizaOS 的 TypeSafe service | TypeScript | 在 main 分支 | ⚠️ 未细读 |
| https://github.com/ComposioHQ/composio/tree/master/python/providers/typesafe | Composio provider | Python | 在 master 分支 | ⚠️ 未细读 |
| https://github.com/cloudflare/cloudflare-docs/blob/production/src/content/catalog-models/typesafe-jev.json | Cloudflare 模型目录条目 | JSON | production 分支 | ✅ 参考资料 |
| https://github.com/anomalyco/models.dev/blob/main/providers/opencode/models/jev-latest.toml | models.dev 的 `jev-latest` 条目 | TOML | main 分支 | ✅ 参考资料 |
| https://github.com/braintrustdata/braintrust-sdk-javascript/blob/main/js/src/vendor-sdk-types/typesafe.ts | Braintrust 的 TypeSafe 类型定义 | TypeScript | main 分支 | ⚠️ |

> 检索方式：`gh search code "jev-latest" --limit 20` / `gh search code "TypeSafeClient" --limit 20`。

### C. 非官方语言 SDK（社区实现，**质量普遍未验证**）

| 仓库 URL | 是什么 | 语言 | License | ★ | created | 能不能直接用 |
|---|---|---|---|---|---|---|
| https://github.com/Tangerg/typesafe-sdk-go | Go SDK，Go 1.25+，零第三方依赖 | Go | MIT | 7 | 2026-09-18 | ✅ 有完整 README + example；作者主动在官方 SDK issue 里求收录 |
| https://github.com/Olti1947/jev-java | Java SDK | Java | 无 | 3 | 2026-09-18 | ⚠️ 无 license |
| https://github.com/saibimajdi/typesafeai-dotnet-sdk | .NET SDK（声明 "Not affiliated"） | C# | MIT | 5 | 2026-09-16 | ⚠️ |
| https://github.com/Hawxy/TypeSafeAI.Net | .NET SDK | C# | Apache-2.0 | 2 | 2026-09-17 | ⚠️ |
| https://github.com/Butochnikov/typesafe-sdk-php | PHP SDK | PHP | MIT | 1 | 2026-09-17 | ⚠️ |
| https://github.com/shanginn/jev-php | PHP 8.5 SDK（走 **OpenRouter** 而非官方端点） | PHP | 无 | 0 | 2026-09-17 | ⚠️ |
| https://github.com/mzainzulifqar/jev-php-sdk | PHP SDK，PSR-18，Laravel 8–13 | PHP | 无 | 0 | 2026-09-18 | ⚠️ |
| https://github.com/marandaneto/typesafe-sdk-swift | Swift SDK（自述为 JS/Python SDK 的移植） | Swift | MIT | 0 | 2026-09-18 | ⚠️ |
| https://github.com/aoprisan/typesafe-ai-scala-sdk | Scala SDK | Scala | MIT | 0 | 2026-09-17 | ⚠️ |
| https://github.com/guillemus/jev-go | Unofficial Go SDK | Go | 无 | 1 | 2026-09-17 | ⚠️ |
| https://github.com/Stumble/jev-go · https://github.com/withzombies/jev-go · https://github.com/Gaurav-Gosain/jev-go · https://github.com/havlan/jev-go | 另外 4 个 Go 客户端 | Go | 无 | 0–1 | 2026-09-17~18 | ⚠️ 4 个同名同功能仓库，疑似抢注 |
| https://github.com/danvega/hello-jev-java | Java 示例仓库 | Java | 无 | 4 | 2026-09-18 | ⚠️ 示例 |

**Ruby：未找到**。`gh search repos "jev ruby"` 只返回 `jeva/Jeva--RubyApp`（0★，无关项目）。
**C# 单独搜索："jev csharp" / "jev dotnet" 均无结果**，需用 `TypeSafeClient` 代码搜索才能命中（见上表）。

### D. MCP server 生态

| 仓库 URL | 是什么 | 语言 | ★ | 能不能直接用 |
|---|---|---|---|---|
| https://github.com/jkudish/jev-mcp | POC MCP，最高星 | TypeScript | 71 | ✅ MIT，有 `npx -y @jkudish/jev-mcp` |
| https://github.com/itsmostafa/typesafe-mcp | MCP connector | Go | 62 | ✅ MIT |
| https://github.com/blakestone-x/jev-mcp | classify/score/check/match/screen | Python | 8 | ⚠️ |
| https://github.com/arunav25/jev-mcp | 与通用 LLM 对比准确率 | JavaScript | 5 | ⚠️ |
| https://github.com/y0usaf/typesafe-mcp | MCP server | JavaScript | 3 | ⚠️ |
| https://github.com/rashedInt32/jev-mcp | Claude Code plugin 形态 | TypeScript | 2 | ⚠️ |
| https://github.com/BYK/jev-mcp | eval-first MCP | TypeScript | 1 | ⚠️ |
| https://github.com/burnigtm/jev-mcp | coding loop 用 MCP（被 jkudish#1 引用） | TypeScript | 1 | ⚠️ MIT |
| https://github.com/abhishekashokvkumar/jev-mcp-dispatcher | 纯用 Jev 做 MCP 工具调度 | Python | 1 | ⚠️ |
| https://github.com/Obrais-cloud/typesafe-mcp | judge / rerank / systemone | Python | 1 | ⚠️ |
| https://github.com/fast-facts/jev-mcp | MCP server | Go | 0 | ⚠️ |
| https://github.com/hangarbay/jev.mcp | MCP server | Go | 0 | ⚠️ |
| https://github.com/minhgv/jev-mcp | coding agents + CI 决策层 | TypeScript | 0 | ⚠️ |
| https://github.com/Pinutss/jev-mcp-router | MCP 工具路由（不执行） | Python | 0 | ⚠️ |
| https://github.com/cbruyndoncx/AskJev-MCP | System One MCP | JavaScript | 0 | ⚠️ |
| https://github.com/AStheTECH/mewcp-jev | "JEV MCP server by MewCP" | Python | 0 | ⚠️ 描述极简 |
| https://github.com/gamesonrblx/Jevbridge | ACP+MCP 桥，把 Jev 接到任意 LLM | TypeScript | — | ⚠️ |

> **注册站情况**：mcp.so 与 smithery 均**未收录**任何 Jev/TypeSafe MCP server（见"逐条发现"第 9、10 条）。

### E. 决策层真实项目（guardrail / router / 分类器 / 自动化）

| 仓库 URL | 用途 | 语言 | ★ | License | created | 最后更新 |
|---|---|---|---|---|---|---|
| https://github.com/browser-use/jev-ultrafast | 浏览器自动化：Jev 选 operation + element，小 LLM 只在 `TYPE_TEXT` 时写文本 | Python | 4946 | MIT | 2026-09-16 | 2026-09-18 |
| https://github.com/tamaratran/fast-jev-compaction | Claude Code 插件：用 Jev `noul` 决策替换 compaction 摘要 | TypeScript | 2821 | MIT | 2026-09-17 | 2026-09-18 |
| https://github.com/TheoLeeCJ/SemIf | 本地开源模型复现"语义 if"（声明与 TypeSafe 无关） | Python | 1508 | MIT | 2026-09-16 | 2026-09-18 |
| https://github.com/jarrodwatts/jev-trader | 每个 Monad 区块一次交易决策（Kuru MON-USDC） | TypeScript | 810 | MIT | 2026-09-16 | 2026-09-18 |
| https://github.com/TianyuCodings/NanoJev | Jev 的 nano 复现 + 训练管线 | Python | 319 | MIT | 2026-09-17 | 2026-09-17 |
| https://github.com/thruwire/foreman | Software Factory Foreman | Python | 280 | MIT | 2026-09-17 | 2026-09-18 |
| https://github.com/fhshaik/typesafe-mario | 用结构化模拟器状态玩超级马里奥 | Python | 260 | — | — | 2026-09-18 |
| https://github.com/devagrawal09/jev-review | 分阶段代码评审工作流 + 本地 dashboard | TypeScript | 254 | MIT | 2026-09-16 | 2026-09-18 |
| https://github.com/awlevin/typesafe-computer-use | macOS computer use：OCR 屏幕 → Jev 分类动作 → 点击，约 $0.0002/step | Python | 204 | MIT | 2026-09-16 | — |
| https://github.com/realZachi/pg-jev | PostgreSQL 扩展：用自然语言查询表 | Python | 145 | NOASSERTION | 2026-09-17 | 2026-09-18 |
| https://github.com/ekzhang/openjev-sglang | 基于开源模型的 Jev 兼容端点（prefill-only） | Python | 131 | 无 | 2026-09-17 | — |
| https://github.com/NiazMorshed2007/jev-review | 本地优先 MCP 插件，持续软件质量评审 | TypeScript | 113 | MIT | 2026-09-17 | 2026-09-18 |
| https://github.com/droidrun/mobile-jev | Android 真机 agent（Mobilerun + Jev） | JavaScript | 104 | MIT | 2026-09-17 | 2026-09-17 |
| https://github.com/hr98w/jev-visual | Apple Silicon 上的本地视觉推理实验 | Python | 100 | — | — | 2026-09-18 |
| https://github.com/standardagents/jevpilot | Three.js 驾驶模拟器 + Jev 自动驾驶 | JavaScript | 59 | 无 | 2026-09-17 | 2026-09-18 |
| https://github.com/razorback16/openjev | 基于 DiffusionGemma 的 Jev 兼容决策服务 | Python | 17 | Apache-2.0 | 2026-09-18 | 2026-09-18 |
| https://github.com/paulsmith/computer-use-jev | macOS computer use，Go 实现 | Go | — | — | — | — |
| https://github.com/max1874/jev-computer-use | macOS computer-use agent（自述为 jev-ultrafast 的 macOS 移植） | Python | 0 | — | — | — |
| https://github.com/cartermccann/typesafe-computer-use-hyprland | Hyprland/NixOS fork | Python | — | — | — | — |
| https://github.com/vercel/eve | 开源 Agent 框架（被二手博客描述为集成 Jev） | TypeScript | — | — | — | — |

### F. Awesome list（Jev 专项）

| 仓库 URL | 是什么 | 语言 | ★ | created |
|---|---|---|---|---|
| https://github.com/Anil-matcha/awesome-jev-by-typesafe | Jev 用例/模式/提示词/示例代码 | Python | 497 | **2023-05-17**（见"存疑"） |
| https://github.com/AbdelStark/awesome-typesafe | TypeSafe / System One / Jev 资源列表 | CSS | 214 | 2026-09-17 |
| https://github.com/yibie/awesome-jev | Jev 项目/集成/讨论列表 | Python | 123 | 2026-09-17 |
| https://github.com/fatwang2/awesome-jev | Jev 项目目录 + 可复用 GitHub review 工作流 | JavaScript | 69 | 2026-09-18 |
| https://github.com/AnotiaWang/awesome-jev | Jev 应用/库/资源列表 | — | 56 | 2026-09-18 |
| https://github.com/jellydn/awesome-typesafe | **噪声**：这是 TypeScript typesafe 库列表，与 TypeSafe AI 无关 | — | 191 | — |

---

## 逐条发现

### 1. GitHub 上第三方实现数量远超预期，不是"零"
- **证据**：`gh search repos jev --limit 30` 返回 30 条中至少 18 条是 TypeSafe Jev 相关；`gh search code "TypeSafeClient" --limit 20` 返回 20 条命中，覆盖 Swift / C# / Scala / PHP / TS / Python。
- **来源类型**：`[一手代码]`
- **日期**：2026-09-19 抓取
- **对照验证**：`gh search repos openrouter --limit 3` 返回 `OpenRouterArchived/openrouter-runner` 等真实结果，通道有效。

### 2. 官方 Python SDK 的最小示例（README 原文）
- **证据**（README 原文摘录，https://github.com/typesafe-ai/typesafe-sdk-python）：
  > Install the SDK: `uv add typesafe-sdk`
  > Set `TYPESAFE_API_KEY` in your environment, then instantiate and use the client:
  > ```python
  > from typesafe_sdk import Choice, TypeSafeClient
  >
  > with TypeSafeClient() as client:
  >     response = client.system_one(
  >         state={"document": "I was charged twice. Please fix this ASAP."},
  >         questions={
  >             "category": Choice(
  >                 instructions="What is this ticket about?",
  >                 criteria={"billing": None, "technical": None, "other": None},
  >             ),
  >         },
  >     )
  >
  > print(response.choices["category"].choice)
  > ```
- **注**：README 用 `response.choices["category"]`，而多数二手博客写的是 `response.answers["category"]`——**两者不一致，以 SDK 源码为准**（本条属 `[推测]`，未读源码）。
- **来源类型**：`[官方]`
- **日期**：2026-09-19 抓取（仓库 pushed 2026-09-18）

### 3. 官方 JS SDK 的最小示例（README 原文）
- **证据**（README 原文摘录，https://github.com/typesafe-ai/typesafe-sdk-js）：
  > JavaScript and TypeScript SDK... Install the SDK (Node.js 20 or newer): `npm install @typesafe-ai/sdk`
  > ```ts
  > import { choice, TypeSafeClient } from "@typesafe-ai/sdk";
  >
  > const client = new TypeSafeClient();
  > const response = await client.systemOne({
  >   state: { document: "I was charged twice. Please fix this ASAP." },
  >   questions: {
  >     category: choice("What is this ticket about?", {
  >       billing: null,
  >       technical: null,
  >       other: null,
  >     }),
  >   },
  > });
  >
  > console.log(response.answers.category.choice);
  > ```
  > Answer types are inferred from your questions. The package includes ESM, CommonJS, and TypeScript declarations.
- **来源类型**：`[官方]`
- **日期**：2026-09-19 抓取（仓库 pushed 2026-09-15）

### 4. LangChain 官方已有 `langchain-typesafe` partner 包（一手源码）
- **证据**（https://github.com/langchain-ai/langchain/blob/master/libs/partners/typesafe/langchain_typesafe/classifier.py 原文摘录）：
  > ```python
  > """LangChain runnable for TypeSafe classification."""
  > ...
  > _DEFAULT_BASE_URL = "https://api.typesafe.ai"
  > _DEFAULT_MODEL = "jev-latest"
  > _DEFAULT_TIMEOUT = 30.0
  > _LS_PROVIDER = "typesafe"
  >
  > @beta()
  > class TypeSafeClassifier(RunnableSerializable[State, ClassificationResponse]):
  > ```
  > 目录内容：`.gitignore / LICENSE / Makefile / README.md / langchain_typesafe/ / pyproject.toml / scripts/ / tests/ / uv.lock`
- **来源类型**：`[一手代码]`
- **日期**：2026-09-19 抓取（master 分支）
- **存疑**：该文件 `import httpx2`（不是 `httpx`），未核实该包名真伪。

### 5. Vercel AI SDK 已内置 TypeSafe provider（一手文档）
- **证据**（https://github.com/vercel/ai/blob/main/content/providers/01-ai-sdk-providers/105-typesafe-ai.mdx 原文摘录）：
  > `pnpm add @ai-sdk/typesafe-ai`；环境变量 `TYPESAFE_AI_API_KEY`；`baseURL` 默认 `https://api.typesafe.ai/v1`
  > ```ts
  > const result = await experimental_evaluate({
  >   model: typeSafeAi.evaluationModel('jev-latest'),
  >   state: { message: 'I was charged twice. Please refund the duplicate.' },
  >   questions: {
  >     department: { type: 'choice', instructions: 'Which team should handle this?',
  >       criteria: { billing: { includes: ['Charges','Invoices','Refunds'] }, technical: ['Bugs','Outages'], other: null } },
  >     severity: { type: 'score', instructions: 'How severe is the issue?',
  >       criteria: ['Cosmetic', 'Workaround exists', 'Blocking; no workaround'] },
  >     requestsRefund: { type: 'boolean', instructions: 'Is the customer requesting money back?' },
  >   },
  > });
  > console.log(result.answers.department.choice);
  > console.log(result.answers.severity.score);
  > console.log(result.answers.requestsRefund.probability);
  > ```
  > 限制表：`choice` 1–255 options；`score` 2–10 ordered levels；`boolean` 对应原生 Noul，返回 model-estimated probability of true。
- **来源类型**：`[一手代码]`
- **日期**：2026-09-19 抓取

### 6. Rig（Rust）有独立的 `rig-typesafeai` crate（一手源码）
- **证据**（https://github.com/0xPlaygrounds/rig/blob/main/crates/rig-typesafeai/README.md 原文摘录）：
  > `Experimental TypeSafe Jev judgments for Rig. Enable the root rig feature typesafeai to use rig::typesafeai... There are no Jev derive macros or schema-generation traits.`
  > ```rust
  > let query = Assessment {
  >     ready: Noul::new("Is this ready to ship?")?,
  >     needs_review: Noul::new("Does this need human review?")?,
  > };
  > let answers: Assessment<NoulAnswer, NoulAnswer> = jev.evaluate(&state, &query).await?.answers;
  > ```
  > 目录：`Cargo.toml 681B / README.md 5792B / fixtures / src`，并提供 `examples/typesafeai_triage/src/main.rs`。
- **来源类型**：`[一手代码]`
- **日期**：2026-09-19 抓取（`0xPlaygrounds/rig` 8662★，仓库本身建于 2024-06-05）

### 7. 官方 SDK 的 README 未列 Go 客户端，社区在 issue 里主动求收录
- **证据**（https://github.com/typesafe-ai/typesafe-sdk-js/issues/7，Tangerg，2026-09-18 原文摘录）：
  > The docs [SDK page](https://docs.typesafe.ai/sdk) lists Python and JavaScript, and otherwise points people at the raw HTTP API. There is no Go client, so I wrote one:
  > `https://github.com/Tangerg/typesafe-sdk-go`；`go get github.com/Tangerg/typesafe-sdk-go`
- **来源类型**：`[一手代码]`
- **日期**：2026-09-18 创建，2026-09-19 抓取

### 8. 社区 Go SDK 的可用示例（已验证仓库存在）
- **证据**（https://github.com/Tangerg/typesafe-sdk-go README 原文摘录）：
  > 需要 Go 1.25+，无第三方依赖；包名 `typesafe`
  > ```go
  > client, err := typesafe.NewClient(nil) // reads TYPESAFE_API_KEY
  > result, err := client.SystemOne(context.Background(), &typesafe.SystemOneRequest{
  >     State: "I was charged twice. Please fix this ASAP.",
  >     Questions: typesafe.Questions{
  >         "category": &typesafe.ChoiceQuestion{
  >             Instructions: "What is this ticket about?",
  >             Criteria: typesafe.ChoiceCriteria{"billing": nil, "technical": nil, "other": nil},
  >         },
  >     },
  > }, nil)
  > category, err := result.Answers.Choice("category")
  > fmt.Println(category.Choice, category.Confidence)
  > ```
  > 可运行版本在 `examples/demo`。
- **来源类型**：`[一手代码]`
- **日期**：2026-09-19 抓取（仓库 created 2026-09-18，7★，MIT）

### 9. mcp.so 上搜不到任何 Jev/TypeSafe MCP server
- **证据**：WebFetch `https://mcp.so/search?q=jev`（2026-09-19）返回的是 **Advanced Limitless MCP Server / Claude MCP Protocol Practice / Maxicar Travel / PinRAG / Ahammedshaik** 等**完全无关**条目，无 Jev/TypeSafe。
- **来源类型**：`[一手代码]`（实际抓取页面）
- **通道有效性验证**：页面确实返回了 MCP server 列表（非空白/非报错），说明搜索通道可用，只是无 Jev 匹配。
- **日期**：2026-09-19

### 10. smithery 上搜不到 Jev MCP
- **证据**：WebFetch `https://smithery.ai/?q=jev`（2026-09-19）返回 Keenable Web Search / OneSignal / Medical Terminologies MCP / IBGE Brasil MCP / SIMOSphere AI / AusEcon MCP / Agentery / reportflow-mcp 等**无关**条目，无 Jev/TypeSafe。
- **来源类型**：`[一手代码]`
- **日期**：2026-09-19

### 11. 四大主流 awesome list 均未收录 Jev（每个都过了对照）
检索方式：`gh api -H "Accept: application/vnd.github.raw" /repos/<r>/readme` 后 grep，对照词先行验证通道。

| 列表 | 对照词命中 | jev 命中 | typesafe 命中 | 结论 |
|---|---|---|---|---|
| `Hannibal046/Awesome-LLM`（624 行） | `openai` = 21 | 0 | 0 | 未收录，**对照通过** |
| `e2b-dev/awesome-ai-agents`（5591 行） | `crewai` = 7 | 0 | 0 | 未收录，**对照通过** |
| `punkpeye/awesome-mcp-servers`（1446 行） | `postgres` = 45 | 0 | 0 | 未收录，**对照通过** |
| `OpenRouterTeam/awesome-openrouter`（881 行） | `openrouter` = 77 | 0 | 0 | **未收录**（连 OpenRouter 自家的 awesome 里都没有，对照通过） |

- **来源类型**：`[一手代码]`
- **日期**：2026-09-19
- **补充**：`sindresorhus/awesome` 的 grep 结果**无效**——该 README 极短，对照词 `openrouter` 也是 0 命中，不能作为"未收录"的证据。

### 12. `kitze/skillbox#4` 独立复现了 OpenRouter 端点的坑（与主 agent 实测一致）
- **证据**（https://github.com/kitze/skillbox/issues/4，2026-09-18 原文摘录）：
  > - `typesafe/jev-1.13` is on OpenRouter ($0.042/M input, $0 output) and is reachable *only* via the decisions endpoint. `POST /api/v1/chat/completions` rejects it: *"typesafe/jev-1.13 is a decisions model and cannot be used with the chat/completions endpoint."*
  > - The working endpoint is `https://openrouter.ai/api/alpha/decisions` — no `/v1`. The published docs page lists `/api/v1/api/alpha/decisions`, which 404s.
  > - The request shape is nearly identical to the existing TypeSafe direct call: `{ model, state: { task, skills }, questions: { skill_N: { type: "score", instructions, criteria } } }`
  > - **Caveat: catalog size** — The endpoint rejects large payloads. Testing up to Skillbox's own cap of 200 candidates:
  >   - 120 candidates (~99 KB) — succeeded, 28.7k input tokens
  >   - 150–200 candidates — intermittently failed with `max_tokens_exceeded`, or HTTP 520
  > - Context is 32000 tokens, so a large library can exceed what the endpoint accepts.
  > - One small gap: OpenRouter returns `usage.cost` as a number, while the parser currently reads `providerMetadata.gateway.cost`
- **来源类型**：`[一手代码]`（issue 正文，作者称对新 key 端到端跑通）
- **日期**：2026-09-18 创建，2026-09-19 抓取；该 issue 目前 **open**，评论数为 0。

---

## 可直接抄的代码片段

### 片段 1 — 官方 Python SDK quickstart（原文，未改写）
出处：https://github.com/typesafe-ai/typesafe-sdk-python （README.md）
```python
from typesafe_sdk import Choice, TypeSafeClient

with TypeSafeClient() as client:
    response = client.system_one(
        state={"document": "I was charged twice. Please fix this ASAP."},
        questions={
            "category": Choice(
                instructions="What is this ticket about?",
                criteria={"billing": None, "technical": None, "other": None},
            ),
        },
    )

print(response.choices["category"].choice)
```

### 片段 2 — 官方 JS/TS SDK quickstart（原文，未改写）
出处：https://github.com/typesafe-ai/typesafe-sdk-js （README.md）
```ts
import { choice, TypeSafeClient } from "@typesafe-ai/sdk";

const client = new TypeSafeClient();
const response = await client.systemOne({
  state: { document: "I was charged twice. Please fix this ASAP." },
  questions: {
    category: choice("What is this ticket about?", {
      billing: null,
      technical: null,
      other: null,
    }),
  },
});

console.log(response.answers.category.choice);
```

### 片段 3 — Go SDK quickstart（原文，未改写）
出处：https://github.com/Tangerg/typesafe-sdk-go （README.md）
```go
package main

import (
	"context"
	"fmt"
	"log"

	typesafe "github.com/Tangerg/typesafe-sdk-go"
)

func main() {
	client, err := typesafe.NewClient(nil) // reads TYPESAFE_API_KEY
	if err != nil {
		log.Fatal(err)
	}

	result, err := client.SystemOne(context.Background(), &typesafe.SystemOneRequest{
		State: "I was charged twice. Please fix this ASAP.",
		Questions: typesafe.Questions{
			"category": &typesafe.ChoiceQuestion{
				Instructions: "What is this ticket about?",
				Criteria: typesafe.ChoiceCriteria{
					"billing":   nil,
					"technical": nil,
					"other":     nil,
				},
			},
		},
	}, nil)
	if err != nil {
		log.Fatal(err)
	}

	category, err := result.Answers.Choice("category")
	if err != nil {
		log.Fatal(err)
	}
	fmt.Println(category.Choice, category.Confidence)
}
```

### 片段 4 — Vercel AI SDK 的 `experimental_evaluate`（原文，未改写）
出处：https://github.com/vercel/ai/blob/main/content/providers/01-ai-sdk-providers/105-typesafe-ai.mdx
```ts
import { typeSafeAi } from '@ai-sdk/typesafe-ai';
import { experimental_evaluate } from 'ai';

const result = await experimental_evaluate({
  model: typeSafeAi.evaluationModel('jev-latest'),
  state: {
    message: 'I was charged twice. Please refund the duplicate.',
  },
  questions: {
    department: {
      type: 'choice',
      instructions: 'Which team should handle this?',
      criteria: {
        billing: { includes: ['Charges', 'Invoices', 'Refunds'] },
        technical: ['Bugs', 'Outages'],
        other: null,
      },
    },
    severity: {
      type: 'score',
      instructions: 'How severe is the issue?',
      criteria: ['Cosmetic', 'Workaround exists', 'Blocking; no workaround'],
    },
    requestsRefund: {
      type: 'boolean',
      instructions: 'Is the customer requesting money back?',
    },
  },
});

console.log(result.answers.department.choice);
console.log(result.answers.severity.score);
console.log(result.answers.requestsRefund.probability);
console.log(result.usage);
```

### 片段 5 — Rig（Rust）的类型化 Query（原文，未改写）
出处：https://github.com/0xPlaygrounds/rig/blob/main/crates/rig-typesafeai/README.md
```rust
use rig_typesafeai::{Error, Noul, NoulAnswer, Query};
use serde::{Serialize, Deserialize};

#[derive(Serialize, Deserialize)]
struct Assessment<R, V> {
    ready: R,
    needs_review: V,
}

impl<R: Query, V: Query> Query for Assessment<R, V> {
    type Response = Assessment<R::Response, V::Response>;
    type Output = Assessment<R::Output, V::Output>;

    fn decode(&self, response: Self::Response) -> Result<Self::Output, Error> {
        Ok(Assessment {
            ready: self.ready.decode(response.ready)?,
            needs_review: self.needs_review.decode(response.needs_review)?,
        })
    }
}

let query = Assessment {
    ready: Noul::new("Is this ready to ship?")?,
    needs_review: Noul::new("Does this need human review?")?,
};
```

### 片段 6 — OpenRouter decisions 端点的真实调用形态（来自 issue 报文，非官方文档）
出处：https://github.com/kitze/skillbox/issues/4 引用的原始请求/响应
```json
// 成功：150-200 candidates 会间歇性 max_tokens_exceeded 或 HTTP 520
// 有效路径（无 /v1）：
// POST https://openrouter.ai/api/alpha/decisions
// {
//   "model": "typesafe/jev-1.13",
//   "state": { "task": "...", "skills": [...] },
//   "questions": { "skill_N": { "type": "score", "instructions": "...", "criteria": [...] } }
// }
// 响应含 answers.skill_N.score、usage.input_tokens、usage.output_tokens、usage.cost
```
> 注：以上为 JSON 注释形式转述，issue 原文以散文描述请求形状，**不是可直接复制的完整 body**。主 agent 已一手实测该端点，以主 agent 的实测为准。

---

## 已知的坑（来自 issue / 讨论）

### 坑 1 — 官方 JS SDK 能构造出 API 会拒的请求（400 / 422）
- 出处：https://github.com/typesafe-ai/typesafe-sdk-js/issues/6
- 作者 `Tangerg`，创建 2026-09-18，状态 **open**
- 原文摘录：
  > Both of these type-check, are asserted by the test suite, and are refused by `api.typesafe.ai`. Verified against the live API today on `jev-latest` with v0.6.0.
  > **1. `noul()` with no instructions** — `noul()` defaults `instructions` to `null`, which serializes to `{"type":"noul","instructions":null}`.
  > ```
  > POST /v1/systemone
  > {"model":"jev-latest","state":"s","questions":{"q":{"type":"noul","instructions":null}}}
  >
  > 400 {"detail":"Noul question must have criteria or instructions: q"}
  > ```
  > The API's rule is that a noul needs **at least one of** `instructions` or `criteria`.
  > `{"type":"noul","instructions":null,"criteria":{"true":"it is a greeting","false":"it is not"}}` → 200
  > `{"type":"noul","instructions":null,"criteria":{}}` → 400
  > `{"type":"noul","instructions":null,"criteria":{"true":null,"false":null}}` → 400
  > So an empty criteria object, and one whose sides are both `null`, count as no criteria.
  > **2. `state: null`** → `422 {"detail":[{"type":"missing","loc":["body","state"],"msg":"Field required",...}]}`
  > | state | 结果 |
  > | `""` | 200 |
  > | `{}` | 200 |
  > | `[]` | 200 |
  > | `null` | 422 |
  > | `42` | 422（`string_type` / `dict_type` / `list_type`）|
- **对主 agent 的意义**：证实 base URL 为 `https://api.typesafe.ai/v1/systemone`（与 OpenRouter 的 `/api/alpha/decisions` **不是同一个端点**）。
- 来源类型：`[一手代码]`｜日期：2026-09-18 创建，2026-09-19 抓取

### 坑 2 — Node 20/22 上取消请求会杀掉进程
- 出处：https://github.com/typesafe-ai/typesafe-sdk-js/issues/2
- 作者 `Kewe63`，创建 2026-09-16，状态 **open**
- 原文摘录：
  > On Node 20.20.2 and 22.23.1, cancelling `systemOne` after response headers arrive can terminate the process with an unhandled native `AbortError`, even after the caller successfully catches the SDK's `APIUserAbortError`.
  > This is a **dependency-origin compatibility report**, not a newly discovered Undici defect... already addressed upstream in [Undici #4804](https://github.com/nodejs/undici/pull/4804). The same test passes on Node 24.21.0.
  > - `@typesafe-ai/sdk@0.6.0`，Linux x86_64 / WSL2
  > - Node 20.20.2 / Undici 6.24.1：fails；Node 22.23.1 / Undici 6.27.0：fails；Node 24.21.0 / Undici 7.29.1：passes
- **实践含义**：README 声明 "Node.js 20 or newer"，但**取消/超时路径在 Node 20/22 不可靠**，生产建议 Node 24+。
- 来源类型：`[一手代码]`｜日期：2026-09-16 创建

### 坑 3 — 数字型 Choice 键被推断成 `never`
- 出处：https://github.com/typesafe-ai/typesafe-sdk-js/issues/4
- 作者 `Kewe63`，创建 2026-09-16，状态 **open**
- 原文摘录：
  > `choice(null, { 0: null, 1: null })` is accepted by the public TypeScript API and serializes identically to `choice(null, { "0": null, "1": null })`. However, the former produces `ResultFor<typeof question>["choice"] = never`, while the latter correctly produces `"0" | "1"`.
- 来源类型：`[一手代码]`｜日期：2026-09-16 创建

### 坑 4 — Python SDK 把 `numpy.str_` 静默编码成字符数组
- 出处：https://github.com/typesafe-ai/typesafe-sdk-python/issues/4
- 作者 `iliazintchenko`，创建 2026-09-18，状态 **closed**
- 原文摘录：
  > `_enc_hook` in `_core/json.py` checks `Sequence` before `str`, so a `str` subclass such as `numpy.str_` is sent as a list of characters: `"ARPANET"` becomes `["A","R","P","A","N","E","T"]`. **Requests still succeed, so questions built from numpy arrays are silently corrupted.**
- **实践含义**：这是**静默数据损坏**（请求 200 但语义全错），比报错更危险。
- 来源类型：`[一手代码]`｜日期：2026-09-18 创建

### 坑 5 — 官方 quickstart 文档示例有误
- 出处：https://github.com/typesafe-ai/typesafe-sdk-python/issues/2
- 作者 `mpkrass7`，创建 2026-09-17，状态 **closed**
- 原文摘录：
  > In the [quickstart](https://docs.typesafe.ai/introduction/quickstart) you have the following example: `from typesafe_sdk import Choice, Noul, Score, TypeSafeClient` ...（作者指出输出访问方式有误）
- 来源类型：`[一手代码]`｜日期：2026-09-17 创建

### 坑 6 — 官方 Python SDK 不支持"单一模型同时承载问题与答案"
- 出处：https://github.com/typesafe-ai/typesafe-sdk-python/issues/1（`Fakamoto`，2026-09-16，closed）与 https://github.com/typesafe-ai/typesafe-sdk-python/issues/5（`danielgafni`，2026-09-18，open）
- 原文摘录（#1）：
  > i'd like to define the output as a Pydantic model, pass it to the SDK, and get a validated instance back. right now, i have to define the questions separately and access results through keys like `response.choices["category"].choice`.
- **对照**：Rig（Rust）已经做到了这一点（见片段 5），**Python 生态还在补**。
- 来源类型：`[一手代码]`｜日期：2026-09-16 / 2026-09-18 创建

### 坑 7 — OpenRouter 端点在大 payload 下会间歇失败
- 出处：https://github.com/kitze/skillbox/issues/4（同"逐条发现 12"）
- 关键数字：**120 candidates ≈ 99 KB ≈ 28.7k input tokens 成功；150–200 candidates 间歇 `max_tokens_exceeded` 或 HTTP 520；context 32000 tokens**
- 来源类型：`[一手代码]`｜日期：2026-09-18 创建

### 坑 8 — 决策层项目抱怨 provider 硬耦合
- 出处：https://github.com/browser-use/jev-ultrafast/issues/25（`ycmjason`，2026-09-18，open）
- 原文摘录：
  > The repository currently couples inference directly to the upstream TypeSafe API client. Decoupling this through a provider abstraction—similar to the Vercel AI SDK pattern—would allow callers to pass in their choice of backend, such as Cloudflare Workers AI (`typesafe/jev`), TypeSafe direct, or custom gateway proxies.
  > Inference is tightly coupled to TypeSafe's client SDK and direct API authentication. Alternative platforms hosting the same Jev schema (such as Cloudflare Workers AI) cannot be used without maintainer forks or monkey-patching.
- **含义**：4946★ 的头号项目在 issue 里请求"可换后端"，说明**多网关（TypeSafe 直连 / Cloudflare / OpenRouter / Vercel）并存已成刚需**。
- 来源类型：`[一手代码]`｜日期：2026-09-18 创建

### 坑 9 — Claude Code compaction 插件踩到的 32k 限制规避方案（可复用）
- 出处：https://github.com/tamaratran/fast-jev-compaction（README 原文摘录）
  > - The state is fitted into `maxStateTokens` (25k by default) in stages... If it still does not fit, compaction throws. Tokens are estimated **without a tokenizer** (a word per six letters, half a token per digit, ~one per other symbol), calibrated to land a little above the counts Jev reports.
  > - Questions are split into as many requests as needed so state plus questions stays under `maxRequestTokens` (30k by default, **under Jev's 32k request limit**). The same full state is resent with every request; **requests run concurrently** and their answers are merged.
- **实践含义**：32k 不是"能塞满就塞满"——实际安全线设在 30k；超长 state 只能**并发分片 + 同 state 重发**，代价是重复计费。
- 来源类型：`[一手代码]`｜日期：2026-09-19 抓取

### 坑 10 — MCP 工具集不完整（社区分歧）
- 出处：https://github.com/jkudish/jev-mcp/issues/1（`rimusz`，2026-09-18，open）
- 原文摘录：
  > I'd like to propose adding three coding-loop judgment tools to this MCP, ported from the recipes in [burnigtm/jev-mcp](https://github.com/burnigtm/jev-mcp) (MIT): `jev_coding_loop` ... `jev_review` ... `jev_gate` ... Maintaining a second MCP just for them is worse than extending this one.
- **含义**：MCP 生态严重碎片化——同一份 recipe 在多个仓库间被复制，尚无事实标准。
- 来源类型：`[一手代码]`｜日期：2026-09-18 创建

---

## 存疑与未证实

1. **`Anil-matcha/awesome-jev-by-typesafe` 的 497★ 不可信为"4 天涨粉"。**
   该仓库 `created_at = 2023-05-17`，但描述却是 Jev 主题 → 极可能是**旧仓库改名/复用**（GitHub 上 `created_at` 不随改名变化）。同类问题也需警惕 `jellydn/awesome-typesafe`（191★）——它实际是 TypeScript typesafe 库列表，**与 TypeSafe AI 无关**，属搜索噪声。
   来源类型：`[推测]`｜URL：https://api.github.com/repos/Anil-matcha/awesome-jev-by-typesafe

2. **大量同名 `jev-mcp` / `jev-go` 仓库疑似 AI 批量生成或抢注。**
   `gh search repos "jev mcp"` 返回 8 个独立 `jev-mcp`；`jev go` 返回 5 个 `jev-go`（其中 4 个 0–1★、无 license、描述雷同）。这些仓库**我未逐个验证其代码是否真实可用**，不应视为可靠依赖。
   来源类型：`[推测]`｜日期：2026-09-19

3. **`langchain_typesafe/classifier.py` 里的 `import httpx2`** —— 不是常见的 `httpx`。未核实该包是否真实存在于 PyPI，也未核实该 partner 包是否已发布。
   来源类型：`[推测]`｜URL：https://github.com/langchain-ai/langchain/blob/master/libs/partners/typesafe/langchain_typesafe/classifier.py

4. **二手博客（中文聚合站）提到 `typesafe-computer-use`、`OpenJev`、"Vercel 的 eve"、"每小时 7 美元"等。**
   我核实了项目**确实存在**（`awlevin/typesafe-computer-use`、`ekzhang/openjev-sglang`、`vercel/eve`），但**博客里的具体数字（成本、速度、star）我一律未采信**，本报告只用 `gh api` 返回的数字。
   来源类型：`[二手转述]`｜日期：2026-09-19

5. **`system-one-adapter-python` 的实际用途**：官方描述为"drop-in replacement for `typesafe_sdk`'s `system_one` API, backed by LLM APIs instead of TypeSafe"，即**用 LLM 模拟 Jev 做对照**。它可以用来先把代码结构跑通，但**不代表真实 Jev 的行为**（尤其是概率校准）。
   来源类型：`[官方]`｜URL：https://github.com/typesafe-ai/system-one-adapter-python

6. **`razorsharp16/openjev` 返回 404**（`gh api` HTTP 404），说明该仓库名在搜索索引中存在但实际不可访问（已改名或删除）。检索时不要把搜索索引结果当作"仓库存在"的证据。
   来源类型：`[一手代码]`｜日期：2026-09-19

7. **未找到中文/多语言场景的实测 issue。**
   检索式：`gh search issues "中文 jev" --limit 5` → 0 命中。
   通道验证：`gh search issues "typesafe" --limit 3` → 命中 `symfony/ai | Support TypeSafe Jev`、`jhowtkd/decupa | D1: Adaptador TypeSafe isolado`、`Arize-ai/phoenix | Document TypeSafe JEV integrations`，**通道有效**。
   结论：**用这些关键词组合未命中**，不等于中文场景无人讨论。
   来源类型：`[一手代码]`｜日期：2026-09-19

8. **未找到 429 / 限流 / 并发配额相关的具体 issue。**
   检索式：`gh search issues "jev 429 OR rate limit OR timeout OR error"` → GitHub 把 `429` 解释为 issue 编号，返回 2014–2015 年的无关历史 issue（**检索式本身设计失败**，不作为证据）。改用 `gh search issues "typesafe jev"` 得到的 30 条结果中，标题均为 "Support / Spike / Feature / Proposal" 类**采纳意向**，**没有一条是限流或报错实录**。
   来源类型：`[一手代码]`｜日期：2026-09-19

---

## 信息源清单（URL + 抓取日期）

### GitHub API（全部 2026-09-19 抓取）
- https://api.github.com/users/typesafe-ai
- https://api.github.com/users/typesafe-ai/repos?per_page=100
- https://api.github.com/repos/typesafe-ai/typesafe-sdk-python
- https://api.github.com/repos/typesafe-ai/typesafe-sdk-js
- https://api.github.com/repos/typesafe-ai/skills
- https://api.github.com/repos/typesafe-ai/system-one-adapter-python
- https://api.github.com/repos/typesafe-ai/typesafe-sdk-js/issues/2
- https://api.github.com/repos/typesafe-ai/typesafe-sdk-js/issues/4
- https://api.github.com/repos/typesafe-ai/typesafe-sdk-js/issues/6
- https://api.github.com/repos/typesafe-ai/typesafe-sdk-js/issues/7
- https://api.github.com/repos/typesafe-ai/typesafe-sdk-python/issues/1
- https://api.github.com/repos/typesafe-ai/typesafe-sdk-python/issues/2
- https://api.github.com/repos/typesafe-ai/typesafe-sdk-python/issues/3
- https://api.github.com/repos/typesafe-ai/typesafe-sdk-python/issues/4
- https://api.github.com/repos/typesafe-ai/typesafe-sdk-python/issues/5
- https://api.github.com/repos/kitze/skillbox/issues/4
- https://api.github.com/repos/browser-use/jev-ultrafast/issues/25
- https://api.github.com/repos/jkudish/jev-mcp/issues/1
- https://api.github.com/repos/di-sukharev/opencommit/issues/587
- https://api.github.com/repos/Hannibal046/Awesome-LLM/readme
- https://api.github.com/repos/e2b-dev/awesome-ai-agents/readme
- https://api.github.com/repos/punkpeye/awesome-mcp-servers/readme
- https://api.github.com/repos/OpenRouterTeam/awesome-openrouter/readme
- https://api.github.com/repos/vercel/ai/contents/content/providers/01-ai-sdk-providers/105-typesafe-ai.mdx
- https://api.github.com/repos/langchain-ai/langchain/contents/libs/partners/typesafe
- https://api.github.com/repos/0xPlaygrounds/rig/contents/crates/rig-typesafeai
- https://api.github.com/repos/pydantic/pydantic-ai/contents/docs/models/typesafe.md
- https://api.github.com/repos/Tangerg/typesafe-sdk-go/readme
- https://api.github.com/repos/browser-use/jev-ultrafast/readme
- https://api.github.com/repos/tamaratran/fast-jev-compaction/readme
- https://api.github.com/repos/droidrun/mobile-jev/readme

### gh CLI 检索式（2026-09-19 执行）
- `gh search repos typesafe --limit 20`
- `gh search repos jev --limit 30`
- `gh search repos openrouter --limit 3` ← **对照**
- `gh search repos "jev mcp" --limit 15`
- `gh search repos "typesafe mcp" --limit 15`
- `gh search repos "jev go" / "jev rust" / "jev java" / "jev php" / "jev ruby" / "jev csharp" --limit 8`
- `gh search code "typesafe/jev" --limit 20`
- `gh search code "jev-latest" --limit 20`
- `gh search code "TypeSafeClient" --limit 20`
- `gh search issues "jev typesafe" --limit 25`
- `gh search issues "typesafe jev" --limit 30`
- `gh search issues "typesafe" --limit 3` ← **对照**
- `gh search issues "中文 jev" --limit 5` ← 未命中

### 包注册表（2026-09-19 抓取）
- https://pypi.org/pypi/typesafe-sdk/json
- https://registry.npmjs.org/@typesafe-ai%2Fsdk

### 网页（2026-09-19 抓取）
- https://mcp.so/search?q=jev （无 Jev 相关结果，通道有效）
- https://smithery.ai/?q=jev （无 Jev 相关结果，通道有效）

### 官方文档（经 GitHub README 间接引用，未直接抓取）
- https://docs.typesafe.ai/ （多处 README 引用）
- https://typesafe.ai/
- https://console.typesafe.ai/
