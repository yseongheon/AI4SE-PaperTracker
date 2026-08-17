# AI4SE PaperTracker — 项目开发文档

> 本文件是项目的**唯一事实来源（single source of truth）**：技术选型、架构约定、开发规范、决策记录均以此为准。
> 给 Claude 的协作硬性要求见第 2 章「决策记录」：**任何方案选择必须先列出多个候选并解释优劣，由用户拍板**。

## 1. 项目简介

**AI4SE PaperTracker** 是一个自动跟踪「AI 赋能软件工程（AI4SE）」论文的网站：定时从 arXiv 拉取最新论文，判定其在 CCF-A 软件工程会议（ICSE / FSE / ASE / ISSTA）的发表情况，识别 AI4SE 论文并按研究主题分类，最终以 Web 页面展示。

### 核心功能

1. **自动爬取**：每日定时从 arXiv 拉取 cs.SE（软件工程）分类的最新论文（APScheduler 调度，手动命令兜底）
2. **A 会判定**：通过 DBLP 收录记录判定论文是否发表于 CCF-A 会议，重点展示 A 会论文
3. **AI4SE 识别与分类**：关键词初筛 + DeepSeek LLM 精标，判断论文是否属于 AI4SE，并打主题标签（代码翻译、代码修复、代码生成、缺陷检测等）
4. **中文摘要**：LLM 为每篇 AI4SE 论文生成中文摘要
5. **展示**：论文列表（分页/搜索/按主题/会议/年份筛选）、论文详情（摘要、作者、双链接：arXiv + DBLP/DOI、主题标签）、主题与会议趋势图表（DR-020：**各研究主题论文数量随时间的折线图**（按周/月聚合）、会议分布对比、年份分布等，前端展示要求丰富）

### 技术栈（已定，详见决策记录）

- **前端**：Vue 3 + TypeScript + Vite + Element Plus + ECharts（Pinia、Vue Router、Axios）
- **后端**：Python + FastAPI + SQLAlchemy 2.x + SQLite + APScheduler（Alembic 迁移、httpx 客户端）
- **外部服务**：arXiv API、DBLP API、DeepSeek API

### 重要认知

- **arXiv 是预印本平台，不是会议**。arXiv 上的论文 ≠ 会议发表。「发表于 CCF-A 会」的唯一可信依据是 DBLP 收录记录（ICSE/FSE/ASE/ISSTA 的 proceedings 在 DBLP 均有完整收录）。
- 同一论文的 arXiv 预印本与正式发表版是**同一条数据记录**（双链接展示），不是两条（关联规则见第 5 章）。

## 2. 决策记录

### 决策规则（对 Claude 的硬性要求）

1. 任何技术方案选择（框架、库、架构、流程），必须先列出 **≥2 个候选方案**及优劣对比（成本/复杂度/适用场景），由**用户拍板**；Claude 不得自行选定。
2. 拍板后写入下表，此后**整个项目期长期遵守**；本表与其他章节冲突时，以本表为准并同步修订其他章节。
3. 变更旧决策：在表中**新增一行**，候选方案列注明「替代 DR-XXX」，原行保留不删（保留决策历史）。

### 决策表

