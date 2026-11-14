# Fakes that replay recorded responses

Tests never touch the network, so they use a fake behind the adapter. A fake that returns a hand-written
response tests what the author believes the service returns. Record a real response once and have the fake
replay it, so the test runs against what the service does return.

1. Call the real service once, by hand, and save the response under `tests/fixtures/<service>/<case>.json`.
2. Remove secrets and personal data from the file before committing it: tokens, keys, emails, names.
3. The fake reads the file. No test makes the call again.
4. Record again when the service's API changes or a new case is needed. Never edit a recording to make a
   test pass.

## Python

```python
import json
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures" / "anthropic"


class FakeModel:
    """Stands in for the adapter; returns what the service returned when the case was recorded."""

    def __init__(self, case: str) -> None:
        self.response = json.loads((FIXTURES / f"{case}.json").read_text(encoding="utf-8"))
        self.calls: list[str] = []

    def complete(self, prompt: str) -> dict:
        self.calls.append(prompt)
        return self.response


def test_a_refusal_is_reported_not_parsed() -> None:
    result = extract("some transcript", model=FakeModel("refusal"))
    assert result.error == "refused"
```

With `respx`, the same file is the mocked reply:
`respx.post(URL).mock(return_value=httpx.Response(200, json=json.loads(path.read_text())))`.

## TypeScript

```ts
import refusal from "./fixtures/anthropic/refusal.json";

const fakeModel = (response: unknown) => ({
  calls: [] as string[],
  async complete(prompt: string) {
    this.calls.push(prompt);
    return response;
  },
});

test("a refusal is reported, not parsed", async () => {
  const result = await extract("some transcript", fakeModel(refusal));
  expect(result.error).toBe("refused");
});
```
