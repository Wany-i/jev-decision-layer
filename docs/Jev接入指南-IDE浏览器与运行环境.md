# Jev 接入指南 —— 进 IDE、进浏览器、要什么环境

> 本文档由 **AI 进行调研、整理与提交**（2026-09-19）。证据分级与出处见文内标注；非官方材料，与模型厂商无隶属关系。

**日期**：2026-09-19　**承接**：`docs/Jev模型使用调研.md`
**状态**：本轮新增 4 个产物，其中 3 个已跑通验收（含真开 Chrome 跑完整闭环）

---

## 0. 入口（先看这张表）

| 优先级 | 文件 | 一句话 |
|---|---|---|
| **必读** | `docs/Jev接入指南-IDE浏览器与运行环境.md` | 本文件：怎么接进 IDE / 浏览器，要什么环境 |
| **必读** | `docs/Jev模型使用调研.md` | 上一轮：它是什么、接口长什么样、实测延迟与成本 |
| **参考** | `docs/jev_client.py` | 决策层**唯一代码入口**（脚本/MCP/浏览器三层共用一个库） |
| **参考** | `docs/jev_mcp_server.py` | MCP server —— 让 IDE 里的 agent 能调它 |
| **留档** | `docs/示例\browser_decision_demo.mjs` | 浏览器 + 决策层闭环示例（真开 Chrome 验过） |

> 原 `jev_probe.py` 已删除 —— 它的功能被 `jev_client.py --probe` 完整取代，不再保留重复实现。

---

## 1. 先回答你的三个问题

**① 它如何使用？**
一个 HTTP POST。`POST https://openrouter.ai/api/alpha/decisions`，body 里三样东西：`model` + `state`（要判断的素材）+ `questions`（声明好的问题）。返回类型化答案 + 概率 + 置信度。**没有对话、没有上下文、没有记忆** —— 每次都是独立一次判断。

**② 普通 IDE 用不了它吧？**
**对，当"模型"用不了。** IDE 的 AI 插件（Copilot / Cursor / Cline / Codex 类）选模型走的是 `chat/completions` 协议，而 Jev 是决策模型，用这个端点调它会**直接 400**（我实测过：`... is a decisions model and cannot be used with the chat/completions endpoint`）。它不生成文本，所以放进"模型下拉框"这件事本身不成立。
**但能让 IDE 用上它** —— 把它包成 **MCP 工具**，让 IDE 里的 agent 主动调用。差别是：**工具身份，不是模型身份。**

**③ 怎么接进浏览器做浏览器操作？**
**Jev 不驱动浏览器。** 三个硬约束：

| 约束 | 实测/出处 | 后果 |
|---|---|---|
| **无视觉** | 端点元数据 `modality: text->decisions`、`input_modalities: ["text"]`【实测】 | **它看不了截图**。页面状态必须先被你**文本化**才能给它 |
| **无工具调用** | 端点元数据 `supported_parameters: []`；响应体只有 `model` / `answers` / `usage` / `id` / `provider`，**没有 tool_calls 字段**【实测】 | 它不能点按钮、不能执行动作 |
| **无记忆** | 设计如此 | 它不知道上下文，你塞什么它看什么 |

所以正确分工是：**执行层**（puppeteer / Playwright / 影刀RPA / 紫鸟CLI / 这里的 agent-browser 技能）读页面、做动作 → 把状态文本化 → **Jev 在分叉点当裁判** → 你的代码按置信度决定自不自动做。

---

## 2. IDE 怎么接：三张牌，只有一张该打

| 接法 | 能不能 | 说明 |
|---|---|---|
| **MCP 工具**（推荐） | ✅ | IDE 里的 agent 把 Jev 当工具调。**这是唯一语义正确的接法** |
| 脚本中间层 | ✅ | 你的脚本调 Jev，脚本再被 agent 作为命令调用。够用，但多一层 |
| 造 OpenAI 兼容假壳 | ⚠️ 不推荐 | 能让它出现在下拉框里，但 IDE 会拿它写代码 → 必然崩。**它不会写代码，这是设计上的"不会"，不是能力不足** |

### 推荐：MCP 工具

`jev_mcp_server.py` 已写好，暴露一个工具 `jev_decide`。注册到 IDE 的 MCP 配置里：

