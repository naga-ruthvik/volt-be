# Platform Clients

This package exposes platform clients via a single import path:

```python
from activities.services.platforms import GitHubClient, CodeforcesClient
```

## Normalized Outputs

### Grouped Summaries
Used for daily activity summaries (heatmaps). Each item follows:

```json
{
  "platform": "github",
  "date": "YYYY-MM-DD",
  "count": 5
}
```

### Item Lists
Used for lists of individual items (events/submissions/repos). Each item follows:

```json
{
  "id": "string-id",
  "platform": "github",
  "created_at": "2026-05-22T15:17:45Z",
  "event_type": "PushEvent"
}
```

- `id` is the native platform identifier when available.
- If missing, a deterministic fallback ID is generated using MD5 with the exact layout:
  `"{platform}_{username}_{timestamp}_{event_type}"`.

## Error Behavior

### Expected user/business errors
Returned as a standard payload dict:

```json
{
  "status": "error",
  "platform": "platform_name",
  "error_type": "INVALID_USERNAME" | "RATE_LIMIT" | "UNKNOWN",
  "message": "Human readable message string",
  "details": {}
}
```

### Infrastructure/network failures
Raised as a typed exception:

- `PlatformNetworkError`

## Field Types

- `platform`: `str` (e.g., `"github"`, `"codeforces"`)
- `date`: `str` (`YYYY-MM-DD`)
- `count`: `int`
- `created_at`: `str` (ISO 8601 timestamp)
- `id`: `str`

