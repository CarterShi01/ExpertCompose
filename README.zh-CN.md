# ExpertCompose

ExpertCompose 把书籍、论文、Agent 对话历史和业务资料，编译成 Agent 可以直接导航和使用的、可追溯的专家系统。核心产物叫 **ExpertNet**：它不是一堆松散 Prompt，而是经过版本化、评估、审批和发布的 Role/Skill/Tool 结构树。

第一版 MVP 已实现完整本地闭环：资料导入与脱敏、证据定位、离线或模型辅助合成、Contexture 项目生成、结构与行为评估、人工审批、不可变发布，以及 CLI/MCP 两种调用方式。

## 最快体验

```bash
uv sync --extra dev
uv run expertcompose --workspace .demo init
uv run expertcompose --workspace .demo project create research-review \
  --title "研究评审" --objective "基于资料生成可追溯的专业答案"
uv run expertcompose --workspace .demo ingest research-review examples/sources/review.md \
  --authorization "我有权处理这份示例资料"
uv run expertcompose --workspace .demo compose research-review
uv run expertcompose --workspace .demo build research-review
uv run expertcompose --workspace .demo evaluate research-review
uv run expertcompose --workspace .demo approve research-review --approved-by reviewer
uv run expertcompose --workspace .demo publish research-review --published-by reviewer
```

默认 `heuristic` 合成器完全离线、可复现，适合验证产品流程；生产专家质量仍应使用更强的模型、领域评审和真实任务评测。

## 核心边界

- 导入内容永远只是“证据”，不会变成系统指令，也不会被执行。
- 模型只能生成严格 Schema 的草案，不能直接生成并运行任意 Python。
- Tool 只是能力需求，只有经过明确绑定和审核后才成为可执行 Tool。
- 结构检查不是效果证明；可通过 Host 回执接入真实 Agent 的留出任务评测。
- 发布必须同时满足：构建成功、评估通过、具名审批、必要 Tool 已绑定。

详细设计见 [docs/design.md](docs/design.md)，实施计划见
[docs/implementation-plan.md](docs/implementation-plan.md)，竞品与开源项目资料见
[docs/competitive-landscape.md](docs/competitive-landscape.md)。关于“像 USB 一样连接 Agent”的
用户场景、统一交互流程，以及真正负责组队、路由、协作、归因和演化的 MetaSkill Kernel，
见[中文产品调研](docs/product-research-and-metaskill-kernel.zh-CN.md)和
[英文权威设计](docs/product-research-and-metaskill-kernel.md)。英文文档和代码是权威版本，
本文件为中文入口说明。
