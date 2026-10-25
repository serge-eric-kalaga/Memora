"""
Ce package contient les différentes routes de l'application.
"""

from .auth.login import auth_router as auth_router
from .auth.user import user_router as user_router
from .healthcheck import healthcheck_router as healthcheck_router
