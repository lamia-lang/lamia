# Triggers

Triggers make your Lamia scripts react to real-world events automatically.
Instead of running a script manually, you define what should start it — an
incoming email, a new file appearing, etc.

## Writing a Triggered Script

Add a `trigger` line at the point in your script where you want to wait for
an event. The parameters you list will be filled in with information from that
event:

```python
trigger.email_received(sender, subject, body)

# From here on, sender/subject/body are available as regular variables.
reply_to_lead(sender, subject, body)
```

String keyword arguments are configuration (they tell Lamia *where* to listen, what to filter out, etc.):

```python
trigger.file_created(name, size, path="sales/pricing")
```

Here `name` and `size` will come from the event, while `path` tells Lamia
which folder to watch.

## Available Events

### Email received

```python
trigger.email_received(sender, subject, body)
```

Fields you can request: `sender`, `subject`, `body`, `html_body`, `message_id`,
`thread_id`, `timestamp`, `attachments`, `labels`.

### File created / modified / deleted

```python
trigger.file_created(name, size, content_type, path="reports/incoming")
trigger.file_modified(name, timestamp, path="shared/data")
trigger.file_deleted(name, path="archive/temp")
```

Fields: `name`, `size`, `content_type`, `timestamp`, `metadata`.

The `path` parameter specifies the folder or location to monitor.

## Deploying

When you deploy a script that contains `trigger.*` calls, Lamia automatically
sets up the event infrastructure for you.

## Choosing a Mode

### Reactive mode

Each event starts its own independent script execution right away.

Best for: notifications that must be handled immediately (order confirmations,
alerts, time-sensitive replies).

To deploy a script that contains `trigger.*`s in reactive mode use:

```bash
lamia pricing_reply.lm --remote
```

### Scheduled mode (similar to how an employee would work)

Events accumulate. At the scheduled time, the script wakes up, processes every
pending event in parallel (one script execution per event), then sleeps until
the next scheduled time.

Best for: tasks where you want to appear human
(answering emails in the morning, processing daily uploads).

To deploy a script that contains `trigger.*`s in scheduled mode use:

```bash
lamia schedule add pricing_reply.lm --remote --cron "33 9 * * *"
```

This will deploy the script to the cloud and set up a cron job to run the script at 9:33 AM every day.

## Multi-Step Scripts

A script can wait for more than one event. Each additional `trigger.*` call
pauses the script until that event arrives (up to 72 hours).

Every script execution is parallel and fully **isolated**. Each execution waits for its own event and runs independently.

### Example: Enterprise Pricing Approval

Below is a complete script that handles pricing inquiries. Regular requests
get an automated response. Enterprise requests need a human to prepare custom
pricing, so the script waits for that file to appear.

```python
from enum import Enum
from pydantic import BaseModel, Field


class LeadType(str, Enum):
    ENTERPRISE = "enterprise"
    STANDARD = "standard"


class LeadClassification(BaseModel):
    lead_type: LeadType = Field(description="Whether this is an enterprise or standard lead")
    company_slug: str = Field(description="Short lowercase identifier for the company, e.g. 'bigcorp'")


trigger.email_received(sender, subject, body, to="pricing@ourcompany.com")

classification = classify_lead(sender, subject, body) -> LeadClassification

if classification.lead_type == LeadType.STANDARD:
    pricing_page = web.get_text("https://ourcompany.com/pricing")
    compose_reply(sender, subject, pricing_page) -> File("drafts/reply.txt")
else:
    notify_sales_team(sender, subject, classification.company_slug)

    trigger.file_created(name, timestamp, path="sales/custom-pricing")

    if not name.startswith(classification.company_slug):
        trigger.reject()
    else:
        pricing_content = file.read(f"sales/custom-pricing/{name}")
        compose_custom_reply(sender, name, pricing_content) -> File("drafts/reply.txt")
```

How this works at runtime:

1. An email arrives to `pricing@ourcompany.com`. Lamia starts a new, isolated
   execution of the script. Emails to other addresses are filtered out at the
   infrastructure level and never start the script.
2. The AI classifies the lead with a validated return type — you get a typed
   `LeadClassification` object with `lead_type` and `company_slug`.
3. **Standard lead**: reply is composed immediately, execution finishes.
4. **Enterprise lead**: the script notifies the sales team and pauses (up to
   72 hours) waiting for a file in `sales/custom-pricing`.
5. When a team member uploads a file, the waiting execution resumes and checks
   whether the filename starts with the expected company slug.
6. **Wrong file**: `trigger.reject()` skips this event and the script keeps
   waiting for the next file event.
7. **Correct file**: reads the content and sends the custom reply.

If no file appears within 72 hours, the execution times out gracefully.

## Best Practices

### Use keyword filters to avoid unnecessary execution

Any keyword argument with a string value acts as an infrastructure-level
filter. The script never starts for events that don't match. You can combine
multiple filters on a single trigger:

```python
trigger.email_received(sender, subject, body,
                       to="pricing@ourcompany.com",
                       from_domain="enterprise.com")

trigger.file_created(name, size, path="sales/invoices")
```

Filters are the most efficient approach — they prevent the job from launching
entirely, saving both time and cost.

### Use `trigger.reject()` when filtering depends on runtime data

When the filter can't be known at deploy time (e.g. it depends on a value
computed earlier in the script), use `trigger.reject()` to skip the event
and keep waiting for a different one:

```python
trigger.file_created(name, timestamp, path="sales/custom-pricing")

if not name.startswith(expected_prefix):
    trigger.reject()
```

`trigger.reject()` applies to the most recent trigger. It acknowledges the
event (so it won't come back to this execution) and the script continues
waiting for the next event on its private listener.

Since each execution has its own isolated listener, rejecting an event in one
execution does not affect other concurrent executions — they each receive
their own independent copy of every event.

### Unhandled exceptions

If your script raises an unhandled exception after a trigger resumes, the
event is retried automatically (up to 5 attempts). After all retries are
exhausted, the event is saved as a **failed event** and can be inspected
via `lamia trigger list --verbose`.

Failed events expire automatically after a retention period — there is no
manual clearing step.

## How Isolation Works

Each script execution that reaches a waiting point creates its own private
event listener. This means:

- There is no queue contention — concurrent waits run in full isolation.
- Finished executions clean up their listeners automatically.

## Listing Triggers

To see what triggers are configured:

```bash
lamia trigger list
```

Example output:

```
  [pricing-reply] pricing_reply.lm
    event: email_received
    mode: reactive
    last run: 2026-07-09  status: ok
    failed events: 2
```

To see details of failed events (what data they contained):

```bash
lamia trigger list --verbose
```

This shows the actual event payload and timestamp for each failure, so you
can understand what went wrong and take action.

## Viewing Logs

Triggers run in the cloud, so their output never reaches your terminal. Use the
id from `lamia trigger list` to read the most recent run:

```bash
lamia trigger logs pricing-reply
```

Multi-stage triggers print each stage in order.

## Requirements

- Currently triggers are only supported in remote mode (`--remote`).
- Install cloud support: `pip install "lamia-lang[cloud]"`
- Set `cloud.project_id` in your project `config.yaml`.
