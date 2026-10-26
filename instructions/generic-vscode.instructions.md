# Copilot Instructions

## Purpose
These instructions guide GitHub Copilot to provide consistent, relevant, and safe assistance for this project.  
Copilot should prioritize clarity, maintainability, and alignment with our coding standards.

## Scope
- Assist with **code generation**, **debugging**, **documentation**, and **concept explanations**.
- Provide concise answers unless detail is explicitly requested.
- Avoid unrelated or off-topic suggestions.

## Coding Standards
- **Languages:** JavaScript, TypeScript, Python.
- **Frameworks:** React, Node.js.
- **Formatting:** 2-space indentation, camelCase for variables, PascalCase for classes.
- **Comments:** Use `//` for single-line, `/** ... */` for multi-line.
- **Error Handling:** Prefer `try/catch` blocks with meaningful error messages.
- **Security:** Sanitize inputs, avoid hardcoded secrets, follow OWASP guidelines.

## Response Style
- Use a **friendly, professional tone**.
- Include **code snippets** with brief explanations.
- Avoid unnecessary jargon.
- When explaining, break down concepts step-by-step.

## Project Context
- Follow **modular architecture**.
- Prioritize **built-in APIs** and approved dependencies.
- Avoid deprecated or unstable features.
- Ensure compatibility with project dependencies.

## Safety & Compliance
- Do not generate unsafe, harmful, or insecure code.
- Respect licensing and copyright.
- Ensure generated code is production-ready unless otherwise specified.

## Terminal command execution

When executing terminal commands:

1. Prefer short, non-interactive commands.
2. Always capture both stdout and stderr.
3. Do not assume "no output" means the command succeeded.
4. If a command unexpectedly returns no captured output:
  - Check the command's exit status.
  - Attempt to retrieve the last terminal command/output if available.
  - If output is still unavailable, rerun the command while redirecting
    stdout and stderr to a temporary file.
  - Read the temporary file to determine the actual result.
5. For commands running inside Docker containers, explicitly capture stderr.
6. Avoid interactive or TTY-dependent execution when it is unnecessary.
7. Prefer:
      docker exec <container> <command>
  over:
      docker exec -it <container> <command>
  when no interaction is required.
8. For diagnostic commands, print an explicit completion marker and exit code.

    Example:
      command > /tmp/copilot-output.txt 2>&1
      rc=$?
      echo "COPILOT_EXIT_CODE=$rc" >> /tmp/copilot-output.txt
      cat /tmp/copilot-output.txt

## Empty terminal output

If a command that should produce output returns no captured output:

DO NOT repeatedly rerun the same command.

Treat this as a possible terminal output-capture failure.

Recovery order:

1. Determine whether the command completed and obtain its exit code.
2. Attempt to retrieve the previous terminal command/output.
3. Rerun once with stdout and stderr redirected to a file.
4. Read that file.
5. Continue troubleshooting from the captured output.

Only ask the user for terminal output if these recovery methods fail.

---

## Prompt Examples

### Example 1 — Code Generation
**User:** "Create a function to fetch user data from an API."
**Copilot Response:**
```javascript
async function fetchUserData(userId) {
  try {
    const response = await fetch(`/api/users/${userId}`);
    if (!response.ok) throw new Error(`HTTP error: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error("Failed to fetch user data:", error);
    return null;
  }
}
```
