from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.ollama import OllamaProvider
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="PANDA_")

    ollama_base_url: str = "http://localhost:11434/v1"
    default_model: str = "qwen3:latest"


settings = Settings()


def get_model(model_name: str | None = None) -> OpenAIChatModel:
    """创建 Ollama 模型实例。"""
    return OpenAIChatModel(
        model_name=model_name or settings.default_model,
        provider=OllamaProvider(base_url=settings.ollama_base_url),
    )
