# tsh CLI Recipes

These are illustrative command forms, not approved infrastructure targets. Replace example values only with supplied, verified organization context. Consult installed command help before using version-dependent flags. Match the client major version to the cluster recommendation rather than pinning an example release.

## Local Preflight

PowerShell:

```powershell
Get-Command tsh -CommandType Application -ErrorAction Stop
tsh version
tsh status
```

Bash:

```bash
command -v tsh
tsh version
tsh status
```

Check each command's result before continuing. These commands do not install software or authenticate. Use `tsh status --format=json` only after confirming support in `tsh status --help`; parse the result using `ConvertFrom-Json` or another standard JSON parser. Do not assume a JSON schema across client versions.

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

Confirm available formatting options with `tsh ls --help` before requesting structured output. Discover within the approved environment and select an exact node. Discovery visibility reflects the user's roles; missing nodes are not permission to connect directly by guessed addresses.

## One-Shot SSH Diagnostic

```text
tsh ssh --proxy=teleport.example.com:443 --cluster=staging diagnostics@staging-api-1 uptime
```

Use only a verified allowed OS login and exact node. The OS login (`diagnostics` here) is distinct from the Teleport identity used during login. Confirm timeout support in the execution tool and apply an agreed deadline before execution; do not assume a client timeout flag exists.

On PowerShell, capture `$LASTEXITCODE` immediately after `tsh` finishes; on Bash, capture `$?`. A nonzero result must be reported, not discarded by a later successful command. If the tool times out, report unknown completion and investigate before retrying. Do not claim a timeout necessarily stopped a remote process.

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
