# Triggers

Triggers let you run Lamia scripts automatically when events happen — like receiving an email or a file being changed.

## Syntax

Use `trigger.<event_type>(output_vars, config_key="value")` at the top of your script:

```python
trigger.email_received(sender, subject, body)
```

- **Bare names** (`sender`, `subject`, `body`) become local variables populated with event data
- **String kwargs** (`path="path/to/my/file"`) are config params that control which events to listen to

## Supported Events

### `trigger.email_received(...)`

Fires when a new email arrives (via Gmail push notifications).

Available fields: `sender`, `subject`, `body`, `html_body`, `message_id`, `thread_id`, `timestamp`, `attachments`, `labels`

```python
trigger.email_received(sender, subject, body)
classify_email(sender, subject, body) -> JSON[Category]
```

### `trigger.file_created(...)`

Fires when a file is created in a storage bucket.

Config params: `path`

Available fields: `name`, `size`, `content_type`, `timestamp`, `metadata`

```python
trigger.file_created(name, size, content_type, path="invoices-bucket")
if name.endswith(".pdf"):
    process_invoice(name) -> JSON[Invoice]
```

### `trigger.file_modified(...)` / `trigger.file_deleted(...)`

Same fields as `file_created`, fires on modification or deletion.

## Deploying Triggers

```bash
lamia trigger add email_handler.lm --remote
```

This single command:
1. Builds and deploys your script as a Cloud Run Job
2. Creates the orchestration workflow
3. Sets up event routing (Eventarc)

### Managing triggers

```bash
lamia trigger list                    # List all triggers with status
lamia trigger remove <id>             # Remove a trigger
```

## Multi-Trigger Scripts

Scripts can have multiple triggers (sequential stages):

```python
trigger.email_received(sender, subject, body)
classification = classify_email(sender, subject, body) -> JSON[Category]

trigger.file_created(name, size, path="attachments-bucket")
process_attachment(name, classification) -> JSON[Report]
```

Each trigger boundary creates a new execution stage. The workflow waits for the next event before proceeding.

## Testing Locally

Set the `LAMIA_TRIGGER_EVENT` environment variable with JSON data:

```bash
export LAMIA_TRIGGER_EVENT='{"sender":"test@example.com","subject":"Test","body":"Hello"}'
lamia email_handler.lm
```

## Requirements

- Cloud triggers require `lamia-lang[cloud]` (`pip install "lamia-lang[cloud]"`)
- A GCP project with `project_id` in your `config.yaml`
- Eventarc, Workflows, and Cloud Run APIs enabled