| 编号 | 决策项 | 候选方案 | 选定 | 理由摘要 | 日期 | 决策人 |
|---|---|---|---|---|---|---|
| DR-001 | 后端框架 | FastAPI / Flask / Django | **FastAPI** | 原生异步契合爬虫限流；自动生成 Swagger 文档方便前后端联调；API-first 契合前后端分离架构 | 2026-08-17 | 用户 |
| DR-002 | 数据源 | arXiv API + DBLP / 加 OpenAlex / 加 Semantic Scholar | **arXiv API + DBLP** | arXiv 免费无认证、按分类+时间窗拉取；DBLP 是会议收录权威来源，补足「A 会判定」缺口。影响：引用数（citation_count）暂不采集，后续需要可再议引入 OpenAlex | 2026-08-17 | 用户 |
| DR-003 | A 会范围 | SE 四大 A 会 / +期刊 TSE、TOSEM / +AI 顶会 / +PL、系统类 | **SE 四大 A 会：ICSE、FSE/ESEC-FSE、ASE、ISSTA（CCF-A）** | 聚焦 AI4SE 核心阵地；CCF 名单存 venues 表（数据而非代码），后续扩展无需改代码 | 2026-08-17 | 用户 |
| DR-004 | AI4SE 识别方式 | 纯关键词 / 纯 LLM / 混合 | **关键词初筛 + LLM 精标（混合）** | 初筛免费、快速、可解释；LLM 精标质量高并直接产出主题标签+中文摘要；混合兼顾成本与质量 | 2026-08-17 | 用户 |
| DR-005 | LLM 供应商 | Claude API / DeepSeek / Qwen / 本地 Ollama | **DeepSeek API** | 国内直连无障碍、中文摘要质量好、成本低；英文论文分类能力足够 | 2026-08-17 | 用户 |
| DR-006 | 数据库 | SQLite / PostgreSQL / MySQL | **SQLite** | 零配置；本项目只有爬虫一个写入方（单写者），量级（年万级）完全够用；SQLAlchemy+Alembic 迁移保底，日后可平滑切 PG | 2026-08-17 | 用户 |
| DR-007 | 前端组件库 | Element Plus / Naive UI / Ant Design Vue | **Element Plus + ECharts** | 生态最大、中文文档最全；表格/筛选/表单组件成熟，契合论文列表+筛选侧栏+趋势图场景 | 2026-08-17 | 用户 |
| DR-008 | 定时任务 | APScheduler / 系统计划任务+CLI / Celery | **APScheduler** | 单机单任务场景进程内定时器即可，零额外依赖；手动 CLI 命令保留作兜底与调试入口 | 2026-08-17 | 用户 |
| DR-009 | 版本管理与远程备份 | 仅本地 git / GitHub 私有仓库 / Gitee 私有仓库 | **git + GitHub 私有仓库（gh CLI 管理）** | 远程备份才能真正防止代码丢失；gh CLI 已安装可全程代操作；私有仓库不公开代码 | 2026-08-17 | 用户 |
| DR-010 | GitHub 推送通道 | HTTPS 直连 / HTTPS 走本地代理 / SSH github.com:22 / SSH over 443 | **SSH over 443（remote 为 `git@ssh.github.com:…`）** | 实测国内 443 被阻断、代理节点不可用；ssh.github.com:443 可达；该地址形式同时绕过全局 git 的 HTTPS 重写规则（`.gitconfig` 中 insteadOf），不改全局配置 | 2026-08-17 | 用户 |
| DR-011 | 爬取范围 | 仅 cs.SE / cs.SE 全量 + cs.AI 关键词过滤 | **cs.SE 全量 + cs.AI 关键词过滤** | cs.SE 是软件工程主分类全量收；cs.AI 论文量大，仅按 AI4SE 关键词过滤进入候选，兼顾召回与噪声 | 2026-08-17 | 用户 |
| DR-012 | 首次历史回填深度 | 近 6 个月 / 近 1 年 / 不回填 | **近 6 个月** | 在 DBLP API 限流约束下几十分钟级可完成；数据量足够支撑趋势展示 | 2026-08-17 | 用户 |
| DR-013 | Python 依赖与环境管理 | uv / pip+venv / conda | **uv** | 现代标准，自动管理 Python 版本+依赖+锁文件；通过 `python -m uv` 调用（Scripts 不在 PATH） | 2026-08-17 | 用户 |
| DR-014 | 前端包管理器 | npm / pnpm / yarn | **npm** | Node 自带零额外依赖；registry 已配 npmmirror 国内镜像 | 2026-08-17 | 用户 |
| DR-015 | DBLP 匹配策略 | 会议流批量拉取 / 逐篇标题搜索 | **会议流批量拉取** | 按「会议+年份」从 DBLP 批量拉取四大 A 会近两年全部论文（约 10~20 个请求），本地用标题归一化+作者+年份匹配；请求数极少、命中率近 100%（DBLP 收录必命中）；逐篇搜索需 5000+ 请求（2~4 小时）且标题改动会漏检。辅助：解析 arXiv journal_ref/comments 字段作线索 | 2026-08-17 | 用户 |
| DR-016 | 数据库 schema 初始化 | Alembic 全管理 / create_all + Alembic | **Alembic 全管理** | autogenerate 生成含全部 8 张表的初始迁移，此后所有变更走 migration；迁移历史完整、从零可重建库、日后切 PG 平滑 | 2026-08-17 | 用户 |
| DR-017 | M1 爬取范围执行策略 | 只爬 cs.SE / 内置关键词规则同步启用 cs.AI | **M1 先只爬 cs.SE** | keyword_rules 表结构先建留空，M1 逻辑单一好验证；cs.AI 关键词过滤待 M2 规则精装后启用（DR-011 长期目标不变） | 2026-08-17 | 用户 |
| DR-018 | LLM 精标范围 | 全部论文精标 / 仅关键词初筛候选精标 | **仅关键词初筛候选** | 全库 3771 篇需 ~3700 次调用（估 $5-15）成本高；关键词初筛预计收敛到 300-600 篇，成本降 10 倍；非 AI4SE 论文无需主题标签与中文摘要 | 2026-08-17 | 用户 |
| DR-019 | M2 执行授权 | 全程逐项询问 / M2 内自主决策 | **M2 内自主决策（用户授权）** | 用户授权 Claude 在 M2 范围内自行权衡技术决策（模型选型、规则设计、实现细节），仅重大不可逆事项（如付费全量调用）需询问；附带决策：LLM 模型选 **deepseek-chat**（DeepSeek 最便宜档，分类/中文摘要能力足够） | 2026-08-17 | 用户 |
| DR-020 | 前端展示增强 | 基础列表 / 主题+会议趋势图表丰富展示 | **趋势图表丰富展示** | 用户补充需求：不同领域（主题）论文数量随时间的折线图、会议分布对比等，前端展示丰富；后端 /api/stats/trends 需支持按 topic/venue/year 分组的时间序列 | 2026-08-17 | 用户 |

