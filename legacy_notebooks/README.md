# Frozen pre-migration notebooks

These are the original Natural Earth and shared-mask Jupyter notebooks, moved
without changing their contents. Production code now lives in `region_mask/`;
the `.py` notebooks in `notebooks/` are small marimo interfaces to that code.

Keep these copies only as migration references. Do not develop two implementations.
Other datasets' preparation notebooks have not been migrated in this change.

For an isolated re-execution of the original implementation, from the repository root:

```bash
.venv/bin/python -m regression run --runner regression.runners:notebook_runner
```

That adapter supplies paths/settings and executes in its own workspace. Opening
these legacy files directly requires the original repository-root working
directory and `.env`; use the current marimo notebooks for normal development.
