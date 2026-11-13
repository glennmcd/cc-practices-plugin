# Secrets and untrusted input

- Secrets come from the environment or a secret store, never from code, committed config or logs. {core; initial}
- Error messages name a missing variable, never its value; never log tokens, full request headers or user content the project marks private. {topic; initial}
- Treat uploaded or fetched input as untrusted: cap sizes while streaming, and never trust declared sizes or client-supplied identity. {review; initial}
