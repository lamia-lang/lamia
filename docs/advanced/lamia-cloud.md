# lamia-cloud

Cloud scheduling and cloud-triggered execution for Lamia scripts. Currently supports GCP (Google Cloud Platform).

## Installation

```bash
pip install "lamia-lang[cloud]"
```

To always have the latest version (e.g. during development):

```bash
pip install --upgrade "lamia-lang[cloud]"
```

Or install directly from git for the bleeding-edge version:

```bash
pip install git+https://github.com/lamia-lang/lamia-cloud.git
```

## Configuration

Add a `cloud` section to your project's `config.yaml`:

```yaml
cloud:
  provider: gcp
  project_id: my-gcp-project
  location: us-central1
  target_url: https://my-cloud-run-service.run.app/schedule
```

| Field | Required | Description |
|-------|----------|-------------|
| `provider` | yes | Cloud provider (`gcp`) |
| `project_id` | yes | Your GCP project ID |
| `location` | yes | Cloud Scheduler region (e.g. `us-central1`) |
| `target_url` | yes | HTTP endpoint that receives schedule triggers and runs the script |

## Authentication

lamia-cloud uses Application Default Credentials. Authenticate once:

```bash
gcloud auth application-default login
```

For production (Cloud Run, GKE, etc.), the service account attached to the compute environment is used automatically — no manual auth needed.

## Usage

Once installed and configured, use the standard lamia CLI with `--remote`:

```bash
lamia schedule add daily_task.lm --every day --remote
```

All other schedule commands work transparently:

```bash
lamia schedule list          # shows both local and cloud jobs
lamia schedule update <id> --cron "0 12 * * *"
lamia schedule remove <id>   # removes the cloud scheduler job
```

## How It Works

1. `lamia schedule add --remote` delegates to `lamia-cloud` which creates a Cloud Scheduler job
2. Cloud Scheduler POSTs to your `target_url` on the configured cron schedule
3. The POST body contains `{"schedule_id": "...", "script": "...", "project_root": "..."}`
4. Your Cloud Run service receives the request and executes the `.lm` script with lamia
5. `lamia schedule list` shows cloud jobs alongside local jobs, with backend indicated

## API Enablement

lamia-cloud automatically enables the Cloud Scheduler API on first use if your credentials have sufficient permissions. If auto-enablement fails, enable it manually:

```bash
gcloud services enable cloudscheduler.googleapis.com --project=my-gcp-project
```

## Limitations

- Cloud schedules ignore the `catch_up` flag (Cloud Scheduler guarantees execution)
- `@reboot` / `on-wake` presets fall back to hourly in cloud mode
- Requires a running Cloud Run (or equivalent) service to execute the scripts
- Only GCP is supported currently; additional providers may be added in future versions

## Releasing New Versions

lamia-cloud uses git tags for versioning. To release:

```bash
git tag v0.2.0
git push origin v0.2.0
```

The CI pipeline automatically builds and publishes to PyPI on tagged pushes.
