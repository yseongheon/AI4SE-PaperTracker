"""应用配置：pydantic-settings 从 .env 读取，代码不硬编码密钥。"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # 数据
    database_url: str = "sqlite:///../data/papers.db"

    # DeepSeek LLM（M2 起用于 AI4SE 分类与中文摘要）
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    llm_cost_limit_usd: float = 5.0
    # 价格估算（deepseek-chat 官方定价，USD/百万 token；仅用于成本开关，非计费）
    llm_price_input_usd_per_1m: float = 0.27
    llm_price_output_usd_per_1m: float = 1.10

    # 爬取调度
    crawl_lookback_days: int = 3
    crawl_schedule_hour: int = 9
    crawl_schedule_minute: int = 30


settings = Settings()
