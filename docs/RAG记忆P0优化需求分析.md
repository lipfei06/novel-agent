# RAG 记忆系统 P0 优化需求分析

> 版本：v1.1 ｜ 日期：2026-09-18 ｜ 状态：P0 已实现（commit 73f402c）；P1 已评审进入实现
> 范围：长期向量库（`memory/long_term.py`）、时序知识图谱（`rag/temporal_graph.py`）、记忆更新（`memory/update.py`）、组合检索（`rag/retriever.py`）、章节删除（`api/routes.py`）

---

## 1. 背景与问题

RAG 记忆链路（章节定稿 → 场景切片入向量库 → 关系入时序图谱 → 写作时双路检索）已跑通，但本轮代码走查发现四个 P0 级缺陷，共同特征是：**造成检索噪声或一致性风险，且修复成本低**。

### P0-1 超长场景语义平均化
- **现状**：一个场景（SceneBlock）= 一个 chunk，无二次切分。3000 字大场面压成一个向量。
- **后果**：向量表征被"平均"，场景两端的内容检索排序靠后甚至进不了 top-k；bigram 模式下长文本的字符二元组集合庞大，相似度进一步失真。
- **触发条件**：写手产出超长场景（高潮戏常见）。

### P0-2 chunk 无元数据，删除无法回滚
- **现状**：向量库存 `{chunks: [原文], vectors: [...]}`，不记录每块来自哪一章。
- **后果**：删除章节时向量无法精准移除（当前实现完全不回滚）；检索结果无来源标注，写手无法判断信息新旧。
- **关联**：`delete_saved_chapter` docstring 已声明"长期向量不回滚"是权宜之计。

### P0-3 图谱边缺卷号，删除回滚不可实现
- **现状**：边只存 `chapter`（章号）不存卷号。
- **后果**：多卷书里"卷1第3章"与"卷2第3章"的边无法区分——即使实现按章回滚也会误伤。这是必须先修的**数据模型缺陷**，否则 P0-4 无从谈起。

### P0-4 `add_diff` 定位脆弱
- **现状**：按整块文本精确匹配（`chunks.index(old)`）定位旧块。
- **后果**：场景文本改动一个字符即失配，退化为"旧块残留 + 新块追加"，与删除残留同性质的噪声源。

---

## 2. 目标与非目标

**目标**
1. 超长场景自动二次切分，保住检索表征质量；
2. 向量 chunk 与图谱边携带章节归属（vol + ch），删除章节可精准回滚两库；
3. 检索结果可标注来源（第几卷第几章），写手可判断信息新旧；
4. `add_diff` 支持按元数据定位，不再依赖文本完全相等；
5. 旧数据文件自动迁移，不丢数据、不需要手工干预。

**非目标（本轮不做）**
- 过短场景合并（min-length 分块）——另行迭代，需与元数据中的场景组成列表联动；
- 记忆整体重建命令（rebuild）——P1；
- 检索相关性阈值与重排（rerank）——P2；
- 换用 FAISS / SQLite-vss 等向量引擎——量级不需要。

---

## 3. 需求详述

### FR-1 超长场景二次切分

| 项 | 内容 |
|---|---|
| 规则 | 单 chunk 超过 `MAX_CHUNK_LEN=1200` 字时，按段落（`\n`）边界贪心打包切分；单段仍超长则按句子（。！？…）切；句子级仍超长按字符硬切 |
| 位置 | `LongTermMemory.add` 入口内部，所有调用方自动生效 |
| 元数据 | 切分产生的子块复制原 meta 并追加 `part`（第几块，1 起）与 `parts`（总块数） |
| 常量 | `MAX_CHUNK_LEN` 模块常量，暂不入配置（YAGNI） |

**验收**：2000 字场景（含多个段落）入库后 chunk 数 > 1；检索原文任一片段可命中；短场景（≤1200 字）行为与现状完全一致。

### FR-2 向量 chunk 元数据

