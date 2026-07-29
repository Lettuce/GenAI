# Assistant Search Module

This package contains lightweight assistant-search utilities used by retrieval.

## Files

- `__init__.py`: package exports for assistant search utilities.
- `init.py`: compatibility shim for environments that import `assistant.init`.
- `agent.py`: `AssistantSearchAgent` planning wrapper.
- `depths.py`: query-depth presets and retrieval limits.
- `instructions.md`: module behavior and goals.
- `outputs.py`: typed plan/progress/result models.
- `progress.py`: progress event tracker.
- `tools.py`: keyword extraction and tsquery term construction.

## Integration

`app.retrieval.queries._build_fts_query_terms` now delegates to `app.assistant.tools.build_fts_query_terms`.
