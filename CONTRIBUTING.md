# Contributing

This is a personal template repo, but issues and PRs are welcome — especially a new
component/service idea, or a bug found while generating a real project from it.

- Branch off `main`, open a PR — direct pushes to `main` are blocked (see `.pre-commit-config.yaml`'s `no-commit-to-branch`).
- Before opening a PR: generate at least one project with your change enabled and confirm
  `uv sync && uv run pytest` passes in the generated output — the template repo itself isn't
  runnable in place (see the root `README.md`'s "Developing this template" section).
- Keep new toggles orthogonal — a new component/service should not require re-answering
  existing questions differently to keep working.
