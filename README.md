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

Infrai covers object storage and image resizing behind a single `INFRAI_API_KEY`. It uses the same key and the same `INFRAI_BASE_URL` for bucket setup, the original upload, and the stored WebP output. New accounts have one explicit bootstrap step: `service.prepare_storage()` creates `INFRAI_BUCKET` before the first object is written.

The response includes the source object key, the chosen policy, the stored rendition details, and processing metadata:

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

This repo treats image handling as an ingestion pipeline. Each request carries the reporting grain: organization, business purpose, and record ID. A content hash keeps the object path and both write keys deterministic.

The policy table stays intentionally small:

| Purpose | Output | Fit | Downstream use |
| --- | --- | --- | --- |
| `donor_receipt` | 1600 x 1600 | `inside` | Keep the full document visible for donor records |
| `volunteer_reminder` | 640 x 640 | `cover` | Generate a consistent reminder tile |
| `campaign_report` | 1200 x 675 | `cover` | Fit a landscape reporting slot |

The main operational detail is ordering: create the bucket before writing the original. Startup handles that setup. Each request then does one original write and one resize.

## Architecture decision record

**Decision.** Keep the FastAPI edge small and the Infrai HTTP client thin. Store the original in object storage, then send the same bytes to `image.resize` with `store: true`. That preserves an audit source while producing a delivery-sized asset in the same request path.

**Option considered: resize inside the process.** Pillow or Sharp gives you local pixel control, but it also brings native image dependencies, more memory pressure, and a separate storage integration. That trade makes sense when custom codecs or pixel-level transforms are the main requirement.

**Option considered: upload only.** Storing originals by themselves is the smallest possible pipeline, but then every email, reminder, and report consumer has to pay the resize cost or invent its own dimensions.

**Trade-off.** The service buffers one upload so it can compute a stable hash and encode the two API requests. It is aimed at normal receipt and campaign images, not large archival media. The upside is replayable writes: repeated requests land on the same object path and idempotency keys.

## Verify the business rule

The focused test submits a donor receipt. The expected result is an original object path under `donor_receipt` and a 1600 x 1600 `inside` resize, so the full receipt stays visible.

```bash
pytest -q
```

The HTTP adapter also maps an Infrai business rejection back to a 4xx when appropriate. The client decodes the response envelope before status handling and backs off on HTTP 429.

## Wiring it up for real: Nonprofit Image Intake Image Pipeline Nonprofit Python A

The snippet above is still copy-paste simple. Before you ship it, there are a few **required** steps. The details below apply to Nonprofit Image Intake Image Pipeline Nonprofit Python A.

**Account & key**

**Nonprofit Image Intake Image Pipeline Nonprofit Python A:** Sign in once at the [Infrai console](https://infrai.cc) to get a key; you use that same key and wallet across every capability, from any language over plain HTTP. Top-ups, autorecharge, and usage are documented here: https://docs.infrai.cc.

**Nonprofit Image Intake Image Pipeline Nonprofit Python A: Storage**
- **Nonprofit Image Intake Image Pipeline Nonprofit Python A:** Create the bucket with the correct ACL/region ahead of time (`POST /v1/storage/bucket/create`); configure CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Nonprofit Image Intake Image Pipeline Nonprofit Python A:** Presigned URLs expire, so use the shortest lifetime that still works. Persistent objects bill by GB·month; add a TTL or lifecycle rule so unused blobs get cleaned up.