```json
{
  "mcpServers": {
    "jev": {
      "command": "python",
      "args": ["docs/jev_mcp_server.py"],
      "env": { "OPENROUTER_API_KEY": "sk-or-v1-..." }
    }
  }
}
```

- Cursor：项目根建 `.cursor/mcp.json`，或 Settings → MCP
- Cline：`cline_mcp_settings.json`
- 配好后重启客户端生效

**验收（不用 IDE 也能测）**：
```bash
python "docs/jev_mcp_server.py" --selftest
```
✅ 我跑过了：`initialize` / `tools/list` / `tools/call` 三种消息全通，返回真实判断。

**接进 IDE 之后它长什么样**：agent 遇到"这算不算紧急""该归哪一类""这个方案要不要拦"这类分叉时，自己调 `jev_decide`，拿到的是**固定取值 + 置信度**，不是一段要它再去解析的文字。

---

## 3. 浏览器怎么接

### 关键动作：**你自己做 state 文本化**（Jev 看不见页面）

```javascript
const state = {
  url: page.url(),
  title: await page.title(),
  visible_text: (await page.evaluate(() => document.body.innerText)).slice(0, 3000),
  inputs: await page.evaluate(() => [...document.querySelectorAll('input')]
            .map(i => ({ id: i.id, placeholder: i.placeholder, filled: !!i.value }))),
  buttons: await page.evaluate(() => [...document.querySelectorAll('button')].map(b => b.innerText)),
  error_text: '',
};
```
→ 完整可跑版本：`docs/示例\browser_decision_demo.mjs`

### 适合 Jev 的决策点 vs 不适合

| ✅ 适合（语义分叉，规则难写死） | ❌ 不适合（留给代码） |
|---|---|
| 这页是不是登录成功了 | 元素坐标、等待时间、循环次数 |
| 这个弹窗该点哪个按钮 / 该不该关 | 金额、价格、库存的算术 |
| 这条报错该重试、跳过还是放弃 | 阈值比较、排序 |
| 这个商品页是不是目标类目 | 批量动作的副作用与幂等 |
| 页面内容算不算"异常/风控提示" | 精确的日期与时区换算 |

**判据**：一个熟悉业务的人**看几秒就能给直觉判断**的，适合 Jev；需要算出来的，留给代码。

### 实测的闭环长这样（真开 Chrome 跑过）

```
页面状态（文本化）→ Jev：ready=0.79 · next_action=fill_phone(conf 0.99) · risk=0.8
                  → 门控：三项都 auto
                  → 代码执行 puppeteer page.type('#phone', ...)
                  → 新状态：inputs[phone].filled = true  ← 闭环成立
```

---

## 4. 需要什么环境

### 最小要求：**只要一个能发 HTTP POST 的东西**

| 层 | 本机现状【实测】 | 说明 |
|---|---|---|
| 调用端 | ✅ Python 3.13.14（管理版） | 只需标准库，**不用装 requests** |
| 调用端 | ✅ Node 22.22.2 | 只需内置 `fetch` |
| 浏览器执行 | ⚠️ Python 侧**没装** Playwright | 但 ✅ Node 侧有 `puppeteer` + `puppeteer-core` |
| 浏览器 | ✅ Chrome（`C:\Program Files\Google\Chrome\Application\chrome.exe`）+ Edge | puppeteer 直接指向本机 Chrome 即可，无需另下浏览器 |
| 本 WorkBuddy 环境 | ✅ 已有 `agent-browser` / `playwright-cli` 技能 | 在这台机器上做浏览器操作走这两个技能，Jev 只当决策工具 |

**结论**：你这台机器**现在就能跑**，不用装任何东西。要补的是"你打算在哪一层写业务逻辑"，不是运行时。

### Jev 本身从哪接

| 通道 | 端点 | 备注 |
|---|---|---|
| **OpenRouter**（你现在这条） | `POST https://openrouter.ai/api/alpha/decisions` | 已跑通；$0.042/M 输入，输出免费 |
| TypeSafe 直连 | `POST https://api.typesafe.ai/v1/systemone` | 需在 console.typesafe.ai 申请（早期访问，候补） |
| Cloudflare / Vercel / Netlify AI Gateway | 各自网关 | 免管 key 的托管通道，模型 id 记作 `typesafe/jev` |

---

