from typing import Any, Mapping

import httpx
import pytest

from order_mail.infrai_client import InfraiClient
from order_mail.lifecycle_templates import OrderStage, TemplateRequest, prepare_lifecycle_template


class RecordingAPI:
    def __init__(self) -> None:
        self.created: tuple[Mapping[str, Any], str] | None = None
        self.previewed: tuple[str, Mapping[str, Any]] | None = None

    def email_template_create(self, payload: Mapping[str, Any], idempotency_key: str) -> Mapping[str, Any]:
        self.created = (payload, idempotency_key)
        return {"id": "tpl_1042"}

    def email_template_preview(self, template_id: str, template_vars: Mapping[str, Any]) -> Mapping[str, Any]:
        self.previewed = (template_id, template_vars)
        return {"subject": "Order A-1042 is on the way", "html": "<p>Tracking: TRACK-9.</p>"}


def test_preview_uses_contract_vars_field() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/email/template/preview/tpl_1042"
        assert request.read() == b'{"vars":{"order_id":"A-1042"}}'
        return httpx.Response(200, json={"ok": True, "data": {"subject": "Preview"}})

    client = InfraiClient(api_key="test", transport=httpx.MockTransport(respond))
    try:
        assert client.email_template_preview("tpl_1042", {"order_id": "A-1042"}) == {"subject": "Preview"}
    finally:
        client.close()


def test_fulfillment_creation_hands_order_data_to_preview() -> None:
    api = RecordingAPI()
    result = prepare_lifecycle_template(
        TemplateRequest(
            order_id="A-1042",
            stage=OrderStage.FULFILLMENT,
            customer_email="buyer@example.com",
            customer_name="Rae",
            total="$48.00",
            tracking_number="TRACK-9",
        ),
        api,
    )

    assert api.created is not None
    assert api.created[0]["name"] == "order-A-1042-fulfillment"
    assert api.created[1] == "template:order-A-1042-fulfillment"
    assert api.previewed == (
        "tpl_1042",
        {
            "order_id": "A-1042",
            "customer_email": "buyer@example.com",
            "customer_name": "Rae",
            "total": "$48.00",
            "tracking_number": "TRACK-9",
            "update_text": "",
        },
    )
    assert result.preview["subject"] == "Order A-1042 is on the way"


def test_fulfillment_requires_tracking_number() -> None:
    api = RecordingAPI()
    with pytest.raises(ValueError, match="tracking_number"):
        prepare_lifecycle_template(
            TemplateRequest(
                order_id="A-1042",
                stage=OrderStage.FULFILLMENT,
                customer_email="buyer@example.com",
                customer_name="Rae",
                total="$48.00",
            ),
            api,
        )
    assert api.created is None
