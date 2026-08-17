# AI4SE PaperTracker

自动跟踪 **AI4SE（AI for Software Engineering）** 论文的网站：定时从 arXiv 拉取最新论文，经 DBLP 判定其在 CCF-A 软件工程会议（ICSE / FSE / ASE / ISSTA）的发表情况，用「关键词 + DeepSeek LLM」混合方案识别 AI4SE 论文、打主题标签（代码翻译、代码修复、代码生成、缺陷检测等）并生成中文摘要，以 Web 页面展示。

## 技术栈

- **前端**：Vue 3 + TypeScript + Vite + Element Plus + ECharts（Pinia、Vue Router、Axios）
- **后端**：Python + FastAPI + SQLAlchemy 2.x + SQLite + APScheduler（uv 管理依赖）
- **外部服务**：arXiv API、DBLP API、DeepSeek API

## 快速开始

```bash
# 1. 后端（端口 8000，首次先复制环境变量）
cp .env.example backend/.env
cd backend && python -m uv run uvicorn app.main:app --reload --port 8000

# 2. 前端（端口 5173，/api 自动代理到后端）
cd frontend && npm install && npm run dev
```

浏览器访问 http://localhost:5173 ，右上角显示「后端已联通」即搭建成功。API 文档：http://localhost:8000/docs

## 文档

- 开发规范与决策记录：[CLAUDE.md](CLAUDE.md)（唯一事实来源，所有方案选择由用户拍板并记录在案）
- 当前进度：M0 脚手架 ✅ → M1 爬虫 → M2 分类 → M3 API → M4 前端 → M5 打磨

## 仓库

私有仓库，推送通道为 SSH over 443（`git@ssh.github.com:…`）。
