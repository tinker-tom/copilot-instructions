# 🚀 Copilot Instructions Repository

Welcome to the **Copilot Instructions** repository!  
This project provides a set of best practices, coding rules, and prompt instructions to guide AI-assisted development, especially with GitHub Copilot and similar tools.

## 📚 What does this repository do?

- Defines clear coding standards and architectural rules (e.g., Domain-Driven Design, testing strategies).
- Provides prompt and instruction files for consistent, high-quality code generation.
- Helps teams and AI tools follow the same guidelines for maintainable, robust, and expressive code.

## 🛠️ How to use this repository

1. **Clone the repository**  
   Open your terminal and run:
   ```sh
   git clone https://github.com/your-username/copilot-instructions.git
   ```
2. **Explore the repository**
   - Check `instructions/` for coding rules and best practices
   - Review `skills/` for specialized capabilities and bundled resources
   - Browse `agents/` for custom AI personas
   - Install plugins from `plugins/` for curated collections
   - Visit `website/` for interactive documentation
3. **Apply the rules**  
   - Follow the documented standards in your projects.
   - Use these files to configure Copilot or other AI tools for consistent code generation.


## ✨ Features

- 🏛️ Domain-Driven Design (DDD) guidelines ([see instructions](instructions/domain-driven-design.instructions.md))
- 📐 Specification pattern for business rules ([see instructions](instructions/specification-business-rules-csharp.instructions.md))
- 🧪 Unit & Integration testing best practices ([see instructions](instructions/unit-and-integration-tests.instructions.md))
- 🗂️ Command/Query (CQRS) best practices ([see command instructions](instructions/command-cqrs-csharp.instructions.md))
- 📝 English-only documentation policy
- 🤖 Copilot and AI prompt instructions
- 🔄 TDD-first workflow for C# (see `copilot-instructions.md`)
- ❓ Follow-up Question Enforcement ([see instructions](instructions/follow-up-question.instructions.md))  
   AI must ask clarifying questions and show confidence before code generation.
