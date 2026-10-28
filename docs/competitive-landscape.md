# Competitive and open-source landscape

Research date: 2026-10-28. Links below point to the primary project repository,
paper, or vendor page reviewed on that date. Project capabilities evolve; this
document is a product-positioning reference, not a benchmark result.

## Executive view

The market has strong products for creating individual agent Skills, converting
a paper into callable Tools, learning from failed trajectories, manually
assembling multi-agent workflows, and building managed agent workforces. The
less-covered combination is: heterogeneous evidence in, explicit
provenance-bearing knowledge IR, a structured Role/Skill/Tool expert graph,
neutral evaluation receipts, and governed reusable releases out.

ExpertCompose should therefore avoid positioning itself as another agent
framework or prompt generator. Its category is an **evidence-to-expert-system
compiler and lifecycle**. ExpertNet structure and governance are the moat;
Contexture supplies an efficient, progressively disclosed execution surface.

## Direct and near-direct projects

| Project | What it does | What to learn | Gap relative to ExpertCompose |
|---|---|---|---|
| [SkillNet](https://github.com/zjunlp/SkillNet) | Creates agent Skills from prompts, repositories, documents, and trajectories; organizes and routes a skill graph. | Broad source adapters, graph retrieval, skill-quality checks. | Primarily individual skills rather than a governed Role/Skill/Tool expert system with source-level provenance and releases. |
| [Paper2Agent](https://github.com/pstaif/paper2agent) and its [Nature paper](https://doi.org/10.1038/s41586-026-11044-y) | Converts research papers and associated code into tested MCP servers/Tools. | Paper/code pairing, executable scientific Tools, test generation. | Optimized for one paper-to-agent/tool path, not general session/book evidence or reusable responsibility trees. |
| [SkillClaw](https://github.com/AMAP-ML/SkillClaw) | Captures agent sessions and evolves, deduplicates, verifies, and shares reusable Skills across agents including Hermes, Codex, and Claude. | Passive session collection, cross-agent packaging, deduplication. | Session-derived Skills are not the same as provenance-rich expert-team composition and publication governance. |
| [EvoSkill](https://github.com/sentient-agi/EvoSkill) | Evolves agent skills/prompts from failed trajectories and evaluates them on held-out tasks. | Failure-driven improvement and held-out evaluation. | Focuses on optimization of skills/prompts rather than multi-source knowledge compilation and structural expert systems. |
| [SkillAdaptor](https://github.com/zjunlp/SkillAdaptor) | Attributes failures to steps, creates or revises Skills, and validates revisions on held-out cases for multiple coding/agent hosts. | Attribution before mutation and accept/reject validation. | Downstream skill maintenance rather than the upstream evidence-to-ExpertNet compiler and registry lifecycle. |
| [MUSE-Autoskill](https://github.com/Akshay2695/muse_autoskill) | Derives reusable skills from agent experience. | Experience-to-skill automation and packaging. | Narrower artifact model and governance surface than a full expert graph. |
| [Distill](https://github.com/seipass/distill) | An evidence-grounded agent Skill for distilling sources into reusable knowledge. | Traceable synthesis discipline and compact knowledge artifacts. | A Skill/workflow itself rather than a standalone product compiling and governing many expert systems. |
| [skill-distill](https://github.com/fielding/skill-distill/blob/main/SKILL.md) | Packages a workflow for extracting and refining reusable agent knowledge. | Simple, inspectable skill authoring conventions. | No durable multi-project evidence, expert graph, build, evaluation, and release lifecycle. |
| [DeepMind workflow-skill-creator](https://github.com/google-deepmind/science-skills/blob/main/skills/workflow_skill_creator/SKILL.md) | Guides conversion of scientific workflows into reusable skills. | Domain-workflow decomposition and scientific reproducibility. | Human/agent-authored workflow skill, not heterogeneous automatic expert-system composition. |

## Adjacent authoring and agent platforms

| Product | Relevance | Positioning implication |
|---|---|---|
| [uberSKILLS](https://github.com/uberskillsdev/uberskills) | Visual environment to author, test, and deploy agent Skills. | A future ExpertCompose UI can learn from visual testing, while keeping compilation/provenance as the core. |
| [CrewAI](https://github.com/crewAIInc/crewAI) | Framework for manually defining agents, crews, flows, knowledge, skills, and Tools. | ExpertCompose can generate/export governed expertise for orchestration frameworks rather than competing as another runtime. |
| [Dify](https://github.com/langgenius/dify) | Broad LLM application platform with knowledge pipelines, agents, workflows, Tools, and MCP integration. | Integrate as a consumer/Host; differentiate through deep expert artifact provenance and lifecycle. |
| [Microsoft AutoGen](https://github.com/microsoft/autogen) | Multi-agent prototyping framework and Studio. The repository now states it is no longer maintained by Microsoft. | Do not bind the product identity to one orchestrator; export portable artifacts and MCP surfaces. |
| [Relevance AI Invent 2.0](https://relevanceai.com/press/invent-2-0) and [AI Workforce](https://relevanceai.com/workforce) | Commercial flow that learns business processes from material/interviews and produces managed agent workforces with Tools, evaluations, and governance. | Closest high-level commercial validation of the category; ExpertCompose differentiates through open/local-first artifacts, evidence provenance, explicit Role/Skill/Tool IR, and Contexture portability. |
| [ExpertForge](https://boardesign.it/en/applications/) | Commercial naming collision around expert/AI application construction. | Avoid the `ExpertForge` name and own the `ExpertCompose`/`ExpertNet` terminology consistently. |

## Feature comparison

This table describes product emphasis observed in the referenced materials,
not an assertion that absent features can never be implemented.

| Capability | ExpertCompose v0.1 | Skill-learning tools | Paper2Agent | Agent frameworks | Managed workforce platforms |
|---|---:|---:|---:|---:|---:|
| Books/docs/papers/sessions as inputs | Yes | Varies | Paper + code | Usually manual/RAG | Yes |
| Exact source locators and evidence IDs | Yes | Varies | Paper-oriented | Usually external | Vendor-specific |
| Explicit Role tree | Yes | Usually no | No | Often manual | Yes |
| Skill procedures | Yes | Core | Tool-oriented | Yes/manual | Yes |
| Inert Tool requirements before binding | Yes | Usually no | Generates Tools | Manual | Vendor-managed |
| Standalone MCP-ready artifact | Yes | Some | Yes | Some | Platform-bound |
| Offline complete baseline | Yes | Some | Limited by workflow | Some | No |
| Held-out evaluation contract | Yes | Strong in EvoSkill/SkillAdaptor | Tests | Framework-dependent | Yes |
| Human approval + immutable release | Yes | Rare | Project-dependent | External | Yes |
| Open/local-first product state | Yes | Often | Yes | Often | No |

## Strategic recommendations

1. Keep the target independent `ExpertBlueprint` and make ExpertNet diff,
   review, and provenance visible. A graph that only exists in generated Python
   loses the product advantage.
2. Make evaluation comparative: baseline versus ExpertNet, held-out tasks,
   navigation cost, evidence correctness, and regression thresholds.
3. Treat session learning as one ingestion mode, not the whole product. This
   absorbs the Hermes-style “accumulate skills” use case without narrowing the
   category.
4. Integrate with agent frameworks and MCP Hosts rather than building a new
   agent loop. The compiler should be useful to Hermes, Codex, Claude, CrewAI,
   Dify, and future hosts.
5. Preserve the distinction between a Tool requirement and executable binding.
   Paper2Agent's tested executable path is valuable, but arbitrary code
   generation needs a stronger sandbox and review phase than v0.1.
6. Add an editorial/evaluation UI only after the artifact contract is stable;
   otherwise the UI becomes the product database and weakens portability.

## Multi-agent organization and meta-skill research

The product's MetaSkill Kernel is not a set of ingestion prompts. It is the
control layer that manages expert-team responsibilities, routing, topology,
coordination, verification, attribution, and reorganization. The detailed
method mapping and adoption cautions are maintained in
[product-research-and-metaskill-kernel.md](product-research-and-metaskill-kernel.md).

Primary references reviewed on 2026-10-28 include
[AutoAgents](https://github.com/OWD-AI/AutoAgents),
[MetaGPT](https://github.com/FoundationAgents/MetaGPT),
[DyLAN](https://arxiv.org/abs/2310.02170),
[ADAS](https://arxiv.org/abs/2408.08435),
[GPTSwarm](https://arxiv.org/abs/2402.16823),
[AFlow](https://arxiv.org/abs/2410.10762),
[AgentPrune](https://arxiv.org/abs/2410.02506),
[AgentDropout](https://aclanthology.org/2025.acl-long.1170/),
[Meta-Agent](https://arxiv.org/abs/2605.25233), and
[AMOD](https://arxiv.org/abs/2610.27531). They provide research methods rather
than production guarantees; several results are benchmark-specific and the
2026 papers are especially recent.

## Naming conclusion

`ExpertCompose` describes the product action: composing operational expert
systems from evidence. `ExpertNet` describes the generated structured artifact.
Together they communicate more than “skill generation” while avoiding a hard
dependency in the public name on Contexture or one agent runtime.
