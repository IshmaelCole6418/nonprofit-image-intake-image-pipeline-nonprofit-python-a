from typing import Any

from nonprofit_images.intake_service import (
    AssetPurpose,
    IntakeRequest,
    NonprofitImageIntake,
)


class RecordingBackend:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def create_bucket(self, name: str, idempotency_key: str) -> dict[str, Any]:
        self.calls.append(("create_bucket", {"name": name, "idempotency_key": idempotency_key}))
        return {"name": name}

    def put_object(self, bucket: str, key: str, data_base64: str, content_type: str, idempotency_key: str) -> dict[str, Any]:
        self.calls.append(("put_object", {"bucket": bucket, "key": key, "content_type": content_type, "idempotency_key": idempotency_key}))
        return {"key": key}

    def resize_image(self, image_base64: str, width: int, height: int, fit: str, idempotency_key: str) -> tuple[dict[str, Any], dict[str, Any]]:
        self.calls.append(("resize_image", {"width": width, "height": height, "fit": fit, "idempotency_key": idempotency_key}))
        return {"id": "stored-rendition"}, {"vendor": "selected-vendor"}


def test_receipt_upload_keeps_readable_document_ratio_and_stores_original() -> None:
    backend = RecordingBackend()
    intake = NonprofitImageIntake(backend, "nonprofit-assets")
    request = IntakeRequest(
        organization_id="food-bank",
        purpose=AssetPurpose.DONOR_RECEIPT,
        record_id="receipt-1042",
    )

    result = intake.ingest(request, "donation scan.png", "image/png", b"png-bytes")

    assert result.resize_policy.model_dump() == {
        "width": 1600,
        "height": 1600,
        "fit": "inside",
    }
    assert result.original_key.startswith("food-bank/donor_receipt/receipt-1042/")
    assert [call[0] for call in backend.calls] == ["put_object", "resize_image"]
    assert backend.calls[1][1]["fit"] == "inside"
    assert result.rendition == {"id": "stored-rendition"}

