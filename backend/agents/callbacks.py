"""Plugin-registered callback factories for agent invocations.

Mirrors the register_provider_wrapper pattern in backend/llm/factory.py.
Plugins call register_callback_factory(fn) in their on_startup() hook; fn is
invoked with keyword args (agent_type, session_id, user_id, ...) at every
agent ainvoke() site and may return a single BaseCallbackHandler, a list of
handlers, or None to skip.
"""
import logging
from typing import Any, Callable, Optional, Union

from langchain_core.callbacks import BaseCallbackHandler

logger = logging.getLogger(__name__)

CallbackFactory = Callable[
    ...,
    Optional[Union[BaseCallbackHandler, list[BaseCallbackHandler]]],
]

_factories: list[CallbackFactory] = []


def register_callback_factory(fn: CallbackFactory) -> None:
    """Register a factory consulted by get_callbacks().

    Plugins should call this during on_startup().
    """
    _factories.append(fn)


def get_callbacks(**ctx: Any) -> list[BaseCallbackHandler]:
    """Collect callbacks from all registered factories.

    Exceptions raised by a factory are logged and that factory is skipped;
    other factories still run.
    """
    out: list[BaseCallbackHandler] = []
    for fn in _factories:
        try:
            result = fn(**ctx)
        except Exception as e:
            logger.warning("callback factory %r raised: %s", fn, e)
            continue
        if result is None:
            continue
        if isinstance(result, list):
            out.extend(result)
        else:
            out.append(result)
    return out
