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
tjira add-comment POSAAS-3412 --body "Investigation update: ..."
tjira comment POSAAS-3412 --body-file ./jira-comment.md
printf 'Comment from stdin\n' | tjira add-comment POSAAS-3412 --body-file -
tjira edit-comment POSAAS-3412 123456 --body-file ./revised-comment.md
tjira edit-ticket POSAAS-3412 --summary "Updated summary" --priority Major
tjira edit-ticket POSAAS-3412 --field 'customfield_13102={"id":"14200"}' --dry-run
tjira transitions POSAAS-3412
tjira transition POSAAS-3412 "Ready for QA" --dry-run
tjira transition POSAAS-3412 "Ready for QA"
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

`tjira add-comment ISSUE-KEY` posts a comment to an issue. The `comment` alias is equivalent.

Comment bodies use the same plain-text / markdown-ish ADF conversion as issue descriptions. Fenced code blocks are preserved as Jira code blocks, and pipe tables are converted to Jira table nodes.

Successful posts print compact metadata by default. Use `--json` only when the raw Jira response body is needed.

For example:

```bash
tjira add-comment POSAAS-3412 --body "Ready for QA."
tjira comment POSAAS-3412 --body-file ./comment.md
```

`tjira edit-comment ISSUE-KEY COMMENT-ID` replaces an existing comment body. The `update-comment` alias is equivalent. It supports the same `--body`, `--body-file`, `--dry-run`, and `--json` options as `add-comment`.

For example:

```bash
tjira edit-comment POSAAS-3412 123456 --body-file ./revised-comment.md
```

`tjira edit-ticket ISSUE-KEY` updates issue fields. The `update-ticket`, `edit-issue`, and `update-issue` aliases are equivalent. Use `--dry-run` before posting when editing custom fields.

Supported common fields:

- `--summary`
- `--description` / `--description-file`
- `--assignee` with accountId, email address, `current`, or `unassigned`
- `--priority`

Raw Jira fields are available for custom fields:

- `--field KEY=VALUE`, where `VALUE` is parsed as JSON when valid, otherwise as a string
- `--fields-json '{"customfield_13102":{"id":"14200"}}'`
- `--fields-file ./fields.json`

For example:

```bash
tjira edit-ticket POSAAS-3412 --summary "Updated title" --dry-run
tjira edit-ticket POSAAS-3412 --field 'customfield_13102={"id":"14200"}' --dry-run
```

`tjira transitions ISSUE-KEY` lists the transitions Jira currently allows from the issue's status.

`tjira transition ISSUE-KEY TARGET` moves an issue using either the transition id, transition name, or target status name. Use `--dry-run` to confirm the selected transition before posting.

For example:

```bash
tjira transitions POSAAS-3412
tjira transition POSAAS-3412 "Ready for QA" --dry-run
tjira transition POSAAS-3412 "Ready for QA"
```

`tjira create` applies POSAAS-specific defaults when `--project POSAAS` is used:

- `Issue Type` defaults to `Defect`
- `--type "Improve Defect"` and `--type Bug` are normalized to Jira issue type `Defect`
- `Priority` defaults to `Major`
- `HR Type` defaults to `POS (internal)`
- `Original Estimate` defaults to `1d`

For example:

```bash
tjira create --project POSAAS --summary "Example production defect" --assignee current
```

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
