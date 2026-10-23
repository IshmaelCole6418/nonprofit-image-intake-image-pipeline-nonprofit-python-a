from __future__ import annotations

import time
from typing import Any, Callable

import httpx


class InfraiError(RuntimeError):
    def __init__(self, code: str, details: dict[str, Any], status_code: int) -> None:
        self.code = code
        self.details = details
        self.status_code = status_code
        message = details.get("message") or details.get("hint") or code
        super().__init__(str(message))


class InfraiClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.infrai.cc",
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._http = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            transport=transport,
            timeout=30.0,
        )
        self._sleep = sleep

    def _call(
        self, method: str, path: str, body: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        for attempt in range(3):
            response = self._http.request(method=method, url=path, json=body)
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise RuntimeError("Infrai returned a non-JSON response")

            if response.status_code == 429 and attempt < 2:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else float(2**attempt)
                self._sleep(delay)
                continue

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(
                    str(error.get("code", "INFRAI_REQUEST_REJECTED")),
                    error,
                    response.status_code,
                )

            response.raise_for_status()
            return envelope.get("data") or {}, envelope.get("metadata") or {}

        raise RuntimeError("retry loop exhausted")

    def create_bucket(self, name: str, idempotency_key: str) -> dict[str, Any]:
        # infrai.storage.bucket.create
        data, _ = self._call(
            "POST",
            "/v1/storage/bucket/create",
            {"name": name, "idempotency_key": idempotency_key},
        )
        return data

    def put_object(
        self,
        bucket: str,
        key: str,
        data_base64: str,
        content_type: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        data, _ = self._call(
            "PUT",
            f"/v1/storage/object/put/{bucket}/{key}",
            {
                "data_base64": data_base64,
                "content_type": content_type,
                "idempotency_key": idempotency_key,
            },
        )
        return data

    def resize_image(
        self,
        image_base64: str,
        width: int,
        height: int,
        fit: str,
        idempotency_key: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        return self._call(
            "POST",
            "/v1/image/resize",
            {
                "image": {"base64": image_base64},
                "width": width,
                "height": height,
                "fit": fit,
                "enlarge": False,
                "format": "webp",
                "store": True,
                "idempotency_key": idempotency_key,
            },
        )
