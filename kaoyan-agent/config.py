"""配置：从 .env 读取，启动时校验关键项。"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://open.bigmodel.cn/api/paas/v4"
    LLM_MODEL_ROUTER: str = "glm-4-flash"
    LLM_MODEL_MAIN: str = "glm-4-plus"

    AGENT_INTERNAL_KEY: str = "kaoyan-agent-internal-key-2026"

    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 3306
    DB_NAME: str = "kaoyan"
    DB_USER: str = "root"
    DB_PASSWORD: str = "clue_Y20060406"

    LOG_LEVEL: str = "INFO"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if len(self.AGENT_INTERNAL_KEY) < 16 or not self.AGENT_INTERNAL_KEY.isascii():
            raise RuntimeError("AGENT_INTERNAL_KEY 至少 16 位 ASCII 字符")


settings = Settings()