| 项 | 内容 |
|---|---|
| 存储 | 新增平行数组 `meta`：`[{vol, ch, scene, key, part?, parts?}, ...]`，`key = "{vol}_{ch}"` |
| 写入 | `update_chapter_memory` 传入每场景的 `{"vol", "ch", "scene", "key"}` |
| 兼容 | 旧文件无 `meta` 字段：加载时补 `[None] * len(chunks)`；`meta=None` 的块不参与按章删除、不参与来源标注 |
| 保存 | `_save` 序列化三数组 `{mode, chunks, vectors, meta}` |

**验收**：新入库数据带 meta；用旧格式文件构造实例不报错且功能正常。

### FR-3 来源标注检索

| 项 | 内容 |
|---|---|
| 接口 | `LongTermMemory.search(query, top_k=4, with_source=False)`；`retrieve(..., annotate=False)` 透传 |
| 格式 | meta 存在时块前缀 `[第{vol}卷第{ch}章]`，如 `[第1卷第3章] 原文……` |
| 启用点 | 写作上下文构建（`_build_writing_context`）开启；写手研究工具（`_q_search_memory`）保持原样（其输出供研究员 JSON 消费） |

**验收**：带 meta 的库 `with_source=True` 检索结果含前缀；`with_source=False` 与现状逐字节一致（回归保障）。

### FR-4 图谱边携带卷号 + 按章回滚

| 项 | 内容 |
|---|---|
| 数据模型 | 边由 `{a,b,kind,chapter,note}` 迁移为 `{a,b,kind,vol,ch,note}` |
| 旧数据迁移 | `_load` 时发现 `chapter` 无 `vol` 的边：转为 `{vol: 1, ch: chapter}`（存量项目均为单卷，假设成立并在代码注释声明） |
| 排序/过滤 | 所有章序比较改为 `(vol, ch)` 元组序；`neighbors(entity, vol, ch)` 过滤 `(e.vol,e.ch) > (vol,ch)` 的边 |
| 回滚接口 | `remove_chapter(vol, ch)`：删除该章全部边，单次落盘；节点集不清理（无伤大雅） |
| `evolution` | 返回边附 `chapter` 派生字段（`f"{vol}_{ch}"`）保持展示层兼容 |

**验收**：多卷场景下卷1第3章的回滚不影响卷2第3章；旧格式 graph.json 加载后行为与迁移前一致（现有测试全部通过即证）。

### FR-5 `add_diff` 按元数据定位

| 项 | 内容 |
|---|---|
| 签名 | `add_diff(old, new, meta=None)` |
| 定位顺序 | ① meta 含 `key`+`scene`：按元数据精确删旧块；② 退化：文本精确匹配（现状逻辑）；③ 均失败：仅追加新块（现状退化路径） |
| 说明 | ①修复"改一个字就失配"；②③保证旧调用方行为不变 |

**验收**：场景文本被改动后，用 meta 定位仍能替换旧块不残留。

### FR-6 删除章节回滚两库

| 项 | 内容 |
|---|---|
| 位置 | `delete_saved_chapter`，在中期摘要移除之后 |
| 向量 | `LongTermMemory.remove_chapter(vol, ch)`——按 meta.key 删除；**必须以 `embed_fn=get_embedder(cfg)` 构造实例**（模式不一致会导致整库被误清空，既有隐患，此处显式规避） |
| 图谱 | `TemporalGraph.remove_chapter(vol, ch)` |
| 文档 | 端点 docstring 更新：删除"不回滚"表述，注明回滚范围与限制（meta 缺失的旧数据不回滚） |

**验收**：删除已入库章节后，两库中该章内容消失；再写同号新章无残留串扰。

---

## 4. 接口变更汇总

| 模块 | 变更 | 兼容性 |
|---|---|---|
| `LongTermMemory.add` | `(chunks, metas=None)` 新增可选参数 | 旧调用不变 |
| `LongTermMemory.search` | `(query, top_k=4, with_source=False)` 新增可选参数 | 旧调用不变 |
| `LongTermMemory.add_diff` | `(old, new, meta=None)` 新增可选参数 | 旧调用不变 |
| `LongTermMemory.remove_chapter` | **新增** | — |
| `TemporalGraph.add_edge(s)` | `chapter` 参数改为 `vol, ch` | **破坏性**：调用方 update.py 同步修改；测试更新 |
| `TemporalGraph.neighbors` | `(entity, vol, ch)` | **破坏性**：retriever 同步修改 |
| `TemporalGraph.remove_chapter` | **新增** | — |
| `retrieve` | `(…, current_vol=0, current_chapter=0, annotate=False)` | 旧调用需补 `current_vol`（routes 已同步） |

