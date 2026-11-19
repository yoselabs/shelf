# settings-base — changelog

AI-facing only: one line per contract-shape change, arrow notation. No prose, no rationale
(see the ledger for why). Read this before source/README when reconciling a pin
(agent-loop.md WORKFLOW: RECEIVE).

- 0.3.0: `# Any: <reason>` on the public signature that names `Any`; no behaviour or stored byte changes (shelf public-any rule, tests/test_arch_public_any.py)
- 0.2.0: BREAKING `resolve_config_path`: override set but not an existing file ⇒ raises new `ConfigOverrideError(ValueError)` (was `None`); unset ⇒ unchanged (`default` if a file else `None`)
- 0.2.0: `resolve_config_path(..., *, env=None)` and `resolve_env_refs(..., *, env=None)` take the environment as an argument (default `os.environ`)