- 🌐 **Microsoft MCP server integration**: this repository integrates the official Microsoft MCP server to provide real-time access to Microsoft documentation and enhance AI-generated responses ([learn more](https://github.com/MicrosoftDocs/mcp)).
- 🐶 Husky setup prompts for .NET projects (see `prompts/huskydotnet.prompt.md`)
- 🤡 Microcks metadata instructions for API Mock and contract testing:
   - [GroovyScript metadata rules](instructions/microcks-metadata-groovyscript.instructions.md)
   - [JSON body metadata rules](instructions/microcks-metadata-jsonbody.instructions.md)
- ⚙️ **SKRAFT plugin**: deterministic agentic SDLC pipeline (DISCOVER → DISCUSS → DESIGN → DISTILL → DELIVER) with specialized agents, adversarial reviewers, discipline skills (Outside-In TDD, Clean Architecture) and mechanical guardrails, compatible with Claude Code, GitHub Copilot and Cursor ([see repository](https://github.com/SebastienDegodez/skraft-plugin) · [documentation](https://sebastiendegodez.github.io/skraft-plugin/fr/))

> [![Watch the video](https://img.youtube.com/vi/QIoorNhYm3s/maxresdefault.jpg)](https://youtu.be/QIoorNhYm3s)

## 🎯 Repository Approach

This repository follows the [awesome-copilot](https://github.com/github/awesome-copilot) structure and conventions for organizing instructions, skills, agents, and plugins to enhance GitHub Copilot capabilities.

### Key Concepts

- **Instructions**: Coding standards and best practices that apply to specific file patterns
- **Skills**: Self-contained capabilities that bundle SKILL.md files with related resources
- **Agents**: Custom AI personas for specialized workflows
- **Plugins**: Installable packages that bundle related skills and agents

## 📂 Repository Structure

```
├── instructions/          # Coding standards and best practices (.instructions.md)
├── agents/               # Custom AI agents (.agent.md)
├── skills/               # Self-contained capabilities with bundled resources
├── plugins/              # Installable packages bundling related agents and skills
│   └── csharp-clean-architecture-development/
├── website/              # Astro static documentation site
├── docs/                 # Documentation and implementation plans
├── .github/
│   └── workflows/        # GitHub Actions for deployment and automation
└── README.md
```

## 🔌 Plugins

### C# Clean Architecture Development

Comprehensive plugin for C# developers with DDD, Clean Architecture, CQRS, and testing best practices.

- **Location**: `plugins/csharp-clean-architecture-development/`
- **Skills**: application-layer-testing, clean-architecture-dotnet
- **Installation**: See plugin README for details

See [plugins/](plugins/) for more available plugins.

### SKRAFT

Deterministic agentic SDLC pipeline that turns a coding assistant into a disciplined software production line. Orchestrates 5 lifecycle phases (DISCOVER → DISCUSS → DESIGN → DISTILL → DELIVER), each driven by a specialized agent and an adversarial reviewer, locked by mechanical guardrails (G1–G8).

- **Repository**: [SebastienDegodez/skraft-plugin](https://github.com/SebastienDegodez/skraft-plugin)
- **Documentation**: [sebastiendegodez.github.io/skraft-plugin/fr/](https://sebastiendegodez.github.io/skraft-plugin/fr/)
- **Supported harnesses**: Claude Code, GitHub Copilot, Cursor
- **Key features**:
  - 🔁 5-phase SDLC pipeline orchestrated by `skraft-orchestrator`
  - 🤖 Specialized phase agents: `backlog-discoverer`, `backlog-planner`, `solution-architect`, `acceptance-designer`, `software-engineer` — each with a dedicated adversarial reviewer
  - 🛡️ Mechanical guardrails G1–G8 (fail-closed hooks): dispatch ordering, forced skill loading, artifact/verdict/commit verification
  - 📚 Discipline skills: Outside-In TDD, Clean Architecture, BDD/Gherkin, mutation testing, contract testing, ADR
  - 💸 Token economy with model routing by cost class

**Installation (Claude Code):**
```bash
/plugin marketplace add SebastienDegodez/skraft-plugin
/plugin install skraft
```

**Quick start:**
```
/skraft
```

## 📦 What is a collection?

A **collection** is a YAML file (in `collections/`) that groups related instructions, prompts, and chatmodes into a reusable package. Collections are designed to be consumed by **APM (Agent Package Manager)** to provide "primitives" for AI agents.

### Using collections with APM

[APM](https://github.com/danielmeppiel/apm) allows you to easily install and manage these collections in your projects. Instead of manually copying instruction files, you can use APM to:

- Install a curated set of instructions for a specific technology stack
- Keep your AI primitives up-to-date across multiple projects
- Share best practices with your team

![APM Demo](https://github.com/danielmeppiel/apm/raw/main/docs/apm-demo.gif)

## 🧑‍💼 What is a chatmode? 

A **chatmode** is a configuration file (in `chatmodes/`) that defines how Copilot or another AI assistant should behave in a specific context or workflow. For example, the `architect` chatmode makes the AI act as an experienced architect and technical lead, focusing on planning, documentation, and Markdown-only outputs. Chatmodes can set the tone, priorities, and constraints for the AI during a session or project.

A **meta-chatmode** is a special chatmode file (e.g., `meta-chatmode.instructions.md`) that defines how to write, structure, and validate other chatmode files. Meta-chatmodes ensure that all chatmodes follow a consistent format and best practices across the repository. They specify the required file structure, naming conventions, expected behavior, and validation checklist for chatmode files. 


## 📏 What is an instruction?

An **instruction** is a Markdown file (in `instructions/`) that defines coding rules, architectural standards, and best practices for the project. Instructions are always active and must be followed for all code and documentation generated in the repository. They ensure consistency, maintainability, and alignment with the project's technical vision (e.g., DDD, specification pattern, testing, commit conventions).

A **meta-instruction** is a special instruction file (e.g., `meta-instructions.instructions.md`) that defines how to write, structure, and validate other instruction files. Meta-instructions ensure that all instructions follow a consistent format and best practices across the repository.

## 💡 What is a prompt?

A **prompt** is a template or guidance file (in `prompts/`) used to help Copilot or another AI tool generate code or documentation in a specific style or for a particular use case. Prompts are reusable and can steer the AI in a particular direction for a given task, such as enforcing TDD, writing API documentation, or generating test cases.

## 🎯 What is a skill?

A **skill** is a modular, self-contained package (in `skills/`) that extends GitHub Copilot's capabilities with specialized knowledge, workflows, and tools. Skills act as "onboarding guides" for specific domains or tasks, transforming Copilot into a specialized agent.

### Available Skills

- **clean-architecture-dotnet**: Complete guide for Clean Architecture with DDD and CQRS (no MediatR), including project initialization scripts and ArchUnit validation
- **application-layer-testing**: Testing Application layer handlers with sociable testing strategy (real Domain objects, mocked Infrastructure)
- **skill-creator**: Create and manage GitHub Copilot skills

### Maintaining Personal Skill Installations

Repository skills are the source of truth, but copied personal installations do not update automatically. Use [tools/sync_skills.py](tools/sync_skills.py) to preview or explicitly apply updates for any current or future top-level skill. It reuses the repository's skill validator and requires Python 3.10+ and PyYAML, also used by the existing skill-authoring tools.

Preview one skill, then apply the same plan to your current user's personal skills directory:

```bash
python tools/sync_skills.py --skill teleport-tsh
python tools/sync_skills.py --skill teleport-tsh --apply
```

The default destination is `~/.copilot/skills` for the Python process's operating system. Windows Python uses the Windows home; WSL Python uses the Linux home. Repeat `--destination` to manage both explicitly from WSL, replacing `WINDOWS_USER` with your Windows account directory:

```bash
python tools/sync_skills.py --skill teleport-tsh --destination /mnt/c/Users/WINDOWS_USER/.copilot/skills --destination ~/.copilot/skills
```

Review the preview, then append `--apply` to that command. Native Windows destinations can likewise be supplied to Windows Python using quoted Windows paths.

Use repeated `--skill` options to select several skills, or `--all` to select every top-level directory containing `SKILL.md`, including skills created in the future:

```bash
python tools/sync_skills.py --all
python tools/sync_skills.py --all --apply
```

`--all` installs missing skills as well as updating existing ones. It does not uninstall skills removed from this repository. No background updater, scheduled task, or Git hook is installed.

#### Update Safety

- Preview is the default and does not change installed packages or manifests. Review the listed added, changed, and removed file paths before applying.
- Successful installation records SHA-256 file hashes under the destination root's `.skill-sync-state/`. Keep these manifests: they distinguish the last synchronized version from local edits.
- Existing identical copies are adopted by recording a manifest. Existing different copies with no manifest are refused because their edit history is unknown.
- Local modifications, additions, and deletions are refused rather than overwritten. Even if source changes are present too, there is no force-overwrite option. Review the listed conflicts; merge intended changes into the repository or preserve a backup outside the installed skill, then reconcile the copy manually and preview again.
- All selected destinations are checked for conflicts before any writes. Each package is staged and verified before replacement, with restoration of the previous directory if installation fails. The entire multi-package run is not one transaction; an I/O failure later in a run can leave earlier packages updated. Re-run preview to inspect the result.
- Only the selected skill directories are copied, never repository-wide private configuration. Hidden paths such as `.local/` and `.env`, common runtime/build directories, and credential/archive suffixes such as `.pem`, `.key`, and `.skill` are excluded from source packages. Example JSON templates remain included. Symbolic links are refused. Exclusions are not a secret scanner: never place private configuration or credentials in distributable skill directories.
- Source metadata is validated before installation, and source/destination overlap is refused. No installed scripts are executed by synchronization.

Start a new Copilot chat after applying updates so the revised skill can be loaded. Existing conversations may retain previously loaded content. Keep organization-specific context outside the installed package and supply its path explicitly when using a skill.

Run the maintenance tool's isolated local tests with:

```bash
python -m unittest discover -s tests/tools -p test_sync_skills.py -v
```

## 🧑‍💻 How to contribute

Contributions are welcome!  
Feel free to open issues or submit pull requests to improve the rules, add new practices, or update documentation.

---

> ⚡ **Coming soon:**
> - Rules and best practices for API endpoints, feature slicing, and observability.
> - The [microcks-aspire-dotnet-demo](https://github.com/microcks/microcks-aspire-demo) repository is the official demo and testbed for these rules and practices.

Happy coding! 💡✨  
If you have any questions, don’t hesitate to open an issue or reach out.