## 5. "基础知识库"到底要不要

**不要 —— Jev 没有检索、没有记忆、没有 RAG。** 它只知道你塞进 `state` 的东西。

所以知识库的位置变了，不是消失：

```
知识库（向量/表格/文档）
      ↓  在你的代码里检索
      ↓  裁剪出【这次判断真正需要的几条】
      ↓  拼进 state
    Jev 判断
```

**两个必须知道的副作用**（第三方复述官方口径）：
- **state 里塞无关内容会掉准确率** —— 不是"多给点总没错"。这条和你在技术栈那章写的"噪声淹没信号"是同一件事。
- **它的语言能力有限**："以英文为主训练，其他语言需按自己的场景评估"。我实测中文可用（confidence 打到 1.00），但**在你的业务语料上必须自己验**。

---

## 6. 生产前必看的坑（本轮新增，多数来自第三方实测）

> **口径说明**：本节是当时（2026-09-19 早些时候）写的。外网侧更完整、且经第四方独立复核的实测数据在
> `docs/Jev外网用法调研.md` 的 §5（官方宣称 vs 独立实测，含校准 ECE 数据）
> 与 §7（**已被证伪、不能引用的结论清单**）。**有冲突时以后者为准。**

1. **阈值不能跨问题类型搬运。** 同一个问题用 `noul` 问和用 `choice` 问，数值差得很远 —— 官方例子 `noul=0.22` vs `choice` 的 `P(yes)=0.01`；第三方实测 `rm -rf node_modules` 那个问题分别是 0.60 和 0.81。**它们回答的不是同一件事。**
2. **不要指望两个问题之间有算术恒等。** 一个问题正着问、反着问两个 `noul`，官方加起来 1.19，第三方实测 0.91。**不变量要在代码里守，不要在模型里求。**
3. **`confidence` 不是独立输出**，是从概率分布算出来的统计量 —— 分布尖就高，扁平就低。所以**扁平的分布是诊断信号：多半是你的 `criteria` 写错了**，不是模型糊涂。
4. **阈值要按"动作"分别定**，不是全局一个数 —— 做错的代价不同（"加否定词"错了很便宜，"暂停投放"错了很贵）。我在 `jev_client.py` 的 `gate()` 里留了这个结构。
5. **量大不等于贵**：一个请求塞十几个问题几乎不额外花钱（并行评估），官方口径称批量比串行省 12 倍、快 10 倍。**多问几个原子判据，比反复调一次划算。**
6. **规模上限**：`choice` 最多 255 个选项，`score` 2–10 个层级。
7. **上线前做影子测试**：先旁路跑，和你的历史人工决策比对，**扫多个置信度阈值**看准确率/覆盖率，再让它影响线上。这个建议官方自己也提。

---

## 7. 已验证的产物与验收命令

```bash
P=python

# 1) 决策层：最小连通验证 ✅ 已验（ok=0.98, 1.73s, $0.0000125）
$P "docs/jev_client.py" --probe

# 2) 决策层：示例 + 置信度门控 ✅ 已验
$P "docs/jev_client.py" --demo --repeat 2 \
   --thresholds '{"action":0.6,"urgency":0.5}'

# 3) MCP server ✅ 已验（三种消息全通）
$P "docs/jev_mcp_server.py" --selftest

# 4) 浏览器闭环 ✅ 已验（真开 Chrome，填入手机号成功）
NODE=/c/Users/WY/.workbuddy/binaries/node/versions/22.22.2-3/node.exe
$NODE "docs/示例/browser_decision_demo.mjs" --mock
$NODE "docs/示例/browser_decision_demo.mjs"
```

---

## 8. 待你定（我不替你决定）

1. **要不要做影子对照表**：挑 20–50 个真实广告关键词，Jev 跑一遍 vs 你 v3.14 规则的人工判断，看准确率与置信度是否吻合。**有这张表才谈得上进 skill。**
2. **key 挪位置**：现在明文在 `环境变量 OPENROUTER_API_KEY（本仓库不含密钥）`。建议移到环境变量 —— 上面 MCP 配置里我用了 `env` 字段，那种方式比读桌面文件干净。
3. **`jev-latest` 还是写死版本**：我默认写死 `typesafe/jev-1.13`。别名会随版本漂，你一旦按某个阈值调过参，就必须写死。
