import os


DEFAULT_CORS_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)


def cors_origins() -> list[str]:
    configured = [
        origin.strip().rstrip("/")
        for origin in os.getenv("EMBER_CORS_ORIGINS", "").split(",")
        if origin.strip()
    ]
    return list(dict.fromkeys((*DEFAULT_CORS_ORIGINS, *configured)))
