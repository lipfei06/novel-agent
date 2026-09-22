# 章节规划智能体 ReAct 改造需求分析

> 版本 v1.1 ｜ 状态：待评审 ｜ 改造对象：stage4b 章节规划师（`agents/packet.py`）
> 关联：E2E 测试报告 §4-B（reference_seeds 错位）、成本优化报告（RAG 环节"不智能"三缺陷）
> v1.1 追加：ask_author 作者澄清机制 + stage4r 新节点

---

## 1. 背景与问题

### 现状：规划师是"单发盲盒"

当前 stage4b 规划师是**一次性的结构化生成**：读卷计划/总纲/人物/正典注入 → 单次 creative 调用 → 直接产出 WriterPacket。这个形态有三个已实证的问题：

| # | 问题 | 证据 |
|---|---|---|
| P1 | **reference_seeds 语义错位**：字段无说明，规划师按字面理解成"写作参考建议"，输出的是叙事风格长句（"参考《红楼梦》餐桌暗流""GIA 钻石分级标准"），而非用于检索前文的实体关键词 | 两本书全部 20+ 章的 seeds 实测：无一条是可直接检索的短实体词 |
| P2 | **检索质量不可验证**：这些错位长句被直接用于向量检索 → 召回不相关内容污染提示词；且检索是规划后无条件执行，规划师不知道自己"提名"的种子能查到什么 | 改进清单 P2：无相关性阈值、无结果反馈 |
| P3 | **规划与正典脱节**：正典注入（事件账本/道具卡）是静态文本，规划师"读过"但无法主动核对——第 13/14 章两次献茶礼、三次获取流水这类节拍重复，规划阶段无从自查 | 摘要对比实证 |

### 根因

规划师是**单发盲盒**：没有观察外部世界（向量库/账本/图谱）的能力，reference_seeds 是"闭门造车式提名"，产出无法自证质量。

## 2. 目标与非目标

**目标**
1. 规划师改造为 **ReAct 循环**：思考 → 调用只读工具查证 → 观察结果 → 再思考……直到认为规划依据充分；
2. 通过查证闭环根治 P1：种子的有效性由"实际检索结果"验证，而非模型臆测；
3. 查证所得的**前文原文片段**直接沉淀为本章 `<reference>` 上下文，打通"规划查证 → 写作引用"；
4. 全程有界（轮数/每轮条数硬上限），失败自动降级回单发路径。

**非目标**
- 不改动写手智能体（写侧研究循环保留，两者分工：规划师查证"写什么"，写手研究员核实"细节对不对"）；
- 不引入写权限（全部工具只读）；
- 不追求一次到位的通用 ReAct 框架——只服务规划这一个场景。

## 3. 设计

### 3.1 ReAct 循环协议

```
[system] 你是章节规划师。先思考本章设计，需要事实依据时调用工具查证；
         资料充分后输出最终任务书。
[user]   卷计划 / 总纲(裁剪) / 人物 / 伏笔账本 / 正典事实(事件账本+道具卡+已用标题)

循环（≤ max_rounds=3，每轮 actions ≤ 4）：
  Thought: 本章规划要点 + 还缺什么依据
  Action:  {"tool": "query_vector", "args": {"keyword": "怀表", "top_k": 4}, "reason": "核实怀表伏笔原文"}
  Observation: [检索到的场景片段...]
  ……（资料充分后）
  Final: {"title":..., "goal":..., ..., "reference_seeds": [...]}   ← WriterPacket 全量
```

- **Thought/Action** 走 `invoke_structured`（schema：`{reasoning, actions:[{tool,args,reason}]}`）——沿用 writer_research 的"决策归模型、执行归代码"模式；
- **每条 Action 必须带 reason**——审计与调试依赖；
- **工具执行是确定性代码**（新增规划员工具模块 `planner_tools.py`），全部只读。

### 3.2 工具清单（规划员专用，全部只读）

| 工具 | 查什么 | 底层 |
|---|---|---|
| `query_vector` | 关键词检索前文场景切片（验证种子有效性 / 收集原文引用） | LongTermMemory.search |
| `query_timeline` | 某角色截至当前章的关系与事件 | TemporalGraph.neighbors |
| `get_chapter_summary` | 指定章的摘要 | MidTermMemory.get |
| `list_recent_events` | 最近 N 章事件账本（防桥段重复） | state.event_ledger |
| `get_prop_facts` | 道具既定事实（防道具矛盾） | state.prop_registry |
| `check_titles` | 章节标题查重 + 返回已用清单 | state.chapters 标题 |

与写手研究员工具的差异：多了 `check_titles` 与 `list_recent_events`（规划师的核心职责是防重复），少了卷进度（写手才需要）。

### 3.3 产出与回填

- **Final 输出**：WriterPacket 全量（schema 同现状），其中 `reference_seeds` **必须来自实际执行过的 query_vector 关键词**（提示词硬约束 + 代码校验：未在执行过的查询中出现过的种子剔除）；
- **`research_context` 回填**：循环中所有 Observation 拼接为规划上下文，注入 stage5 的 `<reference>` 块——**规划时查证过的原文，写作时直接引用**，替代当前"错位种子 → 盲检索"的链路。

