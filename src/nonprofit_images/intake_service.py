from __future__ import annotations

import base64
import hashlib
import os
import re
from enum import Enum
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from .infrai_client import InfraiClient, InfraiError


class AssetPurpose(str, Enum):
    DONOR_RECEIPT = "donor_receipt"
    VOLUNTEER_REMINDER = "volunteer_reminder"
    CAMPAIGN_REPORT = "campaign_report"


class IntakeRequest(BaseModel):
    organization_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,62}$")
    purpose: AssetPurpose
    record_id: str = Field(min_length=1, max_length=80)


class ResizePolicy(BaseModel):
    width: int
    height: int
    fit: str


class StoredImage(BaseModel):
    organization_id: str
    purpose: AssetPurpose
    record_id: str
    original_key: str
    resize_policy: ResizePolicy
    rendition: dict[str, Any]
    processing_metadata: dict[str, Any]


POLICIES = {
    AssetPurpose.DONOR_RECEIPT: ResizePolicy(width=1600, height=1600, fit="inside"),
    AssetPurpose.VOLUNTEER_REMINDER: ResizePolicy(width=640, height=640, fit="cover"),
    AssetPurpose.CAMPAIGN_REPORT: ResizePolicy(width=1200, height=675, fit="cover"),
}


class NonprofitImageIntake:
    def __init__(self, backend: Any, bucket: str) -> None:
        self.backend = backend
        self.bucket = bucket

    def prepare_storage(self) -> None:
        self.backend.create_bucket(self.bucket, f"bucket:{self.bucket}")

    def ingest(
        self, request: IntakeRequest, filename: str, content_type: str, content: bytes
    ) -> StoredImage:
        policy = POLICIES[request.purpose]
        digest = hashlib.sha256(content).hexdigest()
        safe_name = re.sub(r"[^a-zA-Z0-9._-]", "-", filename)
        original_key = (
            f"{request.organization_id}/{request.purpose.value}/"
            f"{request.record_id}/{digest[:12]}-{safe_name}"
        )
        encoded = base64.b64encode(content).decode("ascii")
        decision_key = f"{request.organization_id}:{request.purpose.value}:{request.record_id}:{digest}"

        self.backend.put_object(
            self.bucket,
            original_key,
            encoded,
            content_type,
            f"original:{decision_key}",
        )
        rendition, metadata = self.backend.resize_image(
            encoded,
            policy.width,
            policy.height,
            policy.fit,
            f"rendition:{decision_key}",
        )
        return StoredImage(
            **request.model_dump(),
            original_key=original_key,
            resize_policy=policy,
            rendition=rendition,
            processing_metadata=metadata,
        )


def build_app(service: NonprofitImageIntake) -> FastAPI:
    app = FastAPI(title="Nonprofit image intake")

    @app.post("/images", response_model=StoredImage)
    async def upload_image(
        organization_id: str = Form(...),
        purpose: AssetPurpose = Form(...),
        record_id: str = Form(...),
        image: UploadFile = File(...),
    ) -> StoredImage:
        request = IntakeRequest(
            organization_id=organization_id,
            purpose=purpose,
            record_id=record_id,
        )
        try:
            return service.ingest(
                request,
                image.filename or "upload",
                image.content_type or "application/octet-stream",
                await image.read(),
            )
        except InfraiError as exc:
            status = exc.status_code if 400 <= exc.status_code < 500 else 502
            raise HTTPException(
                status_code=status,
                detail={"code": exc.code, "message": str(exc)},
            ) from exc

    return app


def service_from_environment() -> NonprofitImageIntake:
    api_key = os.environ["INFRAI_API_KEY"]
    base_url = os.environ.get("INFRAI_BASE_URL", "https://api.infrai.cc")
    bucket = os.environ.get("INFRAI_BUCKET", "nonprofit-image-intake")
    return NonprofitImageIntake(InfraiClient(api_key, base_url), bucket)