### 默认值 / 待确认项（M0 启动时逐项确认，未确认前按默认执行）

| 项 | 默认值 | 说明 |
|---|---|---|
| 爬取范围 | cs.SE 全量 + cs.AI 关键词过滤 | cs.SE 是软件工程主分类；cs.AI 仅按 AI4SE 关键词过滤进入候选 |
| 历史回填深度 | 近 6 个月 | 脚本支持加深；受 DBLP API 限流（1–2s/请求）约束，深回填需分批或改用本地 dump |
| 主题分类法 | 初版 10 主题（见第 5 章 topics 表） | 存库数据驱动，可增删改，无需改代码 |
| 前端语言 | TypeScript（strict 模式） | — |
| 文档语言 | 中文（技术名词保留英文） | — |

## 3. 系统架构总览

```
APScheduler 每日定时触发（手动 CLI 兜底）
  │
  ▼
① arXiv 拉取         export.arxiv.org/api/query：cat:cs.SE(+cs.AI) 近 N 天窗口，≥3s/请求
  │
  ▼
② 归一化 + 去重入库   title_normalized 指纹；arxiv_id 唯一索引 upsert（幂等）
  │
  ▼
③ DBLP A 会匹配      标题搜索（1–2s/请求）→ 作者+年份校验 → venue ∈ CCF-A 名单
  │                  命中回填 dblp_key/venue/DOI；多候选歧义 → match_status=pending 人工复核
  │
  ▼
④ 关键词初筛         keyword_rules 表规则（免费、可配置、可解释）
  │
  ▼
⑤ DeepSeek 精标      结构化 JSON：is_ai4se / topics[] / summary_zh / confidence
  │                  并发受控、失败重试、成本上限开关
  │
  ▼
⑥ 入库更新 + 审计     crawl_runs 记录 fetched/new/updated/failed 计数
  │
  ▼
⑦ FastAPI REST API   /api/papers、/api/topics、/api/venues、/api/stats/trends
  │
  ▼
Vue 3 前端            列表页 / 详情页 / 趋势页（Element Plus + ECharts）
```

