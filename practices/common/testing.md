# Testing and checks

- Write the failing test first where practical and confirm it fails for the right reason; new functions, routes and rules ship with their tests, failure paths included. {core; initial}
- Tests never touch the network or a hosted service: use fakes behind adapter interfaces, HTTP mocks or in-memory databases. {core; initial}
- Before moving on, run the project's lint, typecheck and test commands (the `verify` skill). {core; initial}
- Run quiet or failures-only variants of commands first, and widen only when they don't explain the problem. {topic; initial}
