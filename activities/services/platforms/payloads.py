import hashlib


def error_payload(
    platform: str,
    error_type: str,
    message: str,
    details: dict | None = None,
) -> dict:
    return {
        "status": "error",
        "platform": platform,
        "error_type": error_type,
        "message": message,
        "details": details or {},
    }


def success_payload(platform: str, username: str | None, data: object) -> dict:
    return {
        "status": "success",
        "platform": platform,
        "username": username,
        "data": data,
    }


def build_fallback_id(
    platform: str, username: str, timestamp: str, event_type: str
) -> str:
    input_str = f"{platform}_{username}_{timestamp}_{event_type}"
    return hashlib.sha256(input_str.encode("utf-8")).hexdigest()
