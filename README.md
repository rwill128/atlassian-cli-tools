# Atlassian CLI Tools

Small CLI tools for Jira and Confluence.

## Commands

- `tjira`
- `tconf`

## Install

```bash
python3 -m pip install .
```

## Config

The tools read config from either:

1. environment variables
2. `.env` in this repo
3. `~/.config/atlassian-cli/config.json`
4. legacy `~/.config/tillster-atlassian/config.json`

Supported config keys:

- `base_url`
- `email`
- `api_token`
- `jira_cache_root`

`base_url` is required. There is no built-in default Jira site.

Repo `.env` variable names:

- `ATLASSIAN_BASE_URL`
- `ATLASSIAN_EMAIL`
- `ATLASSIAN_API_TOKEN`
- `ATLASSIAN_CLI_CACHE_ROOT`

Legacy repo `.env` variable names still supported:

- `TILLSTER_ATLASSIAN_BASE_URL`
- `TILLSTER_ATLASSIAN_EMAIL`
- `TILLSTER_ATLASSIAN_API_TOKEN`
- `TILLSTER_ATLASSIAN_CACHE_ROOT`

Environment variable overrides:

- `ATLASSIAN_BASE_URL`
- `ATLASSIAN_EMAIL`
- `ATLASSIAN_API_TOKEN`
- `ATLASSIAN_CLI_CACHE_ROOT`
- `ATLASSIAN_CONFIG_PATH`

Legacy environment variable overrides still supported:

- `TILLSTER_ATLASSIAN_BASE_URL`
- `TILLSTER_ATLASSIAN_EMAIL`
- `TILLSTER_ATLASSIAN_API_TOKEN`
- `TILLSTER_ATLASSIAN_CACHE_ROOT`

## Examples

```bash
tjira whoami
tjira create --project POSAAS --summary "Example story" --type Story --description "Example description" --priority Major --assignee current
tjira assigned
tjira assigned --all
tjira pull POSAAS-3412
tjira refresh POSAAS-3412
tjira pull-assigned
tjira attachments POSAAS-3412
tjira comments POSAAS-3412
tjira history POSAAS-3412
tjira projects --limit 5
tjira issue POSAAS-1234
tjira search 'project = POSAAS ORDER BY created DESC' --limit 10

tconf spaces --limit 10
tconf search 'Micros SQL Anywhere' --limit 5
tconf page 99778688 --body
```

## Jira Defaults

`tjira assigned` defaults to active tickets only.

By default it excludes statuses:

- `Released`
- `Passed QA`
- `Closed`
- `Sub-task Closed`

Use `tjira assigned --all` to include the full assigned history.

## Jira Snapshots

`tjira pull ISSUE-KEY` writes a local snapshot under:

```text
~/.local/share/atlassian-cli/jira/ISSUE-KEY/
```

It saves:

- `issue.json`
- `fields.json`
- `summary.md`
- `comments.json`
- `comments.md`
- `changelog.json`
- `history.md`
- `attachments.json`
- `attachments/`

`tjira refresh ISSUE-KEY` overwrites that snapshot with the latest Jira state.

`tjira pull-assigned` pulls the default active assigned set into:

```text
~/.local/share/atlassian-cli/jira/assigned/
```

and also refreshes one folder per issue under `~/.local/share/atlassian-cli/jira/<ISSUE-KEY>/`.

If the legacy Tillster cache root `~/tillster/.jira` already exists, the tools continue using it by default unless `ATLASSIAN_CLI_CACHE_ROOT` or `jira_cache_root` is set.
