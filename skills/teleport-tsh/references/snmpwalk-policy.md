# Deferred SNMP Walk Exception Policy

This document defines requirements for a possible future SNMP workflow. The current skill and setup script do not read this policy, construct `snmpwalk` commands, or execute SNMP. Do not treat the example as an authorization or as permission to run SNMP through SSH.

## Example Record

An owner-controlled policy could describe one narrowly scoped exception:

```json
{
  "diagnosticOverrides": [
    {
      "kind": "snmpwalk",
      "teleportProxy": "teleport.example.invalid:443",
      "teleportCluster": "staging.example.invalid",
      "sshNode": "ops-gateway-1",
      "osLogin": "diagnostics",
      "snmpTarget": "router.example.invalid:161",
      "oidSubtree": "1.3.6.1.2.1.1",
      "securityProfile": "approved-read-only-snmpv3-profile",
      "maxDurationSeconds": 15,
      "maxVarbinds": 25,
      "maxOutputBytes": 4096,
      "approvalReference": "NETOPS-1234",
      "expiresAt": "2026-11-15T00:00:00Z"
    }
  ]
}
```

All values are illustrative. Store any real policy in an owner-controlled location separate from the user's `assets/environment.json` preferences. Never store SNMP communities, passwords, keys, or other credentials in policy or chat. `approvalReference` and `expiresAt` are audit metadata, not proof of approval; verify current authorization with the responsible owner and enforce access through the organization's actual controls.

## Required Runtime Checks

A future implementation must:

- Match one exact Teleport proxy, cluster, SSH node, and non-root OS login, plus one distinct exact SNMP target and port. Never interpret a hostname range, subnet, label selector, or wildcard as one target.
- Restrict the walk to the approved numeric OID subtree. Reject an omitted/default root, the entire MIB tree, and caller-supplied shell fragments.
- Use only an approved read-only SNMP security profile, resolved through an organization-approved secret mechanism. Never put secrets in command arguments, generated files, logs, or chat.
- Require a current owner approval for the exact target and OID scope, and fresh user confirmation before every execution. A policy record does not replace either approval.
- Verify the installed client's supported options and construct an argument array, not a shell string. Apply a local deadline and output cap. Enforce `maxVarbinds` with a reviewed wrapper or another proven mechanism; do not assume `snmpwalk` has a total-result limit or claim a limit that is not enforced.
- Capture and report the child exit status, separate stdout/stderr, redact sensitive values, and treat timeout completion as unknown. Do not automatically retry.
- Keep this as a separately authorized workflow. It must not bypass Teleport version checks, RBAC, session verification, clean-terminal requirements, or approval controls.

Until those checks are implemented and tested, stop on SNMP requests and explain that this skill only supports its established SSH workflow.
