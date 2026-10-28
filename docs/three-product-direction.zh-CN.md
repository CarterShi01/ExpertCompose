# Contexture、ExpertCompose、one-creator

状态：产品方向的中文翻译  
更新：2026-10-28

```text
one-creator                  Project / Scope / Authorization
     |  把已授权的 Scope 映射到一个确定版本的团队
     v
ExpertCompose                素材 -> Blueprint -> ExpertNet
     |  渲染团队
     v
Contexture                   Role / Skill / Tool
```

三个产品保持独立：

- **Contexture** 运行选定的 Role/Skill/Tool，不理解项目、用户和业务权限。
- **ExpertCompose** 制造、评估、发布和提供专家团队；**ExpertNet 就是团队**。
- **one-creator** 管项目、协作、权限、Work、Hand、Hermes session 和项目 Tool。

设计只新增一个持久关系：

```text
ScopeBinding: project://apollo -> release rel_123 -> team/engineering/*
```

`scope_ref` 对 ExpertCompose 是不透明字符串，由 Scope 所属产品解释和鉴权；
Binding 固定到不可变 release。Role 路径已经承担组织和路由，因此不再增加
Namespace，也不再增加第二个 Team 模型。

ExpertCompose 个人版和企业版共用一套代码：个人版本地运行且不需要权限系统；
企业版只在宿主边界增加身份、权限、审计和可扩展存储。

本阶段全部持久概念：

```text
Contexture:    Role / Skill / Tool
ExpertCompose: Workspace / Blueprint / ExpertNet / ScopeBinding
one-creator:   Project / Scope / Authorization
```
