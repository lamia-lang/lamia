# Scheduling Scripts

Lamia supports scheduling `.lm` scripts to run automatically on your local machine using the native OS scheduler (launchd on macOS, systemd timers on Linux, Windows Task Scheduler on Windows).

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
lamia schedule add daily_task.lm --cron "0 9 * * *" --timezone Europe/Berlin
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
| `--timezone` | `UTC` | IANA timezone (ignored for `on-wake`) |
| `--no-catch-up` | off | If set, missed runs (machine was off) are skipped |

By default, if the machine was off at the scheduled time, the missed run fires once when the machine wakes up. Pass `--no-catch-up` to disable this.

Legacy aliases are still accepted: `hourly`, `daily`, `weekdays`, `weekly`.

## Listing Schedules

```bash
lamia schedule list
```

Shows all registered schedules with their cron, timezone, project path, and last run status:

```
  [a3f7c2e1b9d0] daily_task.lm
    cron: 0 9 * * *  timezone: Europe/Berlin  catch_up: True
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
lamia schedule update <id> --cron "15 10 * * *" --timezone Europe/Berlin
```

You can also toggle catch-up behavior during update:

```bash
lamia schedule update <id> --every on-wake --no-catch-up
```

## How It Works

Schedules are stored globally at `~/.lamia/schedules/` — one JSON file per job. The OS scheduler invokes:

```
lamia --file /abs/path/to/script.lm --log-file ~/.lamia/logs/<script>.log --schedule-id <id>
```

This means:

- Lamia's internal logs go to `~/.lamia/logs/<script>.log`
- Stdout/stderr from the script itself is captured to `.stdout.log` / `.stderr.log` in the same directory
- After each run, exit status is recorded so `lamia schedule list` can display it

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
| `0 9 * * *` | Daily at 9:00 |
| `0 */6 * * *` | Every 6 hours |
| `30 8 * * 1-5` | Weekdays at 8:30 |
| `0 0 1 * *` | First of each month at midnight |

## OS-Specific Behavior

### macOS (launchd)

Creates a plist at `~/Library/LaunchAgents/com.lamia.schedule.<script>.plist`. Uses `StartCalendarInterval` which automatically catches up missed runs.

### Linux (systemd)

Creates a `.service` and `.timer` unit in `~/.config/systemd/user/`. Uses `Persistent=true` to catch up on missed runs after boot.

### Windows (Task Scheduler)

Creates a task in `Lamia\<script>` via `schtasks.exe`. The task runs with the user's permissions.

## Troubleshooting

- **Script not found**: If you moved the project after scheduling, the job will fail. Use `lamia schedule list` to see the stale path, then `remove` and `add` with the new location.
- **Check logs**: All output goes to `~/.lamia/logs/`. Check `<script>.log` for Lamia errors and `<script>.stdout.log` for script output.
- **Force fresh login**: If a web automation script's session expired, delete `.lamia_sessions/` and run the script manually once to re-authenticate before the next scheduled run.
