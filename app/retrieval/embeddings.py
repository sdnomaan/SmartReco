from __future__ import annotations

from dataclasses import dataclass

from openai import OpenAI

from app.config import get_settings


@dataclass
class MeshEmbeddingClient:
    model: str | None = None

    def _client(self) -> OpenAI:
        settings = get_settings()
        api_key = settings.mesh_api_key_value.strip()
        if not api_key:
            raise RuntimeError("MESH_API_KEY is required for embedding generation")
        return OpenAI(base_url="https://api.meshapi.ai/v1", api_key=api_key)

    def embed_text(self, text: str) -> list[float]:
        settings = get_settings()
        response = self._client().embeddings.create(model=self.model or settings.mesh_model, input=text)
        return list(response.data[0].embedding)
