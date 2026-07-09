# Triggers

Triggers make your Lamia scripts react to real-world events automatically.
Instead of running a script manually, you define what should start it — an
incoming email, a new file appearing, etc. — and Lamia takes care of the rest.

## Writing a Triggered Script

Add a `trigger` line at the point in your script where you want to wait for
an event. The parameters you list will be filled in with information from that
event:

```python
trigger.email_received(sender, subject, body)

# From here on, sender/subject/body are available as regular variables.
reply_to_lead(sender, subject, body)
```

String keyword arguments are configuration (they tell Lamia *where* to listen):

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

**Immediate reaction** — the script runs every time the event happens:

```bash
lamia pricing_reply.lm --remote
```

**Scheduled (employee mode)** — events collect overnight and the script
processes them all at a set time:

```bash
lamia schedule add pricing_reply.lm --remote --every day
```

To see what is deployed:

```bash
lamia trigger list
```

## Choosing a Mode

### Always-reactive

Each event starts its own independent script execution right away.

Best for: notifications that must be handled immediately (order confirmations,
alerts, time-sensitive replies).

### Employee mode (scheduled)

Events accumulate. At the scheduled time, the script wakes up, processes every
pending event in parallel (one script execution per event), then sleeps until
the next scheduled time.

Best for: tasks where batching is acceptable or where you want to appear human
(answering emails in the morning, processing daily uploads).

## Multi-Step Scripts

A script can wait for more than one event. Each additional `trigger.*` call
pauses the script until that event arrives (up to 72 hours).

Every script execution is fully **isolated** — if 10 emails arrive and each
starts waiting for a file, they all wait independently. One execution receiving
its file does not affect the others.

### Example: Enterprise Pricing Approval

Below is a complete script that handles pricing inquiries. Regular requests
get an automated response. Enterprise requests need a human to prepare custom
pricing, so the script waits for that file to appear.

```python
trigger.email_received(sender, subject, body)

# AI classifies the request
classification = classify_lead(sender, subject, body) -> JSON

if not classification["enterprise"]:
    # Standard request — send public pricing immediately
    pricing_page = web.get_text("https://ourcompany.com/pricing")
    compose_reply(sender, subject, pricing_page) -> File("drafts/reply.txt")
else:
    # Enterprise request — notify the team and wait for human input.
    # The sales team places a custom pricing document at this path
    # within 72 hours. The file name should reference the request
    # (e.g. "bigcorp-2026-07.pdf").
    notify_sales_team(sender, subject, body)

    trigger.file_created(name, timestamp, path="sales/custom-pricing")

    # Script resumes here once the file appears.
    compose_custom_reply(sender, name) -> File("drafts/reply.txt")
```

How this works at runtime:

1. An email arrives. Lamia starts a new, isolated execution of the script.
2. The AI classifies the request.
3. **Standard request**: reply is sent immediately, execution finishes.
4. **Enterprise request**: the script pauses and waits (up to 72 hours) for a
   file to appear at `sales/custom-pricing`.
5. Meanwhile, other emails can arrive and start their own independent
   executions — they do not interfere with each other.
6. When a team member uploads the pricing file, the waiting execution resumes
   and sends the custom reply.

If no file appears within 72 hours, the execution times out gracefully.

## How Isolation Works

Each script execution that reaches a waiting point creates its own private
event listener. This means:

- Execution A waiting for a file will not accidentally consume a file meant
  for Execution B.
- There is no queue contention — concurrent waits run in full isolation.
- Finished executions clean up their listeners automatically.

## Requirements

- Triggers run in remote mode (`--remote`).
- Install cloud support: `pip install "lamia-lang[cloud]"`
- Set `cloud.project_id` in your project `config.yaml`.
