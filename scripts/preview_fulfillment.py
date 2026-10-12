import json
import os

from order_mail.infrai_client import InfraiClient
from order_mail.lifecycle_templates import OrderStage, TemplateRequest, prepare_lifecycle_template


def main() -> None:
    recipient = os.environ.get("DEMO_EMAIL_TO")
    if not recipient:
        raise SystemExit("DEMO_EMAIL_TO is required")
    client = InfraiClient()
    try:
        result = prepare_lifecycle_template(
            TemplateRequest(
                order_id="demo-1042",
                stage=OrderStage.FULFILLMENT,
                customer_email=recipient,
                customer_name="Sam",
                total="$48.00",
                tracking_number="TRACK-1042",
            ),
            client,
        )
        print(json.dumps(result.model_dump(), indent=2))
    finally:
        client.close()


if __name__ == "__main__":
    main()
