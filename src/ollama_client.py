from __future__ import annotations

import json
import os
from typing import Any, Callable, Dict, Optional
from urllib.error import HTTPError
from urllib.request import Request, urlopen


DEFAULT_OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
DEFAULT_OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:4b")


class OllamaClient:
    def __init__(
        self,
        *,
        base_url: str = DEFAULT_OLLAMA_BASE_URL,
        model: str = DEFAULT_OLLAMA_MODEL,
        timeout_seconds: float = 15.0,
        transport: Optional[Callable[[str, Dict[str, Any], float], Dict[str, Any]]] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    def interpret(self, prompt: str) -> Dict[str, Any]:
        endpoint = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        }
        if self.transport is not None:
            raw = self.transport(endpoint, payload, self.timeout_seconds)
        else:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            request = Request(
                endpoint,
                data=body,
                headers={"Content-Type": "application/json; charset=utf-8"},
                method="POST",
            )
            try:
                with urlopen(request, timeout=self.timeout_seconds) as response:  # nosec B310
                    raw = json.loads(response.read().decode("utf-8"))
            except HTTPError as exc:
                detail = self._http_error_detail(exc)
                raise RuntimeError(f"ollama_http_error status={exc.code} detail={detail}") from exc

        if isinstance(raw, dict) and "response" in raw:
            response_payload = raw.get("response")
            if isinstance(response_payload, str):
                return json.loads(response_payload)
            if isinstance(response_payload, dict):
                return response_payload
        if isinstance(raw, dict):
            return raw
        raise ValueError("unexpected ollama response payload")

    @staticmethod
    def _http_error_detail(exc: HTTPError) -> str:
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            body = ""
        if not body:
            return str(exc)
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            return body
        if isinstance(payload, dict):
            return str(payload.get("error") or payload)
        return str(payload)
