"""DeepSeek LLM 精标（管线阶段⑤，M2）：AI4SE 判定 + 主题标签 + 中文摘要。

设计（DR-019 授权内自主决策）：
- openai SDK（OpenAI 兼容模式，base_url 指向 DeepSeek）；模型 deepseek-chat（最便宜档，DR-019）
- 结构化输出：response_format=json_object + 严格 prompt；解析校验失败重试（最多 2 次）
- 成本控制：每次调用按 usage 精确累计美元成本，跨运行持久化到 data/llm_cost.json，
  累计超 LLM_COST_LIMIT_USD 抛 CostLimitExceeded（调度方捕获后停止精标并记录）
- 并发由调用方控制（run_classify 默认 2）
"""
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from openai import OpenAI

from app.config import settings

logger = logging.getLogger(__name__)

VALID_TOPIC_SLUGS = {
    "code_generation",
    "code_repair",
    "code_translation",
    "code_summarization",
    "defect_detection",
    "testing",
    "analysis",
    "requirements",
    "llm4se_general",
    "other",
}

MAX_RETRIES = 2  # API 失败 / 输出解析失败各最多重试 2 次
ABSTRACT_MAX_CHARS = 2000  # 摘要截断长度，控制输入 token 成本


class CostLimitExceeded(Exception):
    """LLM 成本超限：调用方捕获后停止精标。"""


@dataclass
class LlmResult:
    """精标结果（结构化输出校验后的产物）。"""

    is_ai4se: bool
    topics: list[str]
    summary_zh: str
    confidence: float
    highlights: dict | None = None  # M6 亮点速读 {contribution, limitation}


