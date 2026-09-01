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

## Automatic Deployments (CI)

To deploy automatically on every push, you need a CI pipeline:

- GitHub: **GitHub Actions**
- GitLab: **GitLab CI/CD pipelines**

This is not Lamia-specific. CI is the standard way any project runs commands after code is pushed.

### Common Rule (All CI Systems)

Only keys listed in `cloud.secrets` are uploaded to Secret Manager.  
If a key is not listed there, Lamia ignores it even if it exists in CI environment.

```yaml
cloud:
  provider: gcp
  project_id: my-project
  secrets:
    - OPENROUTER_API_KEY
    - THIRD_PARTY_API_KEY
```

### GitHub Actions

Create this file in your repository:

- Path: `.github/workflows/lamia-deploy.yml`

Example workflow:

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
      OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
      THIRD_PARTY_API_KEY: ${{ secrets.THIRD_PARTY_API_KEY }}
    steps:
      - uses: actions/checkout@v4
      - run: pip install "lamia-lang[cloud]"
      - run: lamia schedule add daily_task.lm --every day --remote
```

About `LAMIA_CONNECTION_ID`:

- It is created by `lamia cloud connect` and saved as a GitHub **repository variable**.
- It is not a secret API key.
- GitHub does not inject repository variables automatically, so workflow YAML must map it to `env`.

Add values in GitHub UI:

1. Open repository **Settings**.
2. Go to **Secrets and variables > Actions**.
3. In **Variables**, confirm `LAMIA_CONNECTION_ID` exists (created by `lamia cloud connect`).
4. In **Secrets**, add keys like `OPENROUTER_API_KEY`, `THIRD_PARTY_API_KEY`.
5. Reference those names in workflow `env:` (as shown above).

### GitLab CI/CD

Create this file in your repository:

- Path: `.gitlab-ci.yml`

Example pipeline:

```yaml
deploy_lamia:
  image: python:3.12
  script:
    - pip install "lamia-lang[cloud]"
    - lamia schedule add daily_task.lm --every day --remote
```

Add values in GitLab UI:

1. Open project **Settings > CI/CD**.
2. Expand **Variables**.
3. Add keys like `OPENROUTER_API_KEY`, `THIRD_PARTY_API_KEY`.
4. Mark them **Masked** and **Protected** when appropriate.

GitLab injects CI/CD variables into job environment automatically, so no extra `env:` mapping block is required in `.gitlab-ci.yml` unless you want to rename variables.

### Self-hosted Git / Other CI

Lamia does not depend on a specific Git host for secret resolution.  
If your CI runner can execute `lamia ... --remote` and expose environment variables, Lamia will read them and upload only `cloud.secrets` keys.

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
