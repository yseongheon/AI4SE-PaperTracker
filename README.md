# AI4SE PaperTracker

自动跟踪「AI 赋能软件工程（AI4SE）」论文的网站。每日从 arXiv 拉取最新论文，判定其在 CCF-A 软件工程会议（ICSE / FSE / ASE / ISSTA）的发表情况，识别 AI4SE 论文并按研究主题分类、生成中文摘要，最终以 Web 页面展示与可视化。

> 开发规范、架构设计与决策记录见 [CLAUDE.md](CLAUDE.md)（项目唯一事实来源）。
> **课题组使用说明（全部功能手册）见 [课题组使用手册.md](课题组使用手册.md)。**

## 核心功能

- **每日自动爬取**：定时从 arXiv 拉取 `cs.SE`（软件工程）分类最新论文，历史回填脚本兜底
- **A 会判定**：通过 DBLP 收录记录判定论文是否发表于 CCF-A 软件工程会议，双链接展示（arXiv 预印本 + DBLP/DOI 正式版）
- **AI4SE 识别与分类**：关键词初筛 + DeepSeek LLM 精标，判定是否属于 AI4SE，并打主题标签（代码生成、代码修复、缺陷检测、自动化测试、需求工程等 10 类）
- **中文摘要**：LLM 为每篇 AI4SE 论文生成中文摘要
- **Web 展示**：论文列表（搜索 / 主题 / 会议 / 年份筛选、分页）、论文详情、主题与会议趋势图表（按天/周/月聚合）

## 技术栈

|层|技术|
|---|---|
|前端|Vue 3 + TypeScript + Vite + Element Plus + ECharts（Pinia / Vue Router / Axios）|
|后端|Python + FastAPI + SQLAlchemy 2.x + SQLite + APScheduler（Alembic 迁移）|
|外部服务|arXiv API（爬取）、DBLP API（A 会判定）、DeepSeek API（分类与中文摘要）|

## 快速开始

### 环境要求

- Python ≥ 3.11（依赖经 [uv](https://docs.astral.sh/uv/) 管理）
- Node.js ≥ 20

### 1. 启动后端（端口 8000）

```bash
cd backend
cp ../.env.example ../.env   # 首次：填入 DEEPSEEK_API_KEY
python -m uv run uvicorn app.main:app --port 8000
```

- API 文档（Swagger）：<http://127.0.0.1:8000/docs>
- 数据库文件位于 `data/papers.db`（SQLite，自动按 Alembic 迁移建表）

### 2. 启动前端（端口 5173）

```bash
cd frontend
npm install
npm run dev
```

打开 <http://localhost:5173>（开发模式经 Vite proxy 调用后端，无跨域配置）。

### 3. 初始化与首次回填（仅服务器部署者，使用者无需任何操作）

> 数据由服务器统一维护（每日 09:30 自动爬取更新）。**普通使用者打开网页即可浏览全部数据，不需要、也不应该执行以下任何命令。**

```bash
cd backend
python -m uv run python -m scripts.seed_venues   # 导入 CCF-A 会议名单
python -m uv run python -m scripts.seed_topics   # 导入主题分类法
python -m uv run python -m scripts.run_crawl --backfill --days 180   # 历史回填（受 DBLP 限流约束）
python -m uv run python -m scripts.run_classify  # 关键词初筛 + LLM 精标 + 中文摘要
```

## 课题组多人使用（生产模式）

```bash
cd frontend && npm run build   # 构建前端（首次或前端改动后执行）
cd backend && python -m uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- 双击根目录 `start.bat` 也会自动走生产模式（检测到 `frontend/dist` 后单端口启动）
- **组内成员**浏览器访问 `http://<你的局域网 IP>:8000`，自行注册账号使用（账号数据互不干扰）
- 首次使用建议在 `backend/.env` 配置 `AUTH_SECRET=<随机长字符串>`（防 token 伪造）
- 成员连不上时，Windows 防火墙放行 8000 端口（bat 启动时有提示命令）

## 常用命令

|任务|命令（backend/ 下）|
|---|---|
|手动跑一次完整爬取|`python -m scripts.run_crawl`|
|历史回填（近 180 天）|`python -m scripts.run_crawl --backfill --days 180`|
|批量重新分类|`python -m scripts.run_classify`|
|复核 DBLP 匹配歧义|`python -m scripts.review_pending list`|
|数据库迁移|`python -m uv run alembic upgrade head`|

> 上表命令**仅服务器管理员使用**（数据维护与异常修复）。普通使用者打开网页即可，无需任何命令行操作。

## 数据与合规

- **arXiv API**：免费无认证，礼貌限流（≥3s/请求）；仅展示元数据与摘要，不下载存储 PDF
- **DBLP**：免费；请求间隔 ≥2s，限流敏感，客户端带本地缓存
- **DeepSeek API**：按 token 计费，启用月度成本上限开关（`LLM_COST_LIMIT_USD`），超出自动暂停
- 仅展示论文元数据、公开链接与 LLM 生成摘要，不搬运付费墙内容

## 项目结构

```text
AI4SE-PaperTracker/
├── backend/
│   ├── app/                # FastAPI 应用（api 路由 / services 业务 / models ORM / crawler 爬虫）
│   ├── scripts/            # 命令行脚本（爬取/分类/回填/复核）
│   ├── alembic/            # 数据库迁移
│   └── tests/              # pytest（71 个测试，离线可跑）
├── frontend/
│   └── src/                # Vue 3 前端（views / components / stores / api / types）
├── data/                   # SQLite 数据库与爬取缓存（不入 git）
├── CLAUDE.md               # 开发文档与决策记录
└── .env.example            # 环境变量模板
```