class CostTracker:
    """跨运行累计 LLM 成本：每次调用后 update(usage)，超限即抛。"""

    def __init__(self, limit_usd: float | None = None) -> None:
        self.limit_usd = limit_usd if limit_usd is not None else settings.llm_cost_limit_usd
        self.total_usd = self._load_total()
        self.session_usd = 0.0
        self.calls = 0
        if self.total_usd >= self.limit_usd:
            raise CostLimitExceeded(
                f"LLM cost limit reached: {self.total_usd:.4f} >= {self.limit_usd} USD (restored)"
            )

    # ---- 价格估算：deepseek-chat 官方定价（2026-08，按百万 token 计） ----
    @property
    def input_price(self) -> float:
        return settings.llm_price_input_usd_per_1m

    @property
    def output_price(self) -> float:
        return settings.llm_price_output_usd_per_1m

    def update(self, usage) -> float:
        """按 usage（openai 返回）累加成本；返回本次调用成本。"""
        prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
        completion_tokens = getattr(usage, "completion_tokens", 0) or 0
        cost = prompt_tokens / 1_000_000 * self.input_price + (
            completion_tokens / 1_000_000 * self.output_price
        )
        self.total_usd += cost
        self.session_usd += cost
        self.calls += 1
        if self.total_usd >= self.limit_usd:
            raise CostLimitExceeded(
                f"LLM cost limit reached: {self.total_usd:.4f} >= {self.limit_usd} USD"
            )
        return cost

    # ---- 持久化 ----
    @staticmethod
    def _state_file() -> Path:
        db_path = Path(settings.database_url.removeprefix("sqlite:///"))
        return db_path.parent / "llm_cost.json"

    def _load_total(self) -> float:
        path = self._state_file()
        if not path.exists():
            return 0.0
        try:
            return float(json.loads(path.read_text(encoding="utf-8")).get("total_usd", 0.0))
        except (ValueError, KeyError, TypeError, OSError):
            logger.warning("llm_cost.json corrupt, reset to 0")
            return 0.0

    def save(self) -> None:
        try:
            path = self._state_file()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(
                    {
                        "total_usd": round(self.total_usd, 6),
                        "updated_at": datetime.utcnow().isoformat(),
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
        except OSError:
            logger.exception("llm_cost.json write failed (non-fatal)")


_CLASSIFY_SYSTEM = """You are an expert research classifier for AI4SE (AI for Software Engineering).
Classify the given paper. Respond with STRICT JSON only, no markdown, no extra text:
{"is_ai4se": bool, "topics": [slug...], "summary_zh": "中文摘要（≤120字）", "confidence": 0.0-1.0, "highlights": {"contribution": "主要贡献（≤60字）", "limitation": "主要局限（≤40字）"}}

Topic slugs (only when is_ai4se=true, pick 1-3):
- code_generation 代码生成
- code_repair 代码修复
- code_translation 代码翻译
- code_summarization 代码摘要
- defect_detection 缺陷检测与定位
- testing 自动化测试
- analysis 软件分析
- requirements 需求工程
- llm4se_general LLM4SE通用（大模型应用于软件工程的综合/框架/调研类）
- other 其他（AI4SE 但无合适主题）

Rules:
- is_ai4se=true only when AI/ML (especially LLM) is APPLIED TO software engineering tasks
  (code generation/repair/testing/analysis...). Pure ML research without SE application → false.
- summary_zh: concise Chinese summary, ≤120 characters, always generate even when is_ai4se=false.
- highlights (only when is_ai4se=true): 一句话核心贡献 + 一句话局限，中文，具体不空泛。
- confidence: your certainty about the whole result.
"""


_DEEP_SUMMARY_SYSTEM = """You are an expert paper reader. Read the given paper and produce a
structured Chinese summary. Respond with STRICT JSON only, no markdown:
{"background": "研究背景（≤80字）", "problem": "要解决什么问题（≤80字）", "method": "方法/思路（≤100字）", "results": "主要实验结果（≤80字）", "conclusion": "结论/贡献（≤80字）"}
Rules: be specific and factual, no empty strings, no generic filler.
"""


def parse_deep_summary(text: str) -> dict | None:
    """解析深度摘要结构化输出；缺任一字段返回 None（调用方重试）。"""
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    result = {}
    for key in ("background", "problem", "method", "results", "conclusion"):
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            return None
        result[key] = value.strip()
    return result


def generate_deep_summary(
    title: str, abstract: str | None, year: int | None = None
) -> dict | None:
    """按需生成深度摘要（M7，DR-024：点击才调 LLM，生成后缓存复用）。

    与 classify 同模式：结构化 JSON + 重试（最多 2 次）+ CostTracker 成本累计。
    """
    classifier = DeepSeekClassifier()
    user_content = (
        f"Title: {title}\nYear: {year or 'unknown'}\n"
        f"Abstract: {(abstract or '')[:ABSTRACT_MAX_CHARS]}"
    )
    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = classifier.client.chat.completions.create(
                model=classifier.model,
                messages=[
                    {"role": "system", "content": _DEEP_SUMMARY_SYSTEM},
                    {"role": "user", "content": user_content},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
                max_tokens=600,
            )
            result = parse_deep_summary(resp.choices[0].message.content or "")
            classifier.cost.update(resp.usage)
            if result is not None:
                return result
            last_err = ValueError("deep summary output failed schema validation")
            logger.warning("deep summary parse failed (attempt %d), retry", attempt + 1)
        except CostLimitExceeded:
            raise
        except Exception as exc:
            last_err = exc
            logger.warning(
                "deep summary api error (attempt %d): %s, backoff %ds",
                attempt + 1,
                type(exc).__name__,
                (attempt + 1) * 2,
            )
            time.sleep((attempt + 1) * 2)
    logger.error("deep summary failed after retries: %s", last_err)
    return None


def parse_llm_result(text: str) -> LlmResult | None:
    """解析并校验 LLM 结构化输出；不合法返回 None（调用方重试）。"""
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    is_ai4se = data.get("is_ai4se")
    if not isinstance(is_ai4se, bool):
        return None
    topics = data.get("topics")
    summary_zh = data.get("summary_zh")
    try:
        confidence = float(data.get("confidence", 0.0))
    except (TypeError, ValueError):
        return None
    if not 0.0 <= confidence <= 1.0:
        return None
    if is_ai4se:
        if not isinstance(topics, list) or not topics:
            return None
        if not isinstance(summary_zh, str) or not summary_zh.strip():
            return None
    else:
        topics = []
        summary_zh = summary_zh if isinstance(summary_zh, str) else ""
    valid_topics = [t for t in topics if isinstance(t, str) and t in VALID_TOPIC_SLUGS]
    if is_ai4se and not valid_topics:
        return None
    # M6 亮点速读：容错解析（非 dict 或缺字段 → None，不因亮点缺失重试整个分类）
    highlights: dict | None = None
    raw_highlights = data.get("highlights")
    if isinstance(raw_highlights, dict):
        hl = {
            k: (v.strip() if isinstance(v, str) else "")
            for k, v in raw_highlights.items()
            if k in ("contribution", "limitation")
        }
        highlights = hl if (hl.get("contribution") or hl.get("limitation")) else None
    return LlmResult(
        is_ai4se=is_ai4se,
        topics=valid_topics[:3],
        summary_zh=(summary_zh or "").strip(),
        confidence=round(confidence, 3),
        highlights=highlights,
    )


class DeepSeekClassifier:
    """DeepSeek 精标器：单篇调用 + 重试 + 成本累计。"""

    def __init__(self, cost: CostTracker | None = None, model: str | None = None) -> None:
        self.cost = cost or CostTracker()
        self.model = model or settings.deepseek_model
        self.client = OpenAI(
            api_key=settings.deepseek_api_key or "missing",
            base_url=settings.deepseek_base_url,
            timeout=120.0,
        )
        if not settings.deepseek_api_key:
            raise RuntimeError("DEEPSEEK_API_KEY 未配置（backend/.env）")

    def classify(
        self, title: str, abstract: str | None, year: int | None = None
    ) -> LlmResult | None:
        """精标单篇；失败重试最多 MAX_RETRIES 次，仍失败返回 None（调用方记录跳过）。"""
        user_content = f"Title: {title}\nYear: {year or 'unknown'}\nAbstract: {(abstract or '')[:ABSTRACT_MAX_CHARS]}"
        last_err: Exception | None = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": _CLASSIFY_SYSTEM},
                        {"role": "user", "content": user_content},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1,
                    max_tokens=700,
                )
                result = parse_llm_result(resp.choices[0].message.content or "")
                self.cost.update(resp.usage)
                if result is not None:
                    return result
                last_err = ValueError("LLM output failed schema validation")
                logger.warning("classify parse failed (attempt %d), retry", attempt + 1)
            except CostLimitExceeded:
                raise  # 成本超限立即停止，不重试
            except Exception as exc:  # 网络/API 错误
                last_err = exc
                logger.warning(
                    "classify api error (attempt %d): %s, backoff %ds",
                    attempt + 1,
                    type(exc).__name__,
                    (attempt + 1) * 2,
                )
                time.sleep((attempt + 1) * 2)
        logger.error("classify failed after retries: %s", last_err)
        return None
