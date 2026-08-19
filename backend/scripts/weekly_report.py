"""周报生成（M6）：统计近 7 天新增 AI4SE 论文并输出 Markdown 报告。

用法（cd backend）：
    python -m scripts.weekly_report            # 生成近 7 天报告
    python -m scripts.weekly_report --days 14  # 自定义窗口
输出：data/reports/YYYY-Www.md（ISO 周，周一为一周开始）

由 APScheduler 每周五 09:30（北京时间）自动触发（见 app/crawler/scheduler.py）。
统计与渲染分离（collect_stats / render_report），便于 pytest 离线测试。
"""
import argparse
import logging
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.db import SessionLocal
from app.models import Paper, PaperTopic, Topic

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_DAYS = 7
REPORT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "reports"
HIGHLIGHT_TOP_N = 10


def _paper_links(p: Paper) -> str:
    """论文双链接（arXiv + DBLP），空格分隔。"""
    links = []
    if p.arxiv_url:
        links.append(p.arxiv_url)
    if p.dblp_key:
        links.append(f"https://dblp.org/rec/{p.dblp_key}.html")
    return " ".join(links)


def collect_stats(db: Session, days: int = DEFAULT_DAYS) -> dict:
    """统计近 N 天（created_at 窗口）新增论文、AI4SE 占比、主题分布、A 会匹配与亮点论文。"""
    cutoff = datetime.utcnow() - timedelta(days=days)

    new_papers = db.query(Paper).filter(Paper.created_at >= cutoff)
    total = new_papers.count()
    ai4se = new_papers.filter(Paper.is_ai4se_confirmed.is_(True)).count()

    # 本周新增 AI4SE 论文的 llm 主题标签分布
    topic_counts = (
        db.query(Topic.slug, Topic.name_zh, func.count(PaperTopic.paper_id))
        .join(PaperTopic, PaperTopic.topic_id == Topic.id)
        .join(Paper, Paper.id == PaperTopic.paper_id)
        .filter(
            Paper.is_ai4se_confirmed.is_(True),
            Paper.created_at >= cutoff,
            PaperTopic.method == "llm",
        )
        .group_by(Topic.id)
        .order_by(func.count(PaperTopic.paper_id).desc())
        .all()
    )

    # 近 N 天 A 会新匹配（matched 状态在此窗口内更新过）
    matched = (
        db.query(Paper)
        .filter(Paper.match_status == "matched", Paper.updated_at >= cutoff)
        .options(selectinload(Paper.venue))
        .order_by(Paper.updated_at.desc())
        .all()
    )

    # 本周新增 + 有亮点速读的论文，按发布时间倒序取 Top N
    highlights = (
        db.query(Paper)
        .filter(
            Paper.is_ai4se_confirmed.is_(True),
            Paper.created_at >= cutoff,
            Paper.highlights.isnot(None),
        )
        .options(selectinload(Paper.venue))
        .order_by(Paper.published_at.desc().nullslast())
        .limit(HIGHLIGHT_TOP_N)
        .all()
    )

    return {
        "days": days,
        "total": total,
        "ai4se": ai4se,
        "topic_counts": [(slug, name_zh, count) for slug, name_zh, count in topic_counts],
        "matched": matched,
        "highlights": highlights,
    }


def render_report(stats: dict, period_label: str) -> str:
    """把统计结果渲染为 Markdown 字符串（纯函数，可单测）。"""
    days = stats["days"]
    lines = [
        f"# AI4SE PaperTracker 周报（{period_label}）",
        "",
        f"> 统计窗口：近 {days} 天新增入库论文",
        "",
        "## 本周概览",
        "",
        f"- 新增入库论文：**{stats['total']}** 篇",
        f"- 其中 AI4SE：**{stats['ai4se']}** 篇"
        + (f"（占比 {stats['ai4se'] / stats['total'] * 100:.0f}%）" if stats["total"] else ""),
        f"- 新增 A 会匹配：**{len(stats['matched'])}** 篇",
        "",
    ]

    # 主题分布
    lines += ["## 主题分布（本周新增 AI4SE）", "", "| 主题 | 篇数 |", "|---|---|"]
    if stats["topic_counts"]:
        for slug, name_zh, count in stats["topic_counts"]:
            lines.append(f"| {name_zh}（{slug}） | {count} |")
    else:
        lines.append("| （本周无新增 AI4SE 论文） | 0 |")
    lines.append("")

    # A 会新匹配
    lines += ["## A 会新匹配", ""]
    if stats["matched"]:
        for p in stats["matched"]:
            venue_name = p.venue.short_name if p.venue else "?"
            link = p.arxiv_url or (
                f"https://dblp.org/rec/{p.dblp_key}.html" if p.dblp_key else None
            )
            lines.append(f"- [{p.title}]({link or '#'}) — {venue_name} {p.year or ''}")
    else:
        lines.append("- 本周无新匹配")
    lines.append("")

    # 亮点论文
    lines += [f"## 亮点论文 Top {HIGHLIGHT_TOP_N}", ""]
    if stats["highlights"]:
        for i, p in enumerate(stats["highlights"], 1):
            venue_name = f"{p.venue.short_name} {p.year}" if p.venue else f"{p.year or ''}".strip()
            hl = p.highlights or {}
            lines += [
                f"### {i}. {p.title}（{venue_name}）",
                "",
                f"- 贡献：{hl.get('contribution', '—')}",
                f"- 局限：{hl.get('limitation', '—')}",
                f"- 链接：{_paper_links(p) or '—'}",
                "",
            ]
    else:
        lines.append("- 本周无亮点速读论文（可运行 `python -m scripts.run_classify --backfill-highlights` 回填）")
    return "\n".join(lines)


def generate_weekly_report(db: Session, days: int = DEFAULT_DAYS) -> Path:
    """统计并写盘，返回报告文件路径。"""
    now = datetime.utcnow()
    period_label = f"{(now - timedelta(days=days)).strftime('%m-%d')} ~ {now.strftime('%m-%d')}"
    stats = collect_stats(db, days)
    content = render_report(stats, period_label)

    iso_year, iso_week, _ = now.isocalendar()
    out = REPORT_DIR / f"{iso_year}-W{iso_week:02d}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")
    # 路径可能含 U+2011 连字符，Windows GBK 控制台无法编码，显示时替换
    logger.info("weekly report written: %s", str(out).replace("‑", "-"))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS, help="统计窗口天数")
    args = parser.parse_args(argv)
    db = SessionLocal()
    try:
        path = generate_weekly_report(db, args.days)
        print(f"周报已生成：{str(path).replace(chr(0x2011), '-')}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
