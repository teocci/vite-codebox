# Error Handling

## Custom Exceptions

- Define in `exceptions.py`: base `AppError`, then specific subclasses (`ValidationError`, `DatabaseError`, `ConfigurationError`)
- Include relevant context in exception messages

## Exception Rules

- Never use bare `except:` — always specify exception type
- Don't catch exceptions just to re-raise without context
- Use exception chaining: `raise CustomError('msg') from e`
- Catch specific exceptions, not `Exception`

## Logging Over Print

- Use `logging` module, never `print()` for operational output
- Use `logger = logging.getLogger(__name__)` in each module
- Configure logging in entry point only, not in library modules

## Log Levels

| Level | Use For |
|-------|---------|
| DEBUG | Detailed diagnostic info |
| INFO | Confirmation of expected behavior |
| WARNING | Unexpected but handled situations |
| ERROR | Failures that prevent operation |
| CRITICAL | System-wide failures |

## Resource Cleanup

- Always use context managers (`with`) for files, connections, and other resources