| 模块 | 位置 | 职责 |
|---|---|---|
| arXiv 客户端 | backend/app/crawler/arxiv_client.py | 按分类+时间窗拉取论文元数据（Atom XML 解析），限流+指数退避+分页 |
| DBLP 客户端+匹配器 | backend/app/crawler/dblp_client.py、matcher.py | 标题搜索、候选校验、A 会判定、预印本↔正式版关联 |
| 分类器 | backend/app/crawler/classifier.py | 关键词初筛 + DeepSeek 精标（结构化输出校验） |
| 调度器 | backend/app/crawler/scheduler.py | APScheduler 每日任务，挂载于 FastAPI 生命周期 |
| API 层 | backend/app/api/ | 路由 → 服务 → ORM 三层 |
| 前端 | frontend/src/ | 页面/组件/状态/请求封装 |

## 4. 项目目录结构

```
AI4SE-PaperTracker/
├── CLAUDE.md                  # 本文档：开发规范与决策记录（唯一事实来源）
├── README.md                  # 项目说明（面向访客）
├── .gitignore                 # data/、.env、node_modules/、__pycache__/、dist/
├── .env.example               # 环境变量模板
├── backend/
│   ├── pyproject.toml         # 依赖：fastapi uvicorn sqlalchemy alembic httpx apscheduler openai(DeepSeek 兼容) pydantic-settings
│   ├── alembic/               # 数据库迁移
│   ├── app/
│   │   ├── main.py            # FastAPI 实例、路由挂载、启动/关闭时挂载与卸载 scheduler
│   │   ├── config.py          # pydantic-settings 读取 .env
│   │   ├── db.py              # engine / SessionLocal
│   │   ├── models/            # SQLAlchemy ORM：paper.py author.py venue.py topic.py crawl_run.py keyword_rule.py
│   │   ├── schemas/           # Pydantic 请求/响应模型（与 ORM 分离）
│   │   ├── api/               # 路由：papers.py topics.py venues.py stats.py
│   │   ├── services/          # 业务层（路由与爬虫共用）
│   │   └── crawler/           # arxiv_client.py dblp_client.py matcher.py keyword_rules.py classifier.py scheduler.py rate_limiter.py
│   ├── scripts/               # run_crawl.py run_classify.py backfill.py seed_venues.py seed_topics.py
│   └── tests/                 # test_normalize.py test_matcher.py test_rate_limiter.py ...
├── frontend/
│   ├── package.json           # vue3 vite typescript pinia vue-router axios element-plus echarts
│   ├── vite.config.ts         # dev proxy：/api → http://127.0.0.1:8000
│   └── src/
│       ├── main.ts / App.vue
│       ├── api/               # axios 实例 + 资源封装（papers.ts topics.ts stats.ts）
│       ├── router/            # 路由：列表 / 详情 / 趋势
│       ├── stores/            # Pinia：filterStore、paperStore
│       ├── types/             # 与后端 schema 对齐的 TS 接口
│       ├── components/        # PaperCard、FilterSidebar、TopicTag、TrendChart...
│       └── views/             # PaperListView、PaperDetailView、TrendView
└── data/                      # SQLite 数据库文件（gitignore，不入库）
```

## 5. 数据模型

| 表 | 关键字段 | 说明 |
|---|---|---|
| **venues** | id, short_name(FSE), full_name, type(conference/journal), rank(CCF-A/B/C/none), dblp_key | CCF 名单是数据不是代码。初版仅四大 A 会；改名单=改数据 |
| **papers** | id, title, title_normalized(索引), abstract, arxiv_id(unique 可空), arxiv_url, dblp_key(unique 可空), doi(可空), venue_id(FK 可空), year, published_at, updated_at, is_ai4se_candidate, is_ai4se_confirmed, match_status(none/matched/pending/rejected), summary_zh, status(fetched/matched/classified/ready), created_at, updated_at | 核心表。双链接展示（arXiv + DBLP/DOI）；索引：(title_normalized)、(venue_id, year) |
| **authors** | id, name, name_normalized(unique) | v1 仅小写/去点归一；同名歧义不处理 |
| **paper_authors** | paper_id(FK), author_id(FK), position | N:M 关联，复合唯一 (paper_id, position) |
| **topics** | id, slug(code_generation), name_zh(代码生成), description, parent_id(可空), is_active | 主题分类法是数据。初版 10 主题：code_generation 代码生成 / code_repair 代码修复 / code_translation 代码翻译 / code_summarization 代码摘要 / defect_detection 缺陷检测与定位 / testing 自动化测试 / analysis 软件分析 / requirements 需求工程 / llm4se_general LLM4SE 通用 / other 其他 |
| **paper_topics** | paper_id, topic_id, confidence, method(keyword/llm), created_at | 多标签+置信度+标注来源（可追溯） |
| **crawl_runs** | id, source(arxiv/dblp/llm), started_at, finished_at, status, fetched_count, new_count, updated_count, failed_count, error | 每次运行审计日志，支持失败重跑 |
| **keyword_rules** | id, topic_id(可空), pattern, field(title/abstract/any), enabled | 关键词初筛规则可配置化 |

