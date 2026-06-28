# Scheduling Scripts

Lamia supports scheduling `.lm` scripts to run automatically on your local machine using the native OS scheduler (launchd on macOS, systemd timers on Linux, Windows Task Scheduler on Windows).

All scheduled times are **local machine time**.

## Adding a Schedule

The simplest way — use a preset:

```bash
lamia schedule add daily_task.lm --every day
```

Or run it every time you open your computer:

```bash
lamia schedule add daily_task.lm --every on-wake
```

For precise control, use a cron expression:

```bash
lamia schedule add daily_task.lm --cron "0 9 * * *"
```

The command resolves the script path and registers it with the OS scheduler. The script's parent directory becomes the working directory for execution.

### Presets (`--every`)

| Preset | Behavior |
|--------|----------|
| `hour` | Every hour at :00 |
| `day` | Every day at 9:00 AM |
| `weekday` | Monday through Friday at 9:00 AM |
| `week` | Every Monday at 9:00 AM |
| `on-wake` | Once when the computer starts or wakes from sleep |

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--every` | — | Schedule preset (see above). Use this OR `--cron`. |
| `--cron` | — | Standard 5-field cron expression. Use this OR `--every`. |
| `--no-catch-up` | off | If set, missed runs (machine was off) are skipped |

By default, if the machine was off at the scheduled time, the missed run fires once when the machine wakes up. Pass `--no-catch-up` to disable this.

Legacy aliases are still accepted: `hourly`, `daily`, `weekdays`, `weekly`.

## Listing Schedules

```bash
lamia schedule list
```

Shows all registered schedules with their cron, project path, and last run status:

```
  [a3f7c2e1b9d0] daily_task.lm
    schedule: day  catch_up: True
    path: /Users/you/project/pinterest_pin_publisher
    last run: 2026-05-28T09:00:12+00:00  status: ok
```

If a script fails (e.g., file moved, runtime error), the status shows `FAILED` with the error detail.

## Removing a Schedule

```bash
lamia schedule remove <id>
```

The `<id>` is shown in `lamia schedule list` output. This unloads the OS scheduler entry and removes the job from the registry.

## Updating a Schedule

If you used a wrong cron expression or want to change cadence, update in one command:

```bash
lamia schedule update <id> --every day
```

Or switch to a custom cron:

```bash
lamia schedule update <id> --cron "15 10 * * *"
```

You can also toggle catch-up behavior during update:

```bash
lamia schedule update <id> --every on-wake --no-catch-up
```

## How It Works

Schedules are stored globally at `~/.lamia/schedules/` — one JSON file per job (`<id>.json`). Each file holds both the job configuration (script, cron, catch_up, project_root) and the last run status (timestamp, exit code, error). The OS scheduler invokes:

```
lamia --file /abs/path/to/script.lm --log-file ~/.lamia/logs/<id>/schedule.log --schedule-id <id>
```

This means:

- One file per job — no companion status files, everything in `<id>.json`
- Logs are grouped per schedule id under `~/.lamia/logs/schedules/<id>/`
- After each run, exit status is written back into the job file so `lamia schedule list` can display it
- When you `lamia schedule remove <id>`, both the OS entry and the file are deleted

## Cron Expression Reference

```
┌───── minute (0-59)
│ ┌───── hour (0-23)
│ │ ┌───── day of month (1-31)
│ │ │ ┌───── month (1-12)
│ │ │ │ ┌───── day of week (0-7, 0 and 7 = Sunday)
│ │ │ │ │
* * * * *
```

Common patterns:

| Expression | Meaning |
|-----------|---------|
| `0 9 * * *` | Daily at 9:00 AM |
| `0 */6 * * *` | Every 6 hours |
| `30 8 * * 1-5` | Weekdays at 8:30 AM |
| `0 0 1 * *` | First of each month at midnight |

## OS-Specific Behavior

### macOS (launchd)

Creates a plist at `~/Library/LaunchAgents/com.lamia.schedule.<id>.plist`. Uses `StartCalendarInterval` for time-based scheduling. Catch-up of missed runs is handled by Lamia at runtime (comparing last run time to current time).

### Linux (systemd)

Creates a `.service` and `.timer` unit in `~/.config/systemd/user/` named `lamia-schedule-<id>`. Uses `Persistent=true` to catch up on missed runs after boot.

### Windows (Task Scheduler)

Creates a task in `Lamia\<id>` via `schtasks.exe`. The task runs with the user's permissions.

## Best Practices for Scheduled Scripts

Lamia tracks only the **last run** of each scheduled job — its timestamp, exit code, and error message. Previous run information is overwritten. You can access the schedule ID via `schedule.id` in your script to store it in a persistent store.

If you want visibility into run history, keep your own per-run records in a persistent store (file, database, or API) so you can audit trends and troubleshoot faster.

Example — deterministic CSV append (no LLM call):

```python
from datetime import datetime