### 3.4 降级与边界

| 情形 | 行为 |
|---|---|
| 循环内结构化输出失败 2 次 | 降级回现行单发生成（`generate_writer_packet` 直调），报 warning |
| Ollama/本地模型无工具调用能力 | 同降级路径（决策走 invoke_structured，与模型无关，天然兼容） |
| max_rounds 用尽仍不输出 Final | 取已有 Observations 生成"研究上下文"，按单发路径产出任务书 |
| `auto_plan=false`（用户手填任务书） | 不启用 ReAct 循环 |

### 3.5 配置

```yaml
planner:
  react_enabled: true       # 总开关（关=现行单发）
  max_rounds: 3             # 循环上限
  max_actions_per_round: 4
```

## 4. 接口变更

| 位置 | 变更 |
|---|---|
| `agents/planner_research.py`（新增） | ReAct 循环 + 工具注册表 |
| `agents/packet.py` | `generate_writer_packet` 新增可选参 `research_context`（查证所得注入 prompt） |
| `graph.py` stage4b | `react_enabled` 时先跑 ReAct 循环再单发生成 |
| `routes.py` 章节任务 | 同上（章节页快捷路径） |
| `reference_seeds` 校验 | 长度 ≤12 字符过滤 + 剔除未执行的查询词（治 P1 错位） |

## 5. 成本估算

- 每章新增：ReAct 循环 1~3 轮 × cheap/creative 决策调用 ≈ +2~8k token 输入（决策短、观察为检索结果文本）；
- 对冲：query_vector 的 Observation 让 stage5 的 RAG 检索**可省略**（规划已验证的引用直接复用），抵扣部分；
- 净增估算：**+8~15% / 章**——买的是规划质量与种子正确性，可开关。

## 6. 验收标准

1. mock 模式：循环确定性可测（mock 工具返回固定观察，1 轮后 Final）；
2. 真实模式：对 zhihu_style 第 5 章实测——reference_seeds 全部为 ≤12 字实体词、且能检索回非空结果；
3. 标题不与已用 20 章重复；
4. 降级路径：工具异常/轮数耗尽时产出合法任务书，流程不中断；
5. 开关关闭时行为与现状逐字节一致。

## 7. 遗留说明

- 章节助手聊天照旧自由文本，不进本循环（规划是流水线环节，聊天是作者交互）；
- "每次都检索浪费资源"的写作侧无条件 RAG：正典注入 + 规划查证接管后，写作侧 RAG 可降级为"仅当规划未提供引用时执行"——本轮不动，下轮评估。

---

## 8. v1.1 追加：ask_author 作者澄清机制

### 8.1 需求

规划时存在**只有作者能裁决的方向分叉**（卷计划事件弧冲突、正典与聊天意图分歧、主线/伏笔孰先）。规划师应能在生成任务书前向作者提问，而不是擅自决定。

### 8.2 设计（关键决策：澄清放在循环前的干净边界）

**不在 ReAct 循环内打断**。LangGraph 的 resume 语义是节点从头重执行——循环内打断会让前序轮次的 LLM 决策重跑（结果不确定、成本重复）。因此：

```
stage4a → 【stage4r 规划研究节点】 → stage4b 任务书生成+确认
stage4r 内部（单节点，原子）：
  ① 澄清判断（cheap 模型）：基于卷计划/总纲/正典/讨论，
     产出 0~2 个必须由作者裁决的方向性问题（每题带选项+默认项）
  ② 若有问题 → interrupt({type:"ask_author", questions}) 挂起等作者
  ③ 作者作答 → 节点重执行 → interrupt 返回答案 → 研究循环（纯只读查询，无打断）
  ④ 产出 digest（查证上下文）写入 state.planner_digest
stage4b 读取 digest → 生成任务书
```

把澄清放在最前端的理由：LangGraph 的 resume 是"从头重放"，中断位置越靠前、重放代价越小；澄清问题在重放时会重新生成一次（cheap 调用），但**返回的答案是绑定在 checkpoint 上的原答案**，与作者看到的题目一致。

### 8.3 前端

「新建章节」页的"流水线待确认"区域识别 `payload.type == "ask_author"`：
渲染问题卡（问题文本 + 选项按钮 + 自定义输入 + 默认项标注），作者提交后走
`POST /confirm {"action":"answer","data":{"answers":[...]}}` → 规划继续。

### 8.4 纪律约束（防滥用提问）

- 每次规划 **≤2 问**（代码硬限）；
- 问题必须**带选项与默认项**（作者可一键采纳默认）；
- prompt 明令：资料能查到的不问、执行细节不问、品味问题不问。

### 8.5 成本

澄清判断 1 次 cheap 调用 + 挂起零成本 + 答案回流后规划照常。相比"作者事后返工一章"的成本，可忽略。
