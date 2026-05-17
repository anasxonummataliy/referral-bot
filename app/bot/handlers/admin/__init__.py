from .base import admin_router

from . import channel
from . import gift_channel
from . import contest
from . import admin_manage
from . import broadcast
from . import stats
from . import users

__all__ = ["admin_router"]
