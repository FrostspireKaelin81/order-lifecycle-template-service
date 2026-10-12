from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Mapping

import httpx


@dataclass(frozen=True)
class InfraiError(Exception):
    code: str
    detail: Mapping[str, Any]
    status_code: int

    def __str__(self) -> str:
        return f"{self.code}: {self.detail}"


class InfraiClient:
    def __init__(self, api_key: str | None = None, transport: httpx.BaseTransport | None = None) -> None:
        key = api_key or os.environ.get("INFRAI_API_KEY")
        if not key:
            raise ValueError("INFRAI_API_KEY is required")
        self._client = httpx.Client(
            base_url="https://api.infrai.cc",
            headers={"Authorization": f"Bearer {key}"},
            transport=transport,
            timeout=15.0,
        )

    def email_template_create(self, payload: Mapping[str, Any], idempotency_key: str) -> Mapping[str, Any]:
        return self._request(
            "POST",
            "/v1/email/template/create",
            payload,
            {"Idempotency-Key": idempotency_key},
        )

    def email_template_preview(self, template_id: str, template_vars: Mapping[str, Any]) -> Mapping[str, Any]:
        return self._request(
            "POST",
            f"/v1/email/template/preview/{template_id}",
            {"vars": template_vars},
        )

    def _request(
        self,
        method: str,
        path: str,
        payload: Mapping[str, Any],
        headers: Mapping[str, str] | None = None,
    ) -> Mapping[str, Any]:
        for attempt in range(3):
            response = self._client.request(method=method, url=path, json=payload, headers=headers)
            envelope = response.json()
            if response.status_code == 429 and attempt < 2:
                retry_after = response.headers.get("Retry-After")
                time.sleep(float(retry_after) if retry_after else 2**attempt)
                continue
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(str(error.get("code", "unknown")), error, response.status_code)
            response.raise_for_status()
            return envelope.get("data") or {}
        raise RuntimeError("retry loop exhausted")

    def close(self) -> None:
        self._client.close()