**预印本 ↔ 正式发表版关联规则**（全项目最关键的逻辑）：

1. 匹配键 = `title_normalized`（小写、去标点/空白/LaTeX 命令）+ 第一作者姓氏 + 年份 ±1 窗口；
2. 命中后**不新建记录**，回填同一条 Paper 的 `dblp_key/venue_id/doi`，前端同时展示 arXiv 与 DBLP/DOI 双链接；
3. 多个候选命中时保守处理：`match_status=pending` 进人工复核，不自动关联；
4. arXiv 论文版本更新（v1→v2）按 arxiv_id 更新摘要与更新时间，保留首次发现时间。

## 6. 爬取管线规范

### 阶段顺序

① arXiv 拉取 → ② 归一化去重入库 → ③ DBLP A 会匹配 → ④ 关键词初筛 → ⑤ LLM 精标 → ⑥ 审计入库。任何一次运行都必须按此顺序；②③ 幂等（可安全重跑）。

### 去重策略

- `papers.arxiv_id` 唯一索引 + upsert 语义 → 每天重跑不产生重复数据
- `papers.dblp_key` 唯一索引 → DBLP 侧同样幂等
- 标题指纹 `title_normalized` 用于跨源匹配（见第 5 章关联规则）

### 限流红线（硬性规定，违反会被封 IP）

| 外部服务 | 规则 |
|---|---|
| arXiv API | 每请求间隔 **≥3 秒**、单连接；每页 max_results ≤ 500；带描述性 User-Agent；指数退避重试（1s/2s/4s/8s，最多 3 次）；submittedDate 搜索索引有约 1–2 天延迟，增量窗口 3 天已容错 |
| DBLP API | 请求间隔 **2 秒**（取红线 1–2s 的保守档）；429 时尊重 Retry-After 头；**实测教训：短时间内高频连续请求会触发临时封禁（连接被重置 WinError 10054，约数分钟到半小时解除）——单次匹配运行前估算请求数，不要连续重复跑匹配任务** |
| DeepSeek API | 并发受控（默认 2），失败重试最多 2 次，超时跳过并记录 |

> DBLP 实测补充（2026-08-17）：
> - **翻页参数是 `f`（first），不是 `start`**：`start` 会被当前节点静默忽略，每页返回相同 100 条（曾导致无限循环拉取 115+ 页）——这是「h 参数无效」表象的真相
> - `stream:xxx:` 查询每页返回条数由 `h` 控制（实测 h=100/h=50 均生效），响应 `result.hits.@total` 是可靠的总数，用于分页终止；ICSE 全历史 7894 条
> - **stream key 与 DBLP 集合 key 不同**：FSE 用 `stream:conf/sigsoft:`、ASE 用 `stream:conf/kbse:`（`conf/fse`/`conf/ase` 均查不到）——已存 venues.stream_key 列
> - 排序并非严格年份倒序，不能靠「整页全旧」截断；逐年 `AND year:YYYY:` 修饰符部分节点不可靠
> - 限流极敏感：突发 >3~6 个请求/分钟即返回非 JSON 错误页/503/429/连接重置，休息 1~2 分钟恢复；客户端已实现「失败等 90s 重试同页、每 5 页休 20s、全量结果本地缓存 7 天（data/dblp_cache/），**且只缓存完整拉取（start 越过 @total）的结果，异常截断不落缓存**」

### 调度

