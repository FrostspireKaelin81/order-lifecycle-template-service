from fastapi import FastAPI, HTTPException

from .infrai_client import InfraiClient, InfraiError
from .lifecycle_templates import PreparedTemplate, TemplateRequest, prepare_lifecycle_template

app = FastAPI(title="Order lifecycle template service")


@app.post("/templates/prepare", response_model=PreparedTemplate)
def prepare_template(request: TemplateRequest) -> PreparedTemplate:
    client = InfraiClient()
    try:
        return prepare_lifecycle_template(request, client)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except InfraiError as exc:
        status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(status_code=status, detail={"code": exc.code, "detail": exc.detail}) from exc
    finally:
        client.close()
