# LeetCode Client

Minimal usage example for the LeetCode GraphQL client.

## Quick Start

```python
from activities.services.platforms.leetcode.client import LeetcodeClient

client = LeetcodeClient()
profile = client.get_user_profile("example_user")
print(profile)
```

## Notes

- All responses follow the standard payload shape: status, platform, username, data.
- Error payloads include the centralized user-not-found message.

