# tsh CLI Recipes

These are illustrative command forms, not approved infrastructure targets. Replace example values only with supplied, verified organization context. Consult installed command help when initializing the cache or after a client-version change before using version-dependent flags. Use Teleport RBAC rather than a local permission inventory.

## Contents

- [Use the current terminal](#use-the-current-terminal)
- [Conditional Bash recovery](#conditional-bash-recovery)
- [Local preflight](#local-preflight)
- [Required proxy version gate](#required-proxy-version-gate)
- [User-completed login](#user-completed-login)
- [Discovery](#discovery)
- [One-shot SSH diagnostic](#one-shot-ssh-diagnostic)
- [Deferred resource workflows](#deferred-resource-workflows)
- [Official references](#official-references)

## Use the Current Terminal

For read-only node inventory or a task-scoped SSH diagnostic, reuse the current terminal and a valid conversation-local session cache. Do not open a shell, run setup, or discover VS Code shell integration just because execution is in WSL. On cache initialization, check status, compatibility, and structured node discovery once; seed the cache from setup output when available. On subsequent tasks, reuse the same proxy, user, cluster, expiry, verified client capabilities, and timestamped node snapshot without repeating those commands. Parse cached inventory and stop for inventory-only requests; listing visible nodes does not connect to them or authorize a later remote command.

```bash
tsh status --format=json
tsh version --client --format=json
tsh ls --proxy=teleport.example.com:443 --cluster=staging --format=json
```

Use the exact flags supported by installed help. If the active context is missing or differs from the requested one, ask the user before login or switching clusters. Do not perform SSH for an inventory-only request.

## Conditional Bash Recovery

Use recovery only when there is concrete evidence that the current terminal is unreliable, such as a continuation prompt, interfering hooks, or missing completion/exit-status evidence. Stop submitting input to an incomplete command. If the terminal tool can preserve a separate session, start one persistent interactive shell:

```bash
bash --noprofile --norc -i
```

Check the prompt and hooks, then test local output and exit-status capture:

```bash
printf 'CLEAN_BASH_READY\n'
declare -p PROMPT_COMMAND
trap -p DEBUG
sh -c 'printf "LOCAL_STDOUT_OK\n"; printf "LOCAL_STDERR_OK\n" >&2; exit 7'
```

An unset `PROMPT_COMMAND` and no DEBUG trap are expected. Do not disable hooks or change profiles/settings automatically. Require both output markers and observed child status 7, not just an echoed command. Do not run `code --locate-shell-integration-path`, source VS Code shell integration, or install/update a VS Code Server for Teleport command tracking. If execution evidence remains unreliable, stop and ask the user to prepare a terminal. Local shell checks do not authorize remote commands.

## Local Preflight

PowerShell:

```powershell
Get-Command tsh -CommandType Application -ErrorAction Stop
tsh version --client --format=json
```

Bash:

```bash
command -v tsh
tsh version --client --format=json
```

Check each command's result before continuing during cache initialization. These commands do not install software, contact a proxy, or authenticate. Inspect `tsh status --format=json` once to identify a reusable session, then confirm the intended proxy/user/cluster and complete the compatibility gate before discovery. Reuse these facts for subsequent tasks in the same conversation until invalidation. Status may retrieve alerts from the existing profile's proxy; do not describe it as an offline guarantee.

## Required Proxy Version Gate

Use the approved proxy hostname and HTTPS port, without a scheme or path, as `TELEPORT_PROXY`. Do not infer this value from an unrelated active profile. Query both fields in one response during cache initialization or invalidation, not for each task, to avoid comparing metadata from separate requests during an upgrade.

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

These recipes retrieve and check the presence/type of metadata; they do not implement version comparison. Validate all three versions using a proven semantic-version parser. The client must be at or above `min_client_version` and have the same major version as the proxy or be one major behind. Normalize only an optional leading `v`; never compare lexicographically or discard prerelease information. Exact patch equality is not required. Invalid values or a minimum higher than the server version are blockers.

Follow the [official component compatibility rules](https://goteleport.com/docs/upgrading/overview/). A newer-major client or a client more than one major behind is unsupported. HTTP/TLS failures, invalid JSON, and missing metadata remain blockers; never disable certificate or compatibility checks. Report local, server, and minimum versions and the result. Do not install or downgrade tsh automatically. Recheck after a new login session, proxy/client changes, or cache invalidation. The specific advisory `A security patch is available for Teleport. Please upgrade your Cluster to v15.5.4 or newer.` is nonblocking for this workflow, but never changes a failed command's exit status or suppresses other warnings.

Use `tsh status --format=json` only after confirming support in installed help. Read the `active` profile, not an arbitrary entry in `profiles`; verify its `profile_url`, `username`, `cluster`, `valid_until`, and `logins`. Run it to initialize or revalidate a cache, not for each task. Expired or missing sessions require user-completed login. Parse JSON structurally and do not assume schemas across versions.

## User-Completed Login

```text
tsh login --proxy=teleport.example.com:443 --user=example.user --request-roles=no
tsh status
```

Setup uses an explicit Teleport username and the proxy's configured authentication flow; it does not ask users to define SSO connectors manually. `--request-roles=no` disables automatic role requests in the verified client. For SSO, identity is established by the browser flow; verify the resulting status rather than silently accepting a different user.

Cluster selection is command-specific. In tsh 15.4.6, login takes a positional cluster, while status reports the active profile and has no `--cluster` flag. Normal setup uses the cluster established by login, not a cluster questionnaire. A later task targeting another cluster must verify/switch that context explicitly. Do not copy discovery or SSH `--cluster` flags onto login or status.

The user must complete browser SSO and MFA. Use `--browser=none` only when the user needs to open the login link manually; it does not bypass authentication. Keep authentication links out of persistent logs. Never collect passwords or MFA codes through chat, and never approve an MFA prompt on the user's behalf.

## Discovery

```text
tsh ls --proxy=teleport.example.com:443 --cluster=staging use=qa
```

Positional arguments to `tsh ls` are label expressions such as `use=qa`, not node names. `grp`, `loc`, `svc`, and `use` are grouping/filtering labels, not locally maintained permissions. Do not pass a bare hostname there. For an exact node name, confirm predicate support with installed command help and use:

```text
tsh ls --proxy=teleport.example.com:443 --cluster=staging --query='name == "staging-api-1"'
```

During cache initialization, retain returned node names, IDs, labels, and the discovery timestamp in the current conversation. Reuse this snapshot for later tasks rather than repeating a full listing. If a target is missing or ambiguous in the cache, use the exact query above or ask for clarification; never guess. Teleport enforces SSH access; a listing does not specify the user's intended task or authorize elevated commands or arbitrary changes. Keep discovered values out of executable expressions unless validated and escaped for both shell and predicate syntax.

Confirm available formatting options with `tsh ls --help` during cache initialization for the current client version. Discover within the approved environment and select an exact node. Discovery visibility reflects the user's roles; missing nodes are not permission to connect directly by guessed addresses. For inventory responses from cache, state when the snapshot was collected.

## One-Shot SSH Diagnostic

```text
tsh ssh --proxy=teleport.example.com:443 --cluster=staging --request-mode=off diagnostics@staging-api-1 uptime
```

Use only a verified allowed OS login and exact node. The OS login (`diagnostics` here) is distinct from the Teleport identity used during login. Confirm timeout support in the execution tool and apply an agreed deadline before execution; do not assume a client timeout flag exists.

Verify `--request-mode=off` support during cache initialization for the current client version and use it to prevent automatic Access Requests. Reuse that capability check until the client changes. Prefer a basic login such as `c2-support` when appropriate. For every command using `c2-maintenance`, sudo, or root, show the exact target/login/command, confirm syntax, and obtain approval before execution. Root-only identities are supported after confirmation; do not automatically escalate on access denial. Explicitly requested changes require their own scope and confirmation rather than being inferred from a diagnostic request.

For GNU `timeout` around a terminal-accessing `tsh` in Bash/WSL, confirm `--foreground` support with `timeout --help` during cache initialization for that terminal environment and reuse the result until the environment changes. Use it, particularly in a subshell wrapper. For example, this is a 15-second deadline with an additional 2-second forced-kill grace, not a strict 15-second wall-clock cap:

```bash
timeout --foreground --signal=TERM --kill-after=2s 15s tsh ssh --proxy=teleport.example.com:443 --cluster=staging --request-mode=off diagnostics@staging-api-1 uptime
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