class RunResult(BaseModel):
    timestamp: str
    job_id: str
    items_processed: int
    success: bool
    error: str

def log_run(job_id, items, success, error="") -> File(CSV[RunResult], "runs/history.csv", append=True):
    return f"{datetime.now().isoformat()},{job_id},{items},{success},{error}"
```

You can also chain file-read mode with deterministic append:

```python
from datetime import datetime

class RunResult(BaseModel):
    timestamp: str
    job_id: str
    items_processed: int
    success: bool
    error: str

job_id = schedule.id # schedule.id is the ID of the scheduled job provided by Lamia
items_processed = 100 # Should be set by your script
success = True # Should be set by your script
error = None # Should be set by your script

def append_history(payload: JSON) -> File(CSV[RunResult], "runs/history.csv", append=True):
    return f"{datetime.now().isoformat()},{job_id},{items_processed},{success},{error:None}"

```

Recommended practices:

1. **Log each run's outcome** — append to CSV rows or write to a database table. Include timestamps, what was processed, and success/failure per item.

2. **Store the run timestamp and exit status** alongside your data. Lamia keeps only the last one, so if you need a history view, maintain your own.

3. **Use idempotent and resumable operations** — catch-up can re-trigger a missed run, and a run can fail halfway. Design steps so retries do not duplicate side effects, and partial failures can resume safely from checkpoints.

4. **Keep scripts self-contained** — the scheduled script runs from its parent directory with no interactive terminal. Avoid prompts, ensure credentials are pre-configured, and handle network failures with retries.

5. **Test manually first** — run `lamia --file your_script.lm` by hand before scheduling. If it works interactively, it will work on schedule.

## Cloud Scheduling

For always-on schedules that don't depend on your local machine being awake, use cloud scheduling with the `--remote` flag:

```bash
lamia daily_task.lm --remote
```

Run this one-time cloud invocation first to verify cloud permissions and runtime behavior.
Then create the schedule:

```bash
lamia schedule add daily_task.lm --every day --remote
```

Cloud jobs are guaranteed to run on time — no catch-up needed, no local machine required. All other commands (`list`, `update`, `remove`) automatically detect whether a job is local or cloud.

Cloud scheduling requires the [`lamia-cloud`](../advanced/lamia-cloud.md) package.  
See the [lamia-cloud user guide](../advanced/lamia-cloud.md) for installation, one-time cloud runs, and scheduler setup.

## Troubleshooting

- **Script not found**: If you moved the project after scheduling, the job will fail. Use `lamia schedule list` to see the stale path, then `remove` and `add` with the new location.
- **Check logs**: Use `lamia schedule list` to get the job id, then inspect `~/.lamia/logs/schedules/<id>/schedule.log`.
- **Force fresh login**: If a web automation script's session expired, delete `.lamia_sessions/` and run the script manually once to re-authenticate before the next scheduled run.
- **Cloud: "requires lamia-cloud"**: Run `pip install "lamia-lang[cloud]"`. See [lamia-cloud docs](../advanced/lamia-cloud.md).
