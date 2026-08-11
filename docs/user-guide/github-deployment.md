# Git-Based Deployment

Deploy lamia scripts from a git repository. Containers are built from committed source instead of local files, so every team member and CI pipeline produces identical deployments.

## Connecting Your Repository

Before using git mode, connect your repository with Lamia Cloud. This is a **one-time setup** performed by a project admin -- once connected, all team members can deploy without running this step again.

```bash
lamia cloud connect
```

Run this from inside your git project. Lamia detects the remote origin and sets up the connection with your cloud provider. A browser window opens for authorization -- install the provider's app on your repository or organization, then return to the terminal.

Verify the connection:

```bash
lamia cloud status
```

Any team member can run `lamia cloud status` to check whether the repository is connected to Lamia Cloud. The connection is stored server-side by the cloud provider, so it works from any machine with access to the same cloud project.

No tokens or credentials are stored in your project files. Authentication is handled by the cloud provider's app and managed server-side.

## How It Works

When you run `lamia ... --remote` inside a connected git repository, lamia automatically uses git mode:

```bash
lamia schedule add daily_task.lm --every day --remote
```

In git mode:

1. Lamia generates a Dockerfile and requirements.txt (same as local mode).
2. Only the Dockerfile and requirements.txt are uploaded -- no project files.
3. The cloud provider clones the latest source from your repository and builds the container.
4. The container is deployed as a cloud job.

The Dockerfile is identical in both modes. The only difference is where the project files come from: a local tarball or a git clone.

### Deterministic IDs

Resource IDs are derived from the git remote URL, not the local checkout path. This means a developer deploying from `/Users/sergey/projects/myapp` and CI deploying from `/home/runner/work/myapp/myapp` both produce the same cloud resource name. Re-deploying updates the existing resource instead of creating a duplicate.

### Forcing Local Mode

To deploy from local files even inside a git repo (for example, to test uncommitted changes), set `deploy_mode` in your `config.yaml`:

```yaml
cloud:
  project_id: my-project
  deploy_mode: local
```

### Private Repositories

Private repositories work after `lamia cloud connect`. The cloud provider's app is installed on the repository and has read access for cloning. No SSH keys or personal tokens are needed.

## CI Integration

Use a GitHub Actions workflow to redeploy whenever scripts change:

```yaml
name: Deploy Lamia Scripts
on:
  push:
    branches: [main]
    paths:
      - '**/*.lm'
      - 'requirements.txt'
      - 'config.yaml'

jobs:
  deploy:
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read
    steps:
      - uses: actions/checkout@v4

      - name: Authenticate to cloud provider
        # Use your provider's authentication action.
        # Example for GCP with Workload Identity Federation:
        # uses: google-github-actions/auth@v2
        # with:
        #   workload_identity_provider: ${{ vars.WIF_PROVIDER }}
        #   service_account: ${{ vars.SERVICE_ACCOUNT }}

      - name: Install lamia
        run: pip install "lamia-lang[cloud]==${{ vars.LAMIA_VERSION }}"

      - name: Deploy schedules
        run: |
          lamia schedule add daily_task.lm --every day --remote
          lamia schedule add weekly_report.lm --cron "0 9 * * 1" --remote

      - name: Deploy triggers
        run: |
          lamia email_handler.lm --remote
```

### Key Points

- **No Docker required** in CI. The cloud provider builds the container.
- **No tokens in config files.** CI authenticates via your provider's identity federation. The repository connection (set up via `lamia cloud connect` by a project admin) handles source access.
- **Pin the lamia version.** Store the version in a CI variable (`vars.LAMIA_VERSION`) and update it deliberately.
- **Path filtering.** The `paths` filter avoids redeployments when only documentation or tests change.
- **Same commands as local.** CI runs the exact same lamia commands a developer runs on their machine.
- **`lamia cloud connect` is not needed in CI.** The connection is already established by the admin. CI only needs cloud authentication (e.g., Workload Identity Federation) and `lamia` installed.

## Updating Scripts

After editing a `.lm` script, run the same command again:

```bash
lamia schedule add daily_task.lm --every day --remote
```

The command is idempotent -- the same script in the same repository always maps to the same cloud resource. The container is rebuilt with the latest source and the schedule is updated in place.

For **local schedules**, no redeployment is needed. The schedule references the script file on disk; editing the file is enough.

## Version Management

- **CI**: pin `lamia-lang[cloud]` to a specific version.
- **Local development**: use whatever version is installed.
- **Cloud labels**: each deployed container is tagged with the lamia version that built it.

If a CI deploy and a local deploy use different lamia versions, the source hash check triggers a rebuild. The container always reflects the last person (or CI run) that deployed it.
