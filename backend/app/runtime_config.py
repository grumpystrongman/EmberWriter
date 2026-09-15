import os

DEFAULT_CORS_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)

_LOCAL_PROXY_BYPASS_HOSTS = (
    "127.0.0.1",
    "localhost",
    "host.docker.internal",
)


def ensure_local_proxy_bypass() -> str:
    """Keep local EmberWriter/Stable Diffusion traffic out of system HTTP proxies."""
    existing = os.getenv("NO_PROXY") or os.getenv("no_proxy") or ""
    entries = [item.strip() for item in existing.split(",") if item.strip()]
    known = {item.casefold() for item in entries}
    for host in _LOCAL_PROXY_BYPASS_HOSTS:
        if host.casefold() not in known:
            entries.append(host)
            known.add(host.casefold())
    value = ",".join(entries)
    os.environ["NO_PROXY"] = value
    os.environ["no_proxy"] = value
    return value


# httpx honors proxy environment variables by default. On managed/corporate Windows
# machines a proxy can accidentally intercept localhost requests, turning a healthy
# local Forge/A1111 service into repeated timeouts. Apply this before any requests.
ensure_local_proxy_bypass()


def cors_origins() -> list[str]:
    configured = [
        origin.strip().rstrip("/")
        for origin in os.getenv("EMBER_CORS_ORIGINS", "").split(",")
        if origin.strip()
    ]
    return list(dict.fromkeys((*DEFAULT_CORS_ORIGINS, *configured)))
