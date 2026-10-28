# tsh CLI Recipes

These are illustrative command forms, not approved infrastructure targets. Replace example values only with supplied, verified organization context. Consult installed command help before using version-dependent flags. Require an exact match to the proxy's current server version rather than pinning an example release.

## Contents

- [Required clean Bash terminal](#required-clean-bash-terminal)
- [Local preflight](#local-preflight)
- [Required proxy version gate](#required-proxy-version-gate)
- [User-completed login](#user-completed-login)
- [Discovery](#discovery)
- [One-shot SSH diagnostic](#one-shot-ssh-diagnostic)
- [Deferred resource workflows](#deferred-resource-workflows)
- [Official references](#official-references)

## Required Clean Bash Terminal

For Bash/WSL execution, use a dedicated clean interactive session before running infrastructure commands:

```bash
bash --noprofile --norc -i
```

Launch this once in a persistent interactive terminal, not as a synchronous one-shot that waits for the shell to exit. Confirm its normal prompt and preserve the terminal/session identity for every subsequent command; do not silently return to the parent shell. If another command is running or Bash shows a continuation prompt, stop and ask the user to cancel the identified incomplete input first. Do not submit a command into that input.

Before loading VS Code integration, submit these local checks separately as single-line commands:

```bash
printf 'CLEAN_BASH_READY\n'
declare -p PROMPT_COMMAND
trap -p DEBUG
```

An unset `PROMPT_COMMAND` and no DEBUG trap are expected before integration. Report unexpected hooks rather than disabling them automatically. Startup files are skipped, not edited; environment variables and exported functions may still be inherited. Preserve approved connectivity settings and do not claim this is a sanitized environment.

In VS Code, locate the local integration script and inspect its guard variable:

```bash
code --locate-shell-integration-path bash
declare -p VSCODE_SHELL_INTEGRATION
```

Unset variables may cause `declare -p` to return nonzero; that alone is not a setup failure. Verify the returned script path is an exact readable local file before sourcing it directly in this same shell. Inspect the script's initialization guard; if an inherited value prevents initialization, report it and obtain approval before changing it. Do not copy a version-specific path from documentation. For a verified path assigned to `integration_path`, source it with:

```bash
source "$integration_path"
```

Do not source user startup files or alter persistent shell configuration. If `code` or the script is unavailable, stop and request a prepared terminal rather than installing software. After integration loads, test only local execution:

```bash
sh -c 'printf "LOCAL_STDOUT_OK\n"; printf "LOCAL_STDERR_OK\n" >&2; exit 7'
```

Require both markers and observed child exit status 7, not just an echoed invocation. A tool-reported exit code 7 is expected evidence, not a failed test. Use read-only command detection if available; a tracker that reports a prompt hook instead of the test is unreliable. Do not run infrastructure commands until this dedicated terminal's local execution and completion handling are verified. No local setup or previous test grants approval for a remote command.

Submit short, single-line synchronous checks once the shell is ready. Code blocks below illustrate syntax; do not paste entire multiline examples into a terminal with unreliable submission handling. Use a reviewed script if necessary, with approval for its creation, rather than repeatedly submitting uncertain blocks.

## Local Preflight

PowerShell:

```powershell
Get-Command tsh -CommandType Application -ErrorAction Stop
tsh version
```

Bash:

```bash
command -v tsh
tsh version
```

Check each command's result before continuing. These commands do not install software or authenticate. Read the local client version, not just the proxy version that `tsh version` may also display. Complete the following gate before running `tsh status`, login, or resource discovery.

## Required Proxy Version Gate

Use the approved proxy hostname and HTTPS port, without a scheme or path, as `TELEPORT_PROXY`. Do not infer this value from an unrelated active profile. Query both fields in one response to avoid comparing metadata from separate requests during an upgrade.

Bash/WSL, requiring `curl` and `jq`:

```bash
proxy_metadata=$(curl --fail --silent --show-error --connect-timeout 5 --max-time 15 "https://${TELEPORT_PROXY:?Set the approved proxy hostname and port}/webapi/find") &&
  printf '%s\n' "$proxy_metadata" | jq -e '
    {server_version, min_client_version} |
    select((.server_version | type == "string") and (.min_client_version | type == "string")) |
    select((.server_version | length > 0) and (.min_client_version | length > 0))'
```

PowerShell, using the supplied `$TeleportProxy` hostname and port:

```powershell
if ([string]::IsNullOrWhiteSpace($TeleportProxy)) { throw 'Set the approved proxy hostname and port.' }
$proxyMetadata = Invoke-RestMethod -Uri "https://$TeleportProxy/webapi/find" -TimeoutSec 15 -ErrorAction Stop
if ($proxyMetadata.server_version -isnot [string] -or
    $proxyMetadata.min_client_version -isnot [string] -or
    [string]::IsNullOrWhiteSpace($proxyMetadata.server_version) -or
    [string]::IsNullOrWhiteSpace($proxyMetadata.min_client_version)) {
    throw 'Proxy version metadata is missing or invalid.'
}
$proxyMetadata | Select-Object server_version, min_client_version
```

These recipes retrieve and check the presence/type of metadata; they do not implement version comparison. Check successful completion, validate all three version values, then compare the installed client against both fields. Normalize only an optional leading `v`. Require exact equality with `server_version` and semantic version ordering at or above `min_client_version`; never compare versions lexicographically or strip patch/prerelease differences. Use an available proven semantic-version parser for automation. If a value cannot be interpreted reliably, stop rather than guessing. Treat a minimum higher than the server version as inconsistent metadata and stop.

A client above the minimum but different from the server still fails this organization's exact-match requirement. A failed HTTP request, TLS error, invalid JSON, or missing field must stop the workflow; do not fall back to cached version output or disable certificate validation. Report local, server, and minimum versions and the gate result. Do not install or downgrade automatically. Retrieve current metadata again after an approved client update or proxy change.

Once the gate passes, run `tsh status`. Use `tsh status --format=json` only after confirming support in `tsh status --help`; parse the result using `ConvertFrom-Json` or another standard JSON parser. Do not assume a JSON schema across client versions.

## User-Completed Login

```text
tsh login --proxy=teleport.example.com:443 --auth=approved-sso
tsh status
```

The user must complete browser SSO and MFA. Use `--browser=none` only when the user needs to open the login link manually; it does not bypass authentication. Keep authentication links out of persistent logs. Never collect passwords or MFA codes through chat, and never approve an MFA prompt on the user's behalf.

## Discovery

```text
tsh ls --proxy=teleport.example.com:443 --cluster=staging env=staging
```

Positional arguments to `tsh ls` are label expressions such as `env=staging`, not node names. Do not pass a bare hostname there. For an exact node name, confirm predicate support with installed command help and use:

```text
tsh ls --proxy=teleport.example.com:443 --cluster=staging --query='name == "staging-api-1"'
```

Use the returned node name for later target selection; discovery does not authorize SSH. Keep externally supplied values out of executable expressions unless properly validated and escaped for both the shell and predicate language.

Confirm available formatting options with `tsh ls --help` before requesting structured output. Discover within the approved environment and select an exact node. Discovery visibility reflects the user's roles; missing nodes are not permission to connect directly by guessed addresses.

## One-Shot SSH Diagnostic

```text
tsh ssh --proxy=teleport.example.com:443 --cluster=staging diagnostics@staging-api-1 uptime
```

Use only a verified allowed OS login and exact node. The OS login (`diagnostics` here) is distinct from the Teleport identity used during login. Confirm timeout support in the execution tool and apply an agreed deadline before execution; do not assume a client timeout flag exists.

For GNU `timeout` around a terminal-accessing `tsh` in Bash/WSL, confirm `--foreground` support with `timeout --help` and use it, particularly in a subshell wrapper. For example, this is a 15-second deadline with an additional 2-second forced-kill grace, not a strict 15-second wall-clock cap:

```bash
timeout --foreground --signal=TERM --kill-after=2s 15s tsh ssh --proxy=teleport.example.com:443 --cluster=staging diagnostics@staging-api-1 uptime
```

Default GNU timeout grouping can place `tsh` outside the terminal foreground group. Terminal access can then stop the job, including the timeout process, so the deadline and Ctrl+C may not behave as expected. Foreground mode preserves terminal access, but does not time out descendants of the command. Neither mode guarantees that remote processes terminate. If foreground mode is unavailable, stop or use a verified compatible execution-tool deadline; do not silently fall back to the known problematic wrapper.

Keep stdout and stderr separate so a warning cannot replace the retained uptime line. Bound displayed output for each stream. If approved temporary capture files are used, distinguish display limits from storage limits, isolate cleanup in the wrapper's subshell, and verify cleanup. Capture the child status before any output handling and report it explicitly; a wrapper whose last command is a successful `printf` can exit 0 despite SSH failure. Do not redirect interactive authentication prompts into hidden capture files; stop and hand required authentication to the user in terminal/browser.

On PowerShell, capture `$LASTEXITCODE` immediately after `tsh` finishes; on Bash, capture `$?`. A nonzero result must be reported, not discarded by a later successful command. If the tool times out, report unknown completion and investigate before retrying. Do not claim a timeout necessarily stopped a remote process.

If the deadline passes without results, use separately authorized local process inspection to distinguish actively running, stopped (`T` state), and exited processes. Compare PID, process group, and terminal foreground group. A stopped background `tsh`/timeout pair is consistent with terminal-access job control; the exact stopping signal is not established by state alone. Do not automatically run `fg`, `bg`, or send `SIGCONT`, since they can resume SSH. Obtain approval before cancelling only the reverified test processes, never broad process-name kills. Status 137 after an explicit SIGKILL is cancellation, not SSH success or proof that the timeout worked. Require fresh approval before a corrected remote attempt.

Do not concatenate untrusted labels or output into a command string. Use argument-safe tool/process APIs. Restrict command output at the source where practical and do not forward raw sensitive logs into chat. Do not execute any example merely because it appears in this reference.

## Deferred Resource Workflows

`tsh apps ls`, `tsh db ls`, and `tsh kube ls` can discover other resource types, but require installed-version help and explicit task scope. Do not infer approval to connect or mutate from resource visibility. This foundation does not implement these connection workflows.

In particular, `tsh kube login` changes kubeconfig, and `tsh kubectl` can submit Access Requests after permission failures. Do not invoke either as an SSH fallback. Database clients, application proxies, Git configuration, certificate export, session playback, and file transfer likewise require their own approved procedures.

## Official References

- [Using tsh](https://goteleport.com/docs/connect-your-client/teleport-clients/tsh/)
- [tsh CLI reference](https://goteleport.com/docs/reference/cli/tsh/)
- [Role-based access controls](https://goteleport.com/docs/reference/access-controls/roles/)
- [Machine & Workload Identity](https://goteleport.com/docs/machine-workload-identity/)

This reference distills the relevant connection workflow rather than reproducing the upstream manual. Keep the original instruction document in the repository as a separate source; the installed skill must not depend on files outside its package.