- 每日北京时间约 09:00 后触发（arXiv 美东时间 20:00 发布新论文）
- 手动兜底命令：`python -m scripts.run_crawl`（跑一次）；`python -m scripts.run_crawl --backfill --days 180`（历史回填）
- 运行结果写入 `crawl_runs` 表，失败可查可重跑

## 7. 后端开发规范

- **分层**：api（路由）→ services（业务）→ models（ORM）；爬虫模块只被调度器/脚本调用，不直接被路由调用
- **ORM/迁移**：SQLAlchemy 2.x 声明式模型；所有表结构变更走 Alembic 迁移（`alembic revision` → `alembic upgrade head`）
- **Schema 分离**：Pydantic 请求/响应模型放 schemas/，与 ORM 模型对应但互不混用
- **配置**：pydantic-settings 从 .env 读取，代码中不硬编码密钥/路径
- **响应与分页**：列表接口统一返回 `{ "items": [...], "total": n, "page": p, "page_size": s }`；错误沿用 FastAPI 默认 `{ "detail": "..." }`
- **重试**：所有外部 HTTP 调用统一走 rate_limiter + 指数退避（1s/2s/4s/8s，最多 3 次）
- **依赖管理**：pyproject.toml；DeepSeek 调用使用 openai SDK（OpenAI 兼容模式）

## 8. 前端开发规范

- Vue 3 `<script setup>` + Composition API；TypeScript strict 模式
- 状态管理 Pinia（filterStore 管筛选条件、paperStore 管论文数据）；组件内局部状态不全局化
- Axios 统一封装（baseURL=/api、错误提示拦截器）；api/ 目录按资源分文件
- 类型：src/types/ 与后端 Pydantic schema 对齐（改接口时两边同步）
- 组件命名 PascalCase；页面放 views/，可复用组件放 components/
- 图表统一用 ECharts（vue-echarts 封装）
- Vite dev proxy：`/api` → `http://127.0.0.1:8000`（前端不发跨域请求）

## 9. API 接口约定

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /api/papers | 列表：`page, page_size, q(标题/摘要搜索), topic(slug), venue(short_name), year, is_ai4se, sort(newest|venue)` |
| GET | /api/papers/{id} | 详情：含作者、venue、topics、summary_zh、双链接 |
| GET | /api/topics | 主题列表（含计数） |
| GET | /api/venues | A 会列表（含计数） |
| GET | /api/stats/trends | 趋势：`group_by=topic|venue|year, start, end` |

列表响应示例：

```json
{
  "items": [
    {
      "id": 1,
      "title": "An Empirical Study of ...",
      "authors": ["Alice Zhang", "Bob Li"],
      "venue": { "short_name": "ICSE", "year": 2026 },
      "topics": [{ "slug": "code_repair", "name_zh": "代码修复" }],
      "is_ai4se_confirmed": true,
      "arxiv_url": "https://arxiv.org/abs/2501.12345",
      "doi": null
    }
  ],
  "total": 128,
  "page": 1,
  "page_size": 20
}
```

## 10. 测试策略

- **pytest**（后端，重点三个最难模块）：`test_normalize.py` 标题归一化、`test_matcher.py` DBLP 匹配与歧义处理、`test_rate_limiter.py` 限流与退避
- 爬虫解析测试使用固定 fixture 样本（离线 XML/JSON 文件），**不依赖真实网络**
- 前端：M4 后视进度引入 vitest，覆盖筛选逻辑与 store
- 冒烟验收：`pytest` 全绿 + `python -m scripts.run_crawl` 手动跑通一次且重跑无重复数据

## 11. 运行与部署

### 本地开发

```bash
# 后端（端口 8000；依赖经 uv 管理，uvicorn 不全局安装）
cd backend && python -m uv run uvicorn app.main:app --reload --port 8000
# 前端（端口 5173，proxy 到后端）
cd frontend && npm run dev
```

### 环境变量（.env，模板见 .env.example）

| 变量 | 说明 |
|---|---|
| DEEPSEEK_API_KEY | DeepSeek 密钥（分类/摘要必需） |
| DATABASE_URL | 默认 `sqlite:///../data/papers.db` |
| LLM_COST_LIMIT_USD | LLM 月度成本上限（超出即停，见第 14 章） |
| CRAWL_LOOKBACK_DAYS | 每次增量拉取回溯天数（默认 3，容错） |

