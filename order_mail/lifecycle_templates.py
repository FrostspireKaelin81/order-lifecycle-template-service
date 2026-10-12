from __future__ import annotations

from enum import StrEnum
from typing import Any, Mapping

from pydantic import BaseModel, Field


class OrderStage(StrEnum):
    CHECKOUT = "checkout"
    FULFILLMENT = "fulfillment"
    RECEIPT = "receipt"
    CUSTOMER_UPDATE = "customer_update"


class TemplateRequest(BaseModel):
    order_id: str = Field(min_length=1, max_length=80)
    stage: OrderStage
    customer_email: str = Field(min_length=3, max_length=320)
    customer_name: str = Field(min_length=1, max_length=120)
    total: str = Field(min_length=1, max_length=40)
    tracking_number: str | None = Field(default=None, max_length=120)
    update_text: str | None = Field(default=None, max_length=500)


class PreparedTemplate(BaseModel):
    template_id: str
    template_name: str
    preview: Mapping[str, Any]


SUBJECTS = {
    OrderStage.CHECKOUT: "Order {{order_id}} is confirmed",
    OrderStage.FULFILLMENT: "Order {{order_id}} is on the way",
    OrderStage.RECEIPT: "Receipt for order {{order_id}}",
    OrderStage.CUSTOMER_UPDATE: "Update for order {{order_id}}",
}

BODIES = {
    OrderStage.CHECKOUT: "<p>Hi {{customer_name}}, we received order {{order_id}} for {{total}}.</p>",
    OrderStage.FULFILLMENT: "<p>Hi {{customer_name}}, order {{order_id}} shipped. Tracking: {{tracking_number}}.</p>",
    OrderStage.RECEIPT: "<p>Hi {{customer_name}}, your receipt total for order {{order_id}} is {{total}}.</p>",
    OrderStage.CUSTOMER_UPDATE: "<p>Hi {{customer_name}}, {{update_text}}</p>",
}


def prepare_lifecycle_template(request: TemplateRequest, api: Any) -> PreparedTemplate:
    if request.stage is OrderStage.FULFILLMENT and not request.tracking_number:
        raise ValueError("tracking_number is required for fulfillment")
    if request.stage is OrderStage.CUSTOMER_UPDATE and not request.update_text:
        raise ValueError("update_text is required for customer updates")

    template_name = f"order-{request.order_id}-{request.stage.value}"
    created = api.email_template_create(
        {"name": template_name, "subject": SUBJECTS[request.stage], "html": BODIES[request.stage]},
        idempotency_key=f"template:{template_name}",
    )
    template_id = str(created["id"])
    template_vars = {
        "order_id": request.order_id,
        "customer_email": str(request.customer_email),
        "customer_name": request.customer_name,
        "total": request.total,
        "tracking_number": request.tracking_number or "",
        "update_text": request.update_text or "",
    }
    preview = api.email_template_preview(template_id, template_vars)
    return PreparedTemplate(template_id=template_id, template_name=template_name, preview=preview)
