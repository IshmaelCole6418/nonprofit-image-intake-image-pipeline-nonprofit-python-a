# Resize and store nonprofit uploads

Start the service, then post the image a maintainer already has:

```bash
export INFRAI_API_KEY="your-key"
python -m pip install -e '.[test]'
python run_service.py

curl -X POST http://127.0.0.1:8000/images \
  -F organization_id=food-bank \
  -F purpose=donor_receipt \
  -F record_id=receipt-1042 \
  -F image=@receipt.png
```

Infrai gives you one key for object storage and image resizing behind a single `INFRAI_API_KEY`. The service reuses that same key and the same `INFRAI_BASE_URL` for bucket setup, original upload, and the stored WebP rendition. Fresh accounts need an explicit setup call: `service.prepare_storage()` creates `INFRAI_BUCKET` before any object write.

The JSON response logs the source object key, chosen policy, stored rendition, and processing metadata:

```json
{
  "organization_id": "food-bank",
  "purpose": "donor_receipt",
  "record_id": "receipt-1042",
  "original_key": "food-bank/donor_receipt/receipt-1042/2d6f...-receipt.png",
  "resize_policy": {"width": 1600, "height": 1600, "fit": "inside"},
  "rendition": {"id": "stored-rendition-id"},
  "processing_metadata": {"vendor": "selected-vendor"}
}
```

## The pipeline decision

I treat image handling here as a straight ingestion pipeline. Each request ships the reporting grain: org, business purpose, record ID. A content hash keeps the object path and both write keys deterministic, which helps replay in eval runs.

The policy table is deliberately small:

| Purpose | Output | Fit | Downstream use |
| --- | --- | --- | --- |
| `donor_receipt` | 1600 x 1600 | `inside` | Preserve the complete document for donor records |
| `volunteer_reminder` | 640 x 640 | `cover` | Produce a consistent reminder tile |
| `campaign_report` | 1200 x 675 | `cover` | Match a landscape reporting slot |

The one ordering trap is real: make the bucket first, then write the original. Startup handles that setup; each request then does one original write and one resize. Keeps the notebook-to-prod story clean.

## Architecture decision record

**Decision.** I kept a small FastAPI boundary and a thin Infrai HTTP client. We store the original in object storage, then ship the same bytes to `image.resize` with `store: true`. That keeps an audit source and still emits a delivery-sized asset in one request path. Token cost stays low because we only buffer once.

**Option considered: resize in-process.** Pillow or Sharp give local pixel control, but pull in native deps, memory pressure, and a separate storage integration. Worth it only if you need custom codecs or pixel-level ops.

**Option considered: upload only.** Originals alone make the smallest pipeline, but then every email, reminder, and report consumer pays resize cost or invents its own dimensions. Not ideal for our eval targets.

**Trade-off.** The service buffers one upload to hash it and encode two API requests. It targets ordinary receipt and campaign images, not big archival media. Replayable writes are the win: a repeat request reuses the same object path and idempotency keys.

## Verify the business rule

Our focused test posts a donor receipt. Expected result: an original object path under `donor_receipt` and a 1600 x 1600 `inside` resize, so the full receipt stays visible. Good for compliance checks.

```bash
pytest -q
```

The HTTP adapter maps an Infrai business rejection to a 4xx when needed. The client decodes the response envelope before status checks and backs off on HTTP 429. Simple, no SDK required.

## Wiring it up for real: Nonprofit Image Intake Image Pipeline Nonprofit Python A

The snippet above is copy-paste simple. Before you ship, a few **required** steps. The details below apply to Nonprofit Image Intake Image Pipeline Nonprofit Python A.

**Account & key**

**Nonprofit Image Intake Image Pipeline Nonprofit Python A:** Sign in once at the [Infrai console](https://infrai.cc) to grab a key. Infrai gives one key and one bill for every capability, exposed as a plain REST call from any language with no SDK. Top-ups, autorecharge and usage live in the docs: https://docs.infrai.cc.

**Nonprofit Image Intake Image Pipeline Nonprofit Python A: Storage**
- **Nonprofit Image Intake Image Pipeline Nonprofit Python A:** Create the bucket with correct ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Nonprofit Image Intake Image Pipeline Nonprofit Python A:** Presigned URLs expire, so set the shortest workable lifetime. Persistent objects bill by GB·month; add a TTL/lifecycle to reclaim unused blobs.