破坏性变更仅 2 处，均为内部接口、调用方全在项目内，无外部消费者。

---

## 5. 测试计划

1. **存量回归**：150 个既有测试全绿（test_rag.py / test_memory.py 按 API 变更同步更新，断言语义不变）；
2. **新增用例**：
   - 超长场景切分：块数、子块长度上限、检索命中子块；
   - 元数据往返：入库带 meta → 持久化 → 重载保留；
   - 旧格式迁移：无 meta 的 long_term.json、含 `chapter` 的 graph.json 加载后行为正常；
   - 按章回滚：remove_chapter 后检索/邻接均不含该章内容，他章不受影响；
   - 来源标注：with_source 前缀存在性；
   - add_diff by meta：文本已改动仍可替换。
3. **端到端**：启动后端，删除一个已入库章节，检查 vector_stores/long_term.json 与 temporal_graph 文件中该章内容消失。

---

## 6. 风险与回滚

| 风险 | 缓解 |
|---|---|
| 模式不一致构造 `LongTermMemory` 导致整库清空（既有隐患，本改动新增一个构造点） | delete 端点显式传 `embed_fn`；代码注释警示 |
| 旧数据迁移假设（chapter→vol=1）对多卷存量不成立 | 存量项目均为单卷；文档声明；未来 rebuild 命令可整体重算 |
| 切分导致 chunk 数增多、检索变慢 | 一章 3~5 块 → 至多 8~10 块，量级无虞（暴力扫描毫秒级） |
| 检索结果带前缀改变写手 prompt 格式 | 仅写作上下文启用，默认关闭；无测试依赖原文格式 |

---

## 7. P1 追加需求：记忆重建（rebuild）

> v1.1 追加。P0 落地后，删除/回滚的不一致已被缩小，但仍需一个**兜底阀**：
> 任何原因导致的记忆脏污（历史残留、embedding 升级、关系抽取提示词升级、
> 手工误改存储文件）都应能通过"从事实源全量重算"恢复。

### FR-7 记忆重建

| 项 | 内容 |
|---|---|
| 事实源 | LangGraph State 中的全量 `chapters`（已接受章节），一切派生存储可由此重算 |
| 范围 | `scope=vector`：仅向量库；`scope=graph`：仅图谱；`scope=all`：两者 |
| 流程 | 清空目标库 → 按章号升序重放"场景切片入库 + 关系抽取入图"（复用 P0 重构出的 `_index_chapter`） |
| 不动 | 中期摘要不重算（LLM 成本高且自身增删改生命周期已自洽）；正文与 State 不动 |
| 成本 | 向量：每场景一次 embedding（dense 模式）；图谱：每章一次 cheap 模型抽取（真实模式）。mock 模式零成本确定性 |
| 接口 | `memory.update.rebuild_memory(chapters, cfg, long_term=None, graph=None, characters=None, progress=None) -> dict`；API `POST /projects/{id}/memory/rebuild` body `{"scope": "vector"\|"graph"\|"all"}` |
| 守卫 | 无已接受章节时 400；scope 非法时 400；`LongTermMemory` 一律带 `embed_fn` 构造（防模式误清空） |
| 重构 | `update_chapter_memory` 的向量+图谱部分提取为 `_index_chapter`，写入与重建共用同一份索引逻辑——**重放即等价重建**的关键 |

**附带修复**：`agents/writer_tools.py` 的 `search_memory` 工具构造 `LongTermMemory` 缺 `embed_fn`——dense 模式项目下该工具静默返回空结果（模式不匹配）。补上 `embed_fn=get_embedder(ctx.cfg)`。

**验收**：
1. 重建后向量库 chunk 集 = 全量章节场景按同一规则切分的结果；图谱边 = 各章关系边并集；
2. 删除章节制造残留 → rebuild(all) → 两库无残留；
3. scope=vector 不动图谱，scope=graph 不动向量；
4. mock 模式全流程离线确定性，测试覆盖。
