"""Sandboxed Python execution engine for user skill code."""
import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

_ALLOWED_MODULES = {"httpx", "json", "datetime", "re", "math", "requests"}

_BLOCKED_BUILTINS = {
    "__import__", "open", "exec", "eval", "compile",
    "breakpoint", "input", "print",
}


def _make_restricted_globals(params: dict, secrets: dict) -> dict:
    """Build a restricted globals dict for sandboxed exec."""
    import builtins

    safe_builtins = {
        name: getattr(builtins, name)
        for name in dir(builtins)
        if name not in _BLOCKED_BUILTINS and not name.startswith("__")
    }
    # Allow __build_class__ for class definitions, but block dangerous ones
    safe_builtins["__build_class__"] = builtins.__build_class__

    def restricted_import(name, *args, **kwargs):
        top_level = name.split(".")[0]
        if top_level not in _ALLOWED_MODULES:
            raise ImportError(f"Import of '{name}' is not allowed in skill code")
        return builtins.__import__(name, *args, **kwargs)

    safe_builtins["__import__"] = restricted_import

    return {
        "__builtins__": safe_builtins,
        "params": params,
        "secrets": secrets,
    }


async def execute_skill_code(code: str, params: dict, secrets: dict) -> Any:
    """
    Execute user-provided skill code in a sandboxed environment.

    The code must define an async function named `run` which receives
    `params` and `secrets` as globals. Example:

        async def run():
            import httpx
            url = params.get("url")
            async with httpx.AsyncClient() as client:
                resp = await client.get(url)
                return resp.json()

    Args:
        code: Python source code string defining async def run()
        params: Dict of runtime parameters passed as global `params`
        secrets: Dict of secret values passed as global `secrets`

    Returns:
        Whatever the run() function returns, or an error dict on failure
    """
    restricted_globals = _make_restricted_globals(params, secrets)

    try:
        exec(compile(code, "<skill>", "exec"), restricted_globals)
    except SyntaxError as exc:
        logger.warning(f"Skill code syntax error: {exc}")
        return {"error": f"Syntax error in skill code: {exc}"}
    except ImportError as exc:
        logger.warning(f"Skill code blocked import: {exc}")
        return {"error": str(exc)}
    except Exception as exc:
        logger.warning(f"Skill code exec error: {exc}")
        return {"error": f"Code execution error: {exc}"}

    run_fn = restricted_globals.get("run")
    if run_fn is None:
        return {"error": "Skill code must define an async function named 'run'"}

    if not asyncio.iscoroutinefunction(run_fn):
        return {"error": "Skill 'run' function must be async (async def run())"}

    import inspect
    sig = inspect.signature(run_fn)

    try:
        # Support both `async def run()` (params as globals) and
        # `async def run(params)` (params as argument) for robustness.
        if sig.parameters:
            result = await asyncio.wait_for(run_fn(params), timeout=30.0)
        else:
            result = await asyncio.wait_for(run_fn(), timeout=30.0)
        return result
    except asyncio.TimeoutError:
        logger.warning("Skill code execution timed out after 30 seconds")
        return {"error": "Skill execution timed out after 30 seconds"}
    except ImportError as exc:
        logger.warning(f"Skill code blocked import at runtime: {exc}")
        return {"error": str(exc)}
    except Exception as exc:
        logger.warning(f"Skill code runtime error: {exc}")
        return {"error": f"Runtime error: {exc}"}
