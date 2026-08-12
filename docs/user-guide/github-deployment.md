# Git-Based Deployment

Deploy lamia scripts from a git repository. Containers are built from committed source instead of local files, so every team member and CI pipeline produces identical deployments.

## Prerequisites

- `pip install lamia-lang[cloud]`
- A `config.yaml` with a `cloud` section (`provider`, `project_id`)
- Cloud provider CLI installed and authenticated (admin only, one-time setup)

Developers who only push code do not need cloud credentials.

## Connecting Your Repository

One administrator runs this once per repository:

```bash
lamia cloud connect
```

This authorizes the repository to deploy to the cloud project configured in `config.yaml`. During connect, Lamia opens an interactive GitHub device authorization flow and configures required repository CI variables automatically. Do not store CI auth fields in `config.yaml`.

The Lamia GitHub App must be installed on the repository (or its organization) with read/write access to Actions variables. If connect reports that variables could not be written, install the app for the repository and rerun `lamia cloud connect`.

All team members and CI pipelines can deploy after this step without any additional cloud setup.

By default, only the `main` branch is authorized for CI deployments. To use a different branch:

```bash
lamia cloud connect --branch master
```

### Verifying and Revoking

```bash
lamia cloud status       # check connection
lamia cloud disconnect   # revoke access
```

## Deploying

When you run `lamia ... --remote` inside a connected repository, lamia uses git mode automatically:

```bash
lamia schedule add daily_task.lm --every day --remote
```

The cloud provider clones the latest source from your repository and builds the container. Re-running the same command updates the existing deployment in place (idempotent).

Resource IDs are derived from the git remote URL, not your local checkout path. Different machines deploying the same repository produce the same cloud resource.

### Forcing Local Mode

To deploy uncommitted changes for testing:

```yaml
cloud:
  project_id: my-project
  deploy_mode: local
```

### Private Repositories

Private repositories work after `lamia cloud connect`. The cloud provider's app is installed on the repository with read access for cloning. No SSH keys or personal tokens are needed.

## CI Integration

Add a GitHub Actions workflow to redeploy on push:

```yaml
name: Deploy Lamia Scripts
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read
    env:
      LAMIA_CONNECTION_ID: ${{ vars.LAMIA_CONNECTION_ID }}
    steps:
      - uses: actions/checkout@v4
      - run: pip install "lamia-lang[cloud]"
      - run: lamia schedule add daily_task.lm --every day --remote
```

`lamia cloud connect` already stored `LAMIA_CONNECTION_ID` as a repository variable, so there is nothing to copy or paste. The `env:` line exists only because GitHub Actions does not expose repository variables to the job automatically — a variable is readable by the process only when the workflow references it through `vars`. Which repository is being deployed comes from the runner itself, so it needs no variable at all.

For a monorepo, add a `paths` filter:

```yaml
on:
  push:
    branches: [main]
    paths:
      - 'my_project/**'
```

Keep the same job permissions in monorepo workflows:

```yaml
permissions:
  id-token: write
  contents: read
```

The `permissions: id-token: write` line is required for CI authentication. If GitHub authorization is interrupted during `lamia cloud connect`, rerun `lamia cloud connect` to complete variable setup.

### CI Secrets

Use repository secrets for runtime API keys and pass them through workflow environment variables:

```yaml
env:
  ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
  OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

Lamia reads these values from process environment in CI. For local development, Lamia continues to read shell env, project `.env`, and global `~/.lamia/.env`.

The example above installs the latest release, so CI picks up fixes without any maintenance. If you would rather a lamia release never change your deploys until you say so, pin the version explicitly:

```yaml
      - run: pip install "lamia-lang[cloud]==1.4.0"
```

Pinning is the safer default for production deploys; using latest is fine while iterating.

## Security

### General CI/CD Security

These practices apply to any language or project using CI/CD — they are not specific to lamia.

**Protect the main branch.** The main branch is the deployment gate. Code merged to main can be deployed to production. Use branch protection rules to require code reviews before merging.

**Open-source projects require extra vigilance.** Anyone can submit a pull request. Maintainers must review code carefully before merging — a malicious contribution that reaches main will be deployed by CI. Enable required reviews from code owners and use GitHub's merge queue for automated checks before merge.

**Private repositories are simpler but not risk-free.** Access is limited to collaborators, but credential leaks and compromised accounts remain threats. Use minimal repository permissions and audit collaborator access regularly.

### How Lamia CI Security Works

- **No static credentials.** CI authentication uses short-lived tokens that expire within minutes. No long-lived keys or secrets are stored anywhere.
- **Repository-scoped trust.** Each repository is authorized individually via `lamia cloud connect`. Only the specific repository (and branch) authorized by the admin can authenticate.
- **Branch restriction.** Only the branch specified during `lamia cloud connect` (default: `main`) can deploy from CI. Feature branches, forks, and pull requests cannot authenticate. Re-running `lamia cloud connect --branch <name>` on an already-connected repository rewrites the restriction to the new branch.
- **Per-repository isolation.** Each connected repository gets its own credentials and permissions. A compromised repository cannot affect other repositories in the same cloud project.
- **Privilege separation.** CI deployments run with deploy permissions. Deployed scripts run with minimal permissions (only what the script needs, such as model access). Deployed code cannot redeploy or modify infrastructure.
- **Mandatory admin setup.** CI cannot deploy without a prior `lamia cloud connect`. There is no way for a repository to self-authorize.
- **Fork protection.** Fork pull requests cannot obtain deployment credentials. GitHub does not grant identity tokens to fork PRs by default, and the cloud trust is scoped to the exact repository.

### Workflow Trigger Safety

Lamia only authenticates for events that run code already merged into the deploy branch:

| Event | CI auth |
|---|---|
| `push`, `workflow_dispatch`, `schedule`, `release` | Allowed |
| everything else | Refused |

Anything outside that list is rejected, so newly introduced GitHub trigger types are denied by default rather than silently permitted.

The notable rejections are `pull_request_target` and `workflow_run`, which run in the base repository's security context while being triggered by an outside contributor — a fork PR could otherwise reach production credentials. `pull_request` is refused as well: same-repo PRs carry the repository's identity and would let unreviewed code deploy.

This check is defense-in-depth and produces a clear error message. The binding restriction is the cloud-side trust condition, which accepts only the exact repository and branch regardless of event type.

## Updating Scripts

Run the same command again:

```bash
lamia schedule add daily_task.lm --every day --remote
```

The command is idempotent. The same script in the same repository maps to the same cloud resource.

For local schedules, no redeployment is needed. The schedule references the script file on disk.
