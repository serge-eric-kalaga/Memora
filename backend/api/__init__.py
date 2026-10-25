from api.configs import SETTINGS
from fastapi import FastAPI


def createApp(config: SETTINGS, *, initialise_database: bool = True) -> FastAPI:
    """Construire l’API ; l’export OpenAPI peut ignorer toute initialisation SQL."""
    import werkzeug.exceptions as werkexcept
    from fastapi import Request, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.exceptions import RequestValidationError
    from fastapi.responses import JSONResponse, StreamingResponse
    from starlette.exceptions import HTTPException as starletteHTTPException
    from api.services.mail import send_app_exception_to_admin

    from api.services import socket
    from api.utility.lifespan import LifeSpan
    from api.configs.logging import logDebug, logInfo, logError
    from api.views import user_router, auth_router, healthcheck_router
    from api.views.access import router as access_router

    Setting = config
    app = FastAPI(
        title=Setting.APP_NAME,
        lifespan=LifeSpan,
    )
    from api.memora.routes import router as memora_router

    app.include_router(memora_router)
    app.include_router(access_router, prefix="/api/access")
    app.include_router(auth_router, prefix="/api/auth")
    app.include_router(user_router, prefix="/api/user")
    app.include_router(healthcheck_router, prefix="/api/healthcheck")

    # ----PROMETHEUS------
    from prometheus_fastapi_instrumentator import Instrumentator

    from prometheus_fastapi_instrumentator import metrics as prometheus_metrics

    # Les sondes ne doivent pas masquer la latence métier ; conserver des buckets
    # au-delà d’une seconde pour que le p95 et ses alertes soient exploitables.
    Instrumentator(excluded_handlers=["/metrics", "/api/healthcheck/"]).add(
        prometheus_metrics.default(
            metric_namespace="api",
            latency_lowr_buckets=(
                0.005,
                0.01,
                0.025,
                0.05,
                0.1,
                0.25,
                0.5,
                1,
                2.5,
                5,
                10,
            ),
        )
    ).instrument(app).expose(app, tags=["OTHER"])

    # ----mount socket------
    sm = socket.socketio.ASGIApp(socket.server, socketio_path="/ws/socket.io")
    app.mount("/ws", sm)
    app.sio = socket.server

    # ------get request from any webpage---------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(
            {
                Setting.FRONTEND_URL.rstrip("/"),
                "http://localhost:3000",
                "http://127.0.0.1:3000",
            }
        ),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --------add logger for each an every request--------
    @app.middleware("http")
    async def loggingRequest(request: Request, call_next):
        """
        Middleware pour logger chaque requête HTTP entrante et la réponse correspondante. Il enregistre les détails de la requête (méthode, URL, hôte du client) et le code de statut de la réponse
        """

        do_not_log = False
        if request.url.path in [
            "/api/healthcheck/",
            "/metrics",
            "/ws/socket.io/",
        ]:
            do_not_log = True

        if not do_not_log:
            logDebug(
                "-------------------------------------------------------------------------"
            )
            logInfo(
                f"{request.method}, {request.url.path if not request.url.path.startswith('/api/memora') else '/api/memora/[resource]'}, {request.client.host}"
            )
        response: StreamingResponse = await call_next(request)

        if not do_not_log:
            logInfo(f"{response.status_code}")
        return response

    @app.exception_handler(werkexcept.HTTPException)
    def handleWerkZeugException(req, exc):
        """
        Gestionnaire d'exception pour les exceptions HTTP de Werkzeug
        """
        logError(exc)
        if exc.code == 500:
            send_app_exception_to_admin(
                error_message=exc,
                error_type="Internal Server Error",
            )
        return JSONResponse(
            content={
                "status": -1,
                "status_code": exc.code,
                "message": f"{exc.description}",
            },
            status_code=exc.code,
        )

    @app.exception_handler(HTTPException)
    def handleHTTPException(req, exc):
        """
        Gestionnaire d'exception pour les exceptions HTTP de FastAPI
        """
        logError(exc)
        if exc.status_code == 500:
            send_app_exception_to_admin(
                error_message=exc,
                error_type="Internal Server Error",
            )
        return JSONResponse(
            content={
                "status": -1,
                "status_code": exc.status_code,
                "message": f"{exc.detail}",
            },
            status_code=exc.status_code,
        )

    @app.exception_handler(RequestValidationError)
    def handleValidationErrorException(req, exc):
        """
        Gestionnaire d'exception pour les erreurs de validation des requêtes FastAPI
        """
        # Les erreurs Pydantic contiennent aussi l’entrée brute (mots de passe, jetons).
        logInfo("Validation de requête refusée")
        return JSONResponse(
            content={
                "status": -1,
                "status_code": 400,
                "message": "Vérifiez les informations saisies.",
            },
            status_code=400,
        )

    @app.exception_handler(starletteHTTPException)
    def handleStarletteException(req, exc):
        """
        Gestionnaire d'exception pour les exceptions HTTP de Starlette
        """
        logError(exc)
        if exc.status_code == 500:
            send_app_exception_to_admin(
                error_message=exc,
                error_type="Internal Server Error",
            )
        return JSONResponse(
            content={
                "status": -1,
                "status_code": exc.status_code,
                "message": f"{exc.detail}",
            },
            status_code=exc.status_code,
        )

    @app.exception_handler(Exception)
    def handleException(req, exc):
        """
        Gestionnaire d'exception pour toutes les autres exceptions non gérées
        """
        logError(exc)
        send_app_exception_to_admin(
            error_message=exc,
            error_type="Internal Server Error",
        )
        return JSONResponse(
            content={"status": -1, "status_code": 500, "message": f"{exc}"},
            status_code=500,
        )

    # ----------------init db------------------
    from api.database import init_database, engine

    if initialise_database:
        init_database(engine)

    from api.services.cache import configure_cache

    configure_cache(app, config)
    return app
