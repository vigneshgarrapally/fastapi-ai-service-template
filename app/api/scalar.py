"""Scalar API reference — interactive, environment-gated API docs.

Serves an interactive `Scalar <https://scalar.com>`_ API reference at ``/scalar``
in every non-production environment. Scalar renders the FastAPI OpenAPI schema
and ships a built-in HTTP client ("Test Request") that can authenticate against
the API using the same header-based auth the protected endpoints expect.

Environment gating
-------------------
The route is registered **only when the environment is not ``production``**. In
production the reference is never mounted, so there is no unauthenticated,
schema-revealing internal API surface on the public internet. (The default
``/docs`` and ``/redoc`` UIs are likewise disabled in production by ``app/main.py``.)

Servers
-------
Scalar is served same-origin from FastAPI, so by default (``public_base_url``
empty) the built-in client targets whatever origin the browser loaded ``/scalar``
from. An explicit ``servers`` entry is passed only when
``settings.app.public_base_url`` is set, for deployments where the public URL
differs from the browser origin (reverse proxy / custom domain).
"""

import structlog
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from scalar_fastapi import AgentScalarConfig, Layout, Theme, get_scalar_api_reference

from app.core.config import Settings

logger = structlog.get_logger(__name__)

_SCALAR_PATH = "/scalar"


def register_scalar(app: FastAPI, settings: Settings) -> None:
    """Register the Scalar API reference route on the app (non-production only).

    Adds ``GET /scalar`` serving the interactive Scalar reference. The route is
    excluded from the OpenAPI schema (``include_in_schema=False``) and is **not**
    registered at all when ``settings.app.environment == "production"``.

    Args:
        app:      The FastAPI application to register the route on.
        settings: Application settings — supplies the environment gate and the
                  public base URL used as the built-in client's target server.
    """
    environment = settings.app.environment
    if environment == "production":
        logger.info("scalar.disabled", reason="production environment")
        return

    base_url = settings.app.public_base_url
    servers = (
        [{"url": base_url, "description": f"{settings.app.app_name} {environment}"}]
        if base_url
        else []
    )

    @app.get(_SCALAR_PATH, include_in_schema=False)
    async def scalar_reference() -> HTMLResponse:
        return get_scalar_api_reference(
            openapi_url=app.openapi_url,
            title=f"{settings.app.app_name} API ({environment})",
            servers=servers,
            layout=Layout.MODERN,
            theme=Theme.DEFAULT,
            dark_mode=True,
            # Scalar's AI Agent defaults on and makes an external network call —
            # disable it so no request leaves the browser without explicit opt-in.
            agent=AgentScalarConfig(disabled=True),
        )

    logger.info("scalar.enabled", path=_SCALAR_PATH, environment=environment)
