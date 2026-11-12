# Code structure

- Keep framework glue thin: logic lives in plain modules that can be tested without the framework; routes, DAGs and handlers only wire things together. {topic; initial}
- Put external services (models, CI hosts, storage) behind an interface with one real adapter, so tests pass a fake and swapping providers is configuration. {topic; initial}
- Generated files (OpenAPI specs, API clients) are committed and never edited by hand. Regenerate them in the same change as their source, and have CI fail when they are stale. {topic; initial}
- Ask before adding a dependency the project brief does not name. {core; initial}
