# lamia-cloud

Run Lamia scripts in the cloud with the same `.lm` workflow you use locally.

`lamia-cloud` currently supports GCP and gives you:

- one-time cloud execution with `--remote`
- cloud scheduling with Cloud Scheduler
- Cloud Run Job execution with logs in Cloud Logging
- event-driven triggers (see [Triggers](../user-guide/triggers.md))

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

## File Sync for Cloud Execution

When your script uses `with files(...)` to provide context to the LLM, Lamia automatically uploads the referenced files to cloud storage (GCS) so the script runs identically in the cloud.

### What gets uploaded

**Only** the folders and files specified in `with files(...)` syntax are uploaded. Nothing else.

```python
with files("./docs", "./data/input.csv"):
    def summarize():
        "Summarize {@report.pdf} and {@input.csv}"
```

In this example, every file inside `./docs/` and the single file `./data/input.csv` are synced to cloud storage.

### How it works at runtime

When files are synced, the GCS bucket is mounted as the container's working directory via GCS FUSE. All relative file paths in your script resolve directly into the mounted bucket. Reads pull from the bucket, writes go to the bucket. No copying, no configuration — transparent filesystem.

### Incremental sync

Lamia tracks file checksums. On subsequent deploys, only changed or new files are uploaded. Files already in the bucket with matching content are skipped. This keeps re-deploy times fast.

When multiple team members sync the same project, Lamia issues a warning before overwriting files that have been modified by someone else.

### Security considerations

All files in `with files(...)` directories are uploaded recursively. This includes every file in the folder — Lamia uploads everything so the LLM context resolution works exactly as on your local machine.

**Risks to be aware of:**

1. **Secrets** — Lamia scans for common secret file patterns (`.env`, files containing `API_KEY`, `private key`, etc.) and blocks the upload with a clear error. Nevertheless, review what's in your directories before deploying.

2. **Security surface** — Every file you upload exists in cloud storage. Fewer files = smaller attack surface. Only upload what the script actually needs.

3. **Sync speed** — Larger directories mean more files to check and upload on every script update. Every time you modify your script, Lamia must scan the referenced directories and sync changes. Hundreds of large files slow this down.

4. **Storage and bandwidth cost** — GCS storage is cheap (~$0.02/GB/month for Standard), but bandwidth adds up with large syncs. For typical Lamia usage (documents, configs, CSVs), costs are negligible — a few cents per month. If you're syncing gigabytes of data, consider limiting scope.

### Best practices

| Practice | Why |
|----------|-----|
| Create a dedicated folder for your script's data (e.g., `./context/`) | Keeps scope clear, fast sync, no surprise files |
| Avoid pointing `with files(...)` at `~/Documents` or home directories | Personal files, secrets, irrelevant data — all gets uploaded |
| Use relative paths from the project root | Portable across machines and team members |
| Keep referenced directories small and focused | Faster sync, lower cost, better LLM context quality |

**It is not terrible to reference a larger directory** — Lamia handles it correctly and securely. The practical concern is that LLMs can get lost in large file sets (context dilution), sync gets slower, and the security surface grows. If your workflow genuinely needs many files, it works — just understand the tradeoffs.

---

## Gitflow for Lamia (Team Workflows)

When multiple developers work on a shared Lamia project, file paths must be consistent across machines. The recommended approach: **use paths relative to the Git repository root**.

### The problem with absolute paths

```python
# BAD for teams — breaks on other machines
with files("~/Documents/company_data/"):
    def analyze():
        "Summarize {@quarterly_report.pdf}"
```

This works for one developer but fails for everyone else (different home directory, different folder structure).

### The solution: repository-relative paths

```python
# GOOD for teams — works for everyone who clones the repo
with files("./data/"):
    def analyze():
        "Summarize {@quarterly_report.pdf}"
```

Place the files your script needs inside the Git repository (or a subdirectory of it). Every team member gets the same structure after cloning.

### Recommended project structure for teams

```
my-project/              ← Git repository root
├── config.yaml          ← cloud configuration
├── daily_report.lm      ← script
├── data/                ← files referenced in with files("./data/")
│   ├── templates/
│   │   └── report_template.html
│   └── reference_data.csv
└── requirements.txt
```

### Rules for team-shared projects

1. **All `with files(...)` paths must be relative** — no `~/`, no `/absolute/paths`
2. **Referenced directories must be inside the Git repository** — otherwise teammates won't have them
3. **Git is the recommended source control** — Lamia assumes Git when detecting project boundaries for teams
4. **Uploading to Git does NOT eliminate cloud sync** — Lamia still syncs files to the GCS bucket for fast runtime access. Git is the source of truth; the bucket is the execution cache.

### Sensitive files in team repos

Be careful:

- Don't commit secrets to the repository
- Lamia will still block uploads of detected secret files but you will still have a problem if you commit them to the repository.
- If you have not committed files in the repository lamia --remote command will upload your locale executable and instead of the state that is in the remote git repo as the team would expecct you local state would be running on the cloud. That is why CI/CD flow is a recommened appoach for the team projects.

### CI/CD integration (GitHub Flow)

For automated deployments, set up a CI workflow that triggers `lamia <script>.lm --remote` when relevant files change:

```yaml
# .github/workflows/lamia-deploy.yml
name: Deploy Lamia Script

on:
  push:
    branches: [main]
    paths:
      - 'daily_report.lm'
      - 'data/**'
      - 'config.yaml'

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install "lamia-lang[cloud]"
      - run: lamia daily_report.lm --remote
        env:
          GOOGLE_APPLICATION_CREDENTIALS: ${{ secrets.GCP_SA_KEY }}
```

This ensures the cloud deployment updates whenever the script or its data files change in the repository — no manual `--remote` runs needed.

**Benefits over manual sync:**

- Only committed and pushed changes get deployed (no accidental local files)
- Full audit trail of what was deployed and when
- Team members don't need individual GCP credentials for deployment

---

## Limitations

- Scripts using browser automation uses headless browser setup in cloud environments which is inferior to the 
- Only GCP is supported currently; additional providers may be added in future versions

## Practical cost note

You usually do **not** need to build custom cloud agents from scratch to start automation in production.
`lamia-cloud` is designed to cover common agentic workflows with much lower setup and maintenance overhead.
