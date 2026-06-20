# Notifier Protocol

## What This Is

`src/taskpilot_ai/interfaces/protocols.py` already contained a `NotifierProtocol` stub
left by Dev 2 for Dev 4 to implement:

```python
class NotifierProtocol(Protocol):
    def notify(self, message: str, channel: str = "cli") -> None: ...
```

Dev 4's job was to write real classes that satisfy this contract and wire them into the system.

## Why Protocols Matter

Python's `typing.Protocol` uses structural subtyping — a class qualifies as long as it has the
right method signatures. It does not need to import or inherit from `NotifierProtocol`.

This means Dev 2 could design the hook point before Dev 4 wrote a single line, and both
sides stayed completely decoupled. No circular imports, no tight coupling.

You can verify compliance at runtime:

```python
from taskpilot_ai.interfaces.protocols import NotifierProtocol
assert isinstance(CLINotifier(), NotifierProtocol)   # True
assert isinstance(SlackNotifier(), NotifierProtocol) # True
```

## What Dev 4 Added

Two concrete implementations in `src/taskpilot_ai/interfaces/notifiers.py`:

| Class | What it does |
|---|---|
| `CLINotifier` | Prints a bordered terminal alert with a UTC timestamp |
| `SlackNotifier` | Posts to a Slack incoming-webhook URL; falls back to CLI if no URL is set |

And a factory function:

```python
def build_notifier(slack_webhook_url=None) -> CLINotifier | SlackNotifier:
    ...
```

`build_notifier()` checks for a `SLACK_WEBHOOK_URL` environment variable and returns
`SlackNotifier` when one is present, otherwise `CLINotifier`.

## Key Concept: @runtime_checkable

```python
@runtime_checkable
class NotifierProtocol(Protocol): ...
```

Without `@runtime_checkable`, `isinstance()` checks on a Protocol raise `TypeError`.
With it, Python checks structurally at runtime — used in our tests to assert both
notifiers satisfy the contract.

## Main Concepts To Remember

- `Protocol` defines a contract without requiring inheritance
- `@runtime_checkable` enables `isinstance()` checks against a Protocol
- A factory function (`build_notifier`) is the clean way to choose an implementation at startup
- Fallback logic (CLI echo inside SlackNotifier) ensures alerts are never silently dropped
</content>
