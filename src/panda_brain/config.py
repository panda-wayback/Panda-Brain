from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.ollama import OllamaProvider
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="PANDA_")

    ollama_base_url: str = "http://localhost:11434/v1"
    default_model: str = "qwen3:latest"
    # LanceDB 数据目录（与 bilibili 登记表 .panda_brain/ 可同迁到一目录时再统一）
    lancedb_path: str = ".lancedb"
    # 向量化模型（sentence-transformers 模型名）
    lancedb_embedding_model: str = "BAAI/bge-small-en-v1.5"
    # B 站抓取已拉取记录（避免重复抓取）
    bilibili_fetched_registry_path: str = ".panda_brain/bilibili_fetched.json"


settings = Settings()


def get_model(model_name: str | None = None) -> OpenAIChatModel:
    """创建 Ollama 模型实例。"""
    return OpenAIChatModel(
        model_name=model_name or settings.default_model,
        provider=OllamaProvider(base_url=settings.ollama_base_url),
    )
