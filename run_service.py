from nonprofit_images.intake_service import build_app, service_from_environment


service = service_from_environment()
service.prepare_storage()
app = build_app(service)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)

