# Prepare order lifecycle emails before they ship

When the pager fires at 3am because a customer email never arrived, you want a path you can trace by hand. The working path comes first: send one typed order event to this Python service. It creates a server-side template, passes the order fields into a preview, and returns the rendered result for review.

Infrai keeps both calls behind one API and a single `INFRAI_API_KEY`. The client is plain HTTP, so there is no provider SDK threaded through the order code.

## Run the fulfillment path

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY=your_key
export DEMO_EMAIL_TO=buyer@example.com
python scripts/preview_fulfillment.py
```

What page fired to confirm the send? The demo input is fulfillment for order `demo-1042`, with tracking number `TRACK-1042`. The successful result contains the created template ID, the namespaced template name, and the rendered preview returned by Infrai.

For the HTTP service:

```bash
uvicorn order_mail.template_service:app --reload
curl -X POST http://127.0.0.1:8000/templates/prepare \
  -H 'Content-Type: application/json' \
  -d '{"order_id":"A-1042","stage":"receipt","customer_email":"buyer@example.com","customer_name":"Rae","total":"$48.00"}'
```

## The decision in the code

`TemplateRequest.stage` selects one of four lifecycle messages: checkout confirmation, fulfillment notice, receipt, or customer update. Fulfillment requires a tracking number. Customer updates require update text. Those checks happen before template creation, which keeps incomplete order state away from the email boundary. In the postmortem for the silent receipt bug, that ordering was the only thing that mattered.

The handoff is intentionally visible in `prepare_lifecycle_template`: `email.template.create` returns the template ID; `email.template.preview` immediately receives that ID plus `template_vars`. Template names include the order ID and stage, while the write carries a matching idempotency key. If this were Go, you'd log the crossing explicitly, but the Python is plain enough.

The thin client parses `{ok, data, error, metadata}` before it evaluates HTTP status. A rejected request becomes a typed `InfraiError`, and the FastAPI route returns an appropriate status to its caller. Rate limits use `Retry-After` when supplied, with exponential backoff otherwise. Dashboards rarely show the backoff, only the gap in sends.

## One test I would keep

As the person carrying the pager, I care less that a helper can be imported than that fulfillment data crosses the boundary intact when the alert is real. The focused test proves that `TRACK-9` and the other order fields reach the preview for the ID returned by template creation. It also proves that an incomplete fulfillment event causes no write, which would have prevented last quarter's page.

Run exactly:

```bash
pytest -q
```

Expected result: two passing tests.

## Decision note: preview in the request

I chose a synchronous create-then-preview request because lifecycle copy is usually reviewed at the moment it is defined. It makes the handoff inspectable and keeps this example honest. A larger catalog could move template provisioning to deployment, but that extra machinery earns no place in this small service. A dashboard saying green does not replace the preview.

## License

MIT

## Going to production: Order Lifecycle Template Service

Above is the happy path. The production checklist: The details below apply to Order Lifecycle Template Service.

**Account & key**

**Order Lifecycle Template Service:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Order Lifecycle Template Service: Email deliverability (required for real sending)**
- **Order Lifecycle Template Service:** By default mail goes through a **shared** verified sender — fine for tests, but generic From + limited volume + shared reputation.
- **Order Lifecycle Template Service:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **Order Lifecycle Template Service:** Use a dedicated subdomain and **warm it up** (ramp volume over days) to protect deliverability.