- `data/`、`.env`、`node_modules/`、`dist/`、`__pycache__/` 不入 git（.gitignore）
- 部署：M5 可选 Docker 化（backend+frontend 双容器）；个人使用本地跑即可

## 12. 常用任务手册

| 任务 | 命令 |
|---|---|
| 手动跑一次完整爬取 | `cd backend && python -m scripts.run_crawl` |
| 历史回填（近 180 天） | `python -m scripts.run_crawl --backfill --days 180` |
| 批量重新分类全部论文 | `python -m scripts.run_classify` |
| 导入 CCF 名单 | `python -m scripts.seed_venues` |
| 导入主题分类法 | `python -m scripts.seed_topics` |
| 新增一个主题 | 向 topics 表插入一行（数据驱动，无需改代码） |
| 迁移数据库 | `alembic upgrade head` |
| 查看爬取审计日志 | 查 crawl_runs 表（DB Browser for SQLite） |

## 13. 里程碑与当前进度

| 里程碑 | 内容 | 验收标准 | 状态 |
|---|---|---|---|
| **M0 脚手架** | git init、目录结构、FastAPI/Vue 空壳、前后端联通、.env.example、决策记录补全（含默认值确认） | 浏览器访问前端能调到后端接口 | ✅ 完成（2026-08-17） |
| **M1 爬虫** | 数据模型+Alembic、arXiv/DBLP 客户端、匹配器、去重 upsert、APScheduler、历史回填脚本 | 单次完整跑通 ①→③→⑥；重跑无重复数据；crawl_runs 计数正确 | ✅ 完成（2026-08-17） |
| **M2 分类** | 主题落库、关键词初筛、DeepSeek 精标（结构化输出/重试/成本开关）、中文摘要、批量回填 | 抽样 50 篇人工检查，分类准确率与主题覆盖可接受 | ⬜ 未开始 |
| **M3 API** | 列表/详情/主题/venue/趋势端点，过滤排序分页 | Swagger 文档完整，curl 可完成全部前端所需查询 | ⬜ 未开始 |
| **M4 前端** | 列表页+筛选侧栏、详情页（双链接/标签/中文摘要）、趋势页（ECharts）、搜索 | 浏览→筛选→详情→趋势主路径无阻断 | ⬜ 未开始 |
| **M5 打磨** | 增量更新持续验证、匹配歧义复核、可选 Docker、备份与 README | 连续 2 周自动增量更新无误；数据可恢复 | ⬜ 未开始 |

**当前进度**：M0、M1 已完成（2026-08-17）。M1 验证记录：4 个 A 会 stream 全量拉取 16967 条（ICSE 7894 / sigsoft 3739 / kbse 3776 / issta 1558，缓存 7 天）；arXiv 近 3 天 4 篇幂等（重跑 new=0/updated=4）；匹配器用真实 DBLP 记录端到端验证通过（dblp_key/venue/year/doi 回填）；pytest 26 通过。M2 分类待启动（需用户提供 DEEPSEEK_API_KEY）。运行方式：后端 `python -m uv run uvicorn app.main:app --reload --port 8000`（backend/ 下，uvicorn 不全局安装）；前端 `npm run dev`（frontend/ 下，proxy 到 8000）。

## 14. 数据与合规

- **arXiv API**：免费无认证；礼貌使用（≥3s/请求、描述性 User-Agent）；只取元数据与摘要，PDF 仅提供链接不下载存储
- **DBLP**：免费；礼貌限流；如未来需深回填大量查询，改用官方 XML dump 本地解析（避免 API 压力）
- **DeepSeek API**：按 token 计费；启用成本上限开关（LLM_COST_LIMIT_USD），超出自动暂停 LLM 精标并记录日志；失败重试有上限，不无限烧钱
- **展示内容**：只展示论文元数据、摘要、公开链接与 LLM 生成摘要，不搬运付费墙内容
- **出处规范**：每篇论文页面同时展示 arXiv 与 DBLP/DOI 原始链接
