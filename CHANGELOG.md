# 变更日志

本文件记录本项目的所有重要变更。
格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [未发布]

### 文档

- README 补齐两条主线，让使用者能看清整体逻辑：
  - **功能**：决策层 / 注册表 / 接入壳 / 质量四组，逐项说明各管什么
  - **上游实现逻辑**：一次 `decide()` 的八步链路（装载注册表 → 裁剪 → 组装 → 发往上游 →
    收答案 → 抽主结论 → 门控 → 硬约束），每一步附"为什么必须存在"
- 新增同一次真实调用的**三段原样快照**（上游请求体 / 上游响应体 / 本层返回），
  以及**字段映射表**与「上游不提供、由本层补上」对照表
- 记录一次实测：同一输入重复调用，数值会有小波动（`confidence` 0.35 / 0.36，
  `无效花费` 0.76 / 0.74）→ **判定必须靠门控，不能靠记结果**

### 计划中

- 打包为可 `pip install` 的包（当前为免安装：复制目录即可用）
- 适配层增加更多后端（当前默认 OpenRouter 的 decisions 端点）
- 阈值标定脚本：用你的历史人工决策扫多个阈值，输出准确率 / 覆盖率曲线

## [0.1.0] - 2026-09-19

首个公开版本。

### 新增

- **决策层** `decision.py`
  - 对外唯一入口 `decide(决策名, 业务上下文)`，返回 `结论 + 置信度 + 门控`
  - `state` 按注册表声明的字段白名单**裁剪**，被裁掉的字段在返回的 `trimmed` 里列出
  - 置信度门控在本层完成：对外只给 `gate=auto|review`，原始概率需显式 `debug=True`
  - `gate()` 对 `noul` 用"离 0.5 的距离"折算（该类答案没有 confidence 字段）
  - **硬约束 `guards`**：注册表可声明高危信号，命中即强制升级为 `review`；
    只允许收紧、不允许放宽
  - 缺字段 / 注册表不合法 / 后端非 200 一律显式抛 `DecisionError`，不静默降级
  - 可重试状态码退避重试
- **适配层**：唯一与模型耦合处 `_call_backend()`，换后端只改这一个函数
- **注册表** `registry/`
  - `ad_keyword_action` —— 广告关键词下一步动作（中文示例）
  - `browser_step` —— 浏览器/桌面自动化的风险闸门（中文示例，演示 `guards`）
  - `support_triage` —— 客服分流（英文示例）
- **接入壳**
  - `mcp_server.py` —— MCP stdio 服务，工具名 `list_decisions` / `decide`（**不带底层模型名**），
    支持 `--selftest` 免客户端自测
  - `decision.py` 自带 CLI：`list` / `show` / `decide`
- **示例** `examples/quickstart.py` —— 三个可直接跑的场景
- **测试** `tests/test_offline.py` —— 28 项离线单元测试（不需要 API key、不联网）
- **CI** `.github/workflows/ci.yml` —— Python 3.10 / 3.12 / 3.13 三档矩阵
- **社区文件** —— CONTRIBUTING / SECURITY / CODE_OF_CONDUCT / issue 模板 / PR 模板

### 说明

- 仅依赖 Python 标准库（3.10+），无第三方依赖
- 仓库内不含任何密钥，运行时从环境变量 `OPENROUTER_API_KEY` 读取
- **非官方项目**，与 TypeSafe AI 无隶属关系

[未发布]: https://github.com/Wany-i/jev-decision-layer/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Wany-i/jev-decision-layer/releases/tag/v0.1.0
