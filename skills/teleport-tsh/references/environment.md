# Approved Environment Context

## Setup

1. Ask the infrastructure owner to define the first allowed environment and diagnostic tasks. Start with nonproduction SSH access.
2. Copy the bundled environment template to an organization-approved private location. Provide its path explicitly when invoking the skill. Do not search the user's home directory for configuration or credentials.
3. Populate `environments` only with owner-approved entries. Leave it empty until these decisions are made; an empty list means no configured targets, not unrestricted access.
4. Validate the JSON with a standard JSON parser. Read only the supplied context file, not credential stores. No script consumes this template automatically.
5. Verify the policy against actual Teleport RBAC with the infrastructure owner. A local context file cannot grant permissions or override approval requirements.

## Environment Entry Fields

| Field | Expected value |
| --- | --- |
| `name` | Explicit environment name, such as staging; no implicit default. |
| `proxy` | Approved Teleport proxy hostname and HTTPS port. |
| `cluster` | Exact Teleport cluster name; do not infer it from the proxy. |
| `authConnector` | Organization-approved connector if explicitly configured. Use `null` for the confirmed default login flow; do not invent an SSO connector or change authentication methods. |
| `teleportUser` | Optional Teleport identity if required by the login method; not the OS login. |
| `production` | Boolean environment classification supplied by the owner; never assume missing means false. |
| `allowedOsLogins` | Explicit non-root OS logins permitted for this workflow. |
| `targetNodes` | Exact approved node names; discovery labels alone do not authorize other nodes. |
| `nodeLabels` | Approved discovery label key/value pairs; not permission for multi-node execution. |
| `requireApprovalBeforeEachRemoteCommand` | Set to `true` when each remote command requires fresh user approval; stored test approval is not ongoing authorization. |
| `diagnostics` | Exact approved commands, their purpose, output limits, and timeout in seconds. Avoid arbitrary shell fragments. |
| `dataPolicy` | What may be read, redacted, and included in chat; follow enterprise AI/data handling policy. |

Do not store passwords, MFA codes, bearer tokens, private keys, certificate contents, or credential paths in this template. Hostnames, usernames, and labels can also be sensitive; do not commit private context into a public repository.

If the context is stored inside a workspace, verify its exact path is ignored by Git before use. Git ignore rules prevent ordinary staging, not access by local processes, backups, or forced staging; apply organization-required filesystem protections separately. Keep it outside the distributable skill directory. Historical test results do not establish current authentication, version compatibility, or authorization; revalidate those before each use.

## Operational Decisions

- Confirm whether VS Code terminal commands run on Windows, WSL, a container, or a remote host. The installed client, network access, and Teleport profile must exist in that same execution environment.
- Use Windows PowerShell examples only in PowerShell; do not mix Bash environment-variable or quoting syntax into those commands.
- Agree on output and timeout limits before remote execution. A read-only command still needs bounded execution and approved data access.
- Require explicit approval of production targets and exact diagnostic commands. This foundation does not support mutations, even when requested alongside diagnostics.
- Prefer the user's normal SSO identity and short-lived certificates. Do not use shared admin accounts or create automation credentials as a workaround for interactive authentication.

## First Smoke Test

Have the user authenticate normally. Verify status, list nodes in the approved nonproduction environment, select one exact node, and execute one approved bounded diagnostic such as `uptime`. Record the observed exit status and confirm the result identifies the intended host. Do not claim this smoke test passed until it has actually run.
