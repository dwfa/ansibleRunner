# AGENTS.md

## Project Context

- This repository builds the standalone Python package `ansibleRunner`.
- Use the package name `ansibleRunner`; do not rename it to `ansible-runner`.
- The public API should expose `main(project_root, argv=None)` for thin project wrappers.
- Project-specific wrappers such as `rpiMgmt` should only discover/pass `project_root` and `argv`.

## Specification Reference

- Treat `@docs/seSpecs` as the read-only specification reference for coding decisions.
- Before changing behavior, public APIs, CLI shape, project layout, or extraction boundaries, inspect the relevant files under `@docs/seSpecs`.
- Do not edit files in `@docs/seSpecs` from this repository. Make specification changes upstream in `dwfa/seSpecs`, then update this submodule pointer when this project is ready to consume them.

## Reference Map

- `@docs/README.md`: local documentation notes for this repository.
- `@docs/seSpecs/README.md`: entry point for the shared engineering specifications.
- `@docs/seSpecs/designPrinciples.md`: design principles to apply before adding abstractions or changing architecture.
- `@docs/seSpecs/codeStyle.md`: coding style guidance.
- `@docs/seSpecs/ansibleGuidelines.md`: Ansible-specific conventions.
- `@docs/seSpecs/developmentWorkflow.md`: development and verification workflow.
- `@docs/seSpecs/documentation.md`: documentation expectations.
- `@docs/seSpecs/loggingDiagnostics.md`: logging and diagnostic guidance.
- `@docs/seSpecs/namingConventions.md`: naming conventions.
- `@docs/seSpecs/variableScoping.md`: variable scope and ownership rules.
- `@docs/seSpecs/versioning.md`: versioning guidance.
- `@docs/seSpecs/markdownAuthoring.md`: Markdown authoring rules.

## Development Expectations

- Keep reusable TUI, Ansible runner, progress, prompt, logs/state default, and CLI entrypoint logic in `@src/ansibleRunner/`.
- Keep tests in `@tests/` focused on the package API and behavior expected by thin wrappers.
- Prefer small, scoped changes that preserve the package boundary between `ansibleRunner` and project-specific shims.
