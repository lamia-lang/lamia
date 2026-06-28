# lamia-cloud

Run Lamia scripts in the cloud with the same `.lm` workflow you use locally.

`lamia-cloud` currently supports GCP and gives you:

- one-time cloud execution with `--remote`
- cloud scheduling with Cloud Scheduler
- Cloud Run Job execution with logs in Cloud Logging
- upcoming cloud triggers support

## Installation

```bash
pip install "lamia-lang[cloud]"
```

## Configuration

Add a `cloud` section to your project's `config.yaml`:

```yaml
cloud:
  provider: gcp
  project_id: my-gcp-project
  location: us-central1
```

| Field | Required | Description |
|-------|----------|-------------|
| `provider` | yes | Cloud provider (`gcp`) |
| `project_id` | yes | Your GCP project ID |
| `location` | yes | Region for scheduling and execution (e.g. `us-central1`) |

## Authentication

lamia-cloud uses Application Default Credentials. Authenticate once:

```bash
gcloud auth application-default login
```

## One-time Cloud Run (`--remote`)

```bash
lamia my_script.lm --remote
```

Use this first to validate cloud permissions, runtime behavior, and logs before creating a schedule.

## Cloud Scheduling

```bash
lamia schedule add daily_task.lm --every day --remote
```

This uses the same cloud runtime as one-time `--remote` execution.

All other commands work transparently:

```bash
lamia schedule list          # shows both local and cloud jobs
lamia schedule update <id> --cron "0 12 * * *"
lamia schedule remove <id>   # tears down the cloud job + scheduler job
```

## How It Works

1. `lamia <script>.lm --remote` packages your project and deploys a Cloud Run Job
2. Your script runs via the `lamia` CLI inside the job container (same script semantics as local)
3. `lamia schedule add --remote` creates a Cloud Scheduler trigger for that job
4. Logs (stdout/stderr) go to Cloud Logging under Cloud Run Job execution logs
5. Exit status is reported back to the local lamia registry so `lamia schedule list` shows it

## Logs

View execution logs:

```bash
lamia schedule logs <id>
```

Or directly in GCP Console under Cloud Run > Jobs > `lamia-...` > Executions > Logs.

## API Enablement

lamia-cloud automatically enables required APIs on first use.
In restricted org environments where API auto-enablement is blocked by policy,
a platform administrator can run:

```bash
gcloud services enable run.googleapis.com cloudscheduler.googleapis.com cloudbuild.googleapis.com logging.googleapis.com --project=my-gcp-project
```

## Limitations

- Cloud schedules ignore the `catch_up` flag (Cloud Scheduler guarantees execution)
- `@reboot` / `on-wake` presets are not supported in cloud mode
- Scripts using browser automation require additional headless browser setup in cloud environments
- Only GCP is supported currently; additional providers may be added in future versions

## Practical cost note

You usually do **not** need to build custom cloud agents from scratch to start automation in production.
`lamia-cloud` is designed to cover common agentic workflows with much lower setup and maintenance overhead.

## Releasing New Versions

lamia-cloud uses git tags for versioning. To release:

```bash
git tag v0.2.0
git push origin v0.2.0
```

The CI pipeline automatically builds and publishes to PyPI on tagged pushes.
