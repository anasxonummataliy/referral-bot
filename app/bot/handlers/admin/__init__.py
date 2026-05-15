# bot/handlers/admin/__init__.py
from .base import admin_router

from . import stats
from . import channels
from . import users

# from . import broadcast
# from . import secret

__all__ = ["admin_router"]
