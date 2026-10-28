# Connection Setup and Live Discovery

Teleport controls authentication, roles, OS logins, and node access. Do not duplicate those permissions in a local environment inventory or ask users to enumerate nodes manually.

## One-Time Setup

From the repository root, in the prepared Bash/WSL terminal:

```bash
python3 skills/teleport-tsh/scripts/setup_environment.py
```

Setup checks `tsh` and Git, creates or reuses `~/.local/share/teleport-tsh/.venv` in the current Python execution environment, and installs the declared Python requirements into that venv. It does not need system pip. If Python venv support, Git, or `tsh` is missing, it stops with guidance; it never installs system packages, invokes sudo, or replaces `tsh`. On Debian/Ubuntu, venv support may require user installation of `python3-venv` for their Python version.

The skill is copied into the host user's `.copilot/skills/teleport-tsh`. Under WSL, setup resolves the Windows profile using `cmd.exe` and `wslpath`; the venv remains in the Linux execution environment, not the Windows skill package. Use `--skills-dir <path>` for another skills root and `--venv-dir <path>` for another dedicated venv. Paths must use the invoking environment's syntax.

Setup displays the current valid session and asks whether to reuse it. Otherwise it asks for proxy and username, runs interactive login, and verifies the resulting session. The proxy accepts a hostname or HTTPS URL, defaults an omitted port to `443`, and re-prompts invalid input. Passwords and MFA are entered directly into the terminal/browser, never chat.

After compatibility and authentication checks, setup lists visible nodes and labels from `tsh ls`. It performs no SSH, diagnostics, elevation, or remote changes. Skill updates preserve installed private preferences and destination-only files, and exclude source private context, `.venv`, and Python caches.

## Optional Preferences

No configuration file is required. After successful setup, the user may save only proxy and username in the installed skill's `assets/environment.json`, beside the bundled example:

```json
{
  "proxy": "teleport.example.invalid:443",
  "teleportUser": "example.user"
}
```

These are illustrative placeholders, not actual targets. Preferences supply prompt defaults, not authorization or proof of a session. `--output <path>` selects another private destination. Existing files are never overwritten. Legacy files containing `environments` are preserved but ignored; they are not needed for setup. To save new preferences without replacing legacy data, use a different output path.

Do not store roles, node inventories, logins, certificates, keys, passwords, or tokens in this file. Keep private preferences Git-ignored and exclude them when distributing the skill. Apply organization-required filesystem protections separately; Git ignore is not an access-control mechanism.

## Labels and Target Selection

Read nodes and labels live using structured output. Labels organize discovery; they do not grant access or authorize command fan-out.

| Label | Meaning in the supplied workflow |
| --- | --- |
| `grp` | Customer or team grouping |
| `loc` | Hosting location: `nh`/`ma` datacenters, `cus` customer site, or a customer-specific location group |
| `svc` | Hosted service; `sp` denotes SitePortal |
| `use` | Purpose: `prod`, `uat`, `qa`, or `dev` |

Unknown or missing labels are not evidence of nonproduction. Resolve an exact node or node ID and its live cluster before SSH. Ask when a filter matches several nodes; never connect to a label selector as an implicit multi-node operation.

## Least Privilege and Elevation

Use the least-privileged suitable OS login returned by the live session. In the supplied workflow, `c2-support` is basic access, `c2-maintenance` is elevated access with passwordless sudo, and `root` is full access. These conventions do not make a local file authoritative about actual privileges.

A root-only identity is valid. Before every command using an elevated login, sudo, or root, show the exact proxy/cluster, node, login, and command and obtain explicit confirmation. Confirm the syntax of every proposed privileged change before executing it. Do not automatically retry permission failures with a stronger login or submit Access Requests. Task-scoped non-elevated diagnostics do not require a separate local node allowlist.
