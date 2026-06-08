# lamia-cloud

Cloud scheduling for Lamia scripts. Scripts run entirely in the cloud — no local machine needed. Currently supports GCP.

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

For CI/CD environments, use a service account with the following roles:
- `roles/cloudfunctions.developer`
- `roles/cloudscheduler.admin`
- `roles/iam.serviceAccountUser`

## Usage

```bash
lamia schedule add daily_task.lm --every day --remote
```

That's it. lamia-cloud handles the full deployment:
1. Packages your `.lm` script and its project directory
2. Deploys a Cloud Function with the lamia runtime
3. Creates a Cloud Scheduler job that triggers the function on your cron schedule

All other commands work transparently:

```bash
lamia schedule list          # shows both local and cloud jobs
lamia schedule update <id> --cron "0 12 * * *"
lamia schedule remove <id>   # tears down the cloud function + scheduler job
```

## How It Works

1. `lamia schedule add --remote` packages your script into a Cloud Function deployment
2. The function includes the `lamia` runtime — your script runs identically to local execution
3. Cloud Scheduler triggers the function on the configured cron
4. Logs (stdout/stderr) go to Cloud Logging under the function's log stream
5. Exit status is reported back to the local lamia registry so `lamia schedule list` shows it

## Logs

View execution logs:

```bash
lamia schedule logs <id>
```

Or directly in GCP Console under Cloud Functions > lamia-schedule-<id> > Logs.

## API Enablement

lamia-cloud automatically enables the required APIs (`cloudfunctions`, `cloudscheduler`, `cloudbuild`) on first use if your credentials have sufficient permissions. If auto-enablement fails:

```bash
gcloud services enable cloudfunctions.googleapis.com cloudscheduler.googleapis.com cloudbuild.googleapis.com --project=my-gcp-project
```

## Limitations

- Cloud schedules ignore the `catch_up` flag (Cloud Scheduler guarantees execution)
- `@reboot` / `on-wake` presets are not supported in cloud mode
- Scripts using browser automation (Selenium) require additional configuration for headless Chrome in the cloud environment
- Only GCP is supported currently; additional providers may be added in future versions

## Releasing New Versions

lamia-cloud uses git tags for versioning. To release:

```bash
git tag v0.2.0
git push origin v0.2.0
```

The CI pipeline automatically builds and publishes to PyPI on tagged pushes.
