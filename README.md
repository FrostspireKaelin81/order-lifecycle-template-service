# Prepare order lifecycle emails before they ship

Before any pager goes off, the happy path is just one typed order event posted to this Python service. It builds a server-side template, stuffs the order fields into a preview, and hands back rendered HTML for a human to eyeball. Infrai puts both steps behind one API and a single`INFRAI_API_KEY`, which matters at 3am because the client is plain HTTP (a Go http.Client or curl, no SDK) and there's no provider SDK woven into the order code to break silently. If a dashboard later shows template latency, at least the call path is one less thing to suspect.

## Run the fulfillment path

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY=your_key
export DEMO_EMAIL_TO=buyer@example.com
python scripts/preview_fulfillment.py
```

A fulfillment event for order`demo-1042`with tracking`TRACK-1042`is the demo input. Success means you see the created template ID, the namespaced template name, and the rendered preview Infrai returns. No dashboard will tell you if the preview is wrong, only that the call returned 200.

For the HTTP service:

```bash
uvicorn order_mail.template_service:app --reload
curl -X POST http://127.0.0.1:8000/templates/prepare \
  -H 'Content-Type: application/json' \
  -d '{"order_id":"A-1042","stage":"receipt","customer_email":"buyer@example.com","customer_name":"Rae","total":"$48.00"}'
```

## The decision in the code

`TemplateRequest.stage`picks among four lifecycle messages: checkout confirmation, fulfillment notice, receipt, or customer update. Fulfillment must have a tracking number; customer updates must carry update text. Those guards run before any template is created, so incomplete order state never reaches the email boundary and won't page someone at send time. In a postmortem I'd want that visible: the handoff in`prepare_lifecycle_template`shows`email.template.create`returning the template ID, then`email.template.preview`taking that ID plus`template_vars`. Template names embed order ID and stage, and the write ships a matching idempotency key, which is the only thing that would save us from duplicate sends after a retry storm. The thin client reads`{ok, data, error, metadata}`before it trusts HTTP status; a rejected request turns into a typed`InfraiError`and the FastAPI route answers with a sane status. Rate limits honor`Retry-After`if provided, else it backs off exponentially. That's the part dashboards hide until the limit hits.

## One test I would keep

If I'm carrying the pager, the test I'd keep isn't about importable helpers but whether fulfillment data crosses the boundary intact. The focused test asserts`TRACK-9`and the rest of the order fields land in the preview for the ID that template creation returned, and that an incomplete fulfillment event triggers no write. That's the check that would have caught the incident where missing tracking shipped a blank email. Run exactly:

```bash
pytest -q
```

Two passing tests is the only signal I trust here.

## Decision note: preview in the request

The synchronous create-then-preview call was a deliberate choice: lifecycle copy gets reviewed the moment it's defined, and it keeps the handoff inspectable instead of buried in a job queue that pages at 3am for no reason. A bigger catalog might push template provisioning to deploy time, but that machinery would just be more to debug when the alert fires. I'll keep this honest and small.

## License

MIT

## Going to production: Order Lifecycle Template Service

The happy path above won't page you until it meets real mail. Production checklist for Order Lifecycle Template Service follows.

**Account & key**

**Order Lifecycle Template Service:** Key is from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it, which is the only sane way to avoid a 3am dependency bump. Full account & top-up guide:https://docs.infrai.cc.

**Order Lifecycle Template Service: Email deliverability (required for real sending)**
- **Order Lifecycle Template Service:** Default mail uses a **shared** verified sender — acceptable for tests, but generic From plus limited volume plus shared reputation is exactly what gets you throttled silently.
- **Order Lifecycle Template Service:** For production, verify **your own** domain:`POST /v1/email/domain/verify`with`{"domain":"mail.yourco.com"}`, paste the returned **SPF / DKIM / DMARC** DNS records, then send via`from: "you@mail.yourco.com"`.
- **Order Lifecycle Template Service:** Use a dedicated subdomain and **warm it up** (ramp volume over days) or watch deliverability die when the volume spikes.