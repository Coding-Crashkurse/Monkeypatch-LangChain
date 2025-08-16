import json
import logging
import time
import uuid
from functools import wraps
from typing import Any, Optional

import requests
from requests.adapters import HTTPAdapter

DEFAULT_TIMEOUT = (0.2, 0.2)
MAX_PREVIEW_LEN = 120
DEFAULT_REDACT_KEYS = {"callbacks", "metadata", "tags"}


class Patcher:
    """
    Drop-in logger/patcher for LangChain Runnables.

    Modes:
      - "simple": Replace RunnableLambda.invoke with a stub (no original call).
      - "production": Wrap .invoke and send start/end/error events.
    """

    def __init__(self, base_url: str, *, redact_keys: Optional[set[str]] = None):
        base = base_url.strip().rstrip("/")
        if not base.startswith(("http://", "https://")):
            base = "http://" + base
        self.endpoint = base + "/api/log"

        session = requests.Session()
        session.trust_env = False
        session.headers.update({"Content-Type": "application/json"})
        adapter = HTTPAdapter(pool_connections=2, pool_maxsize=4, max_retries=0)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        self._session = session

        self._run_id = uuid.uuid4().hex
        self._redact_keys = set(
            DEFAULT_REDACT_KEYS if redact_keys is None else redact_keys
        )

    @staticmethod
    def _preview(obj: Any, max_len: int = MAX_PREVIEW_LEN) -> str:
        try:
            text = repr(obj)
        except Exception:
            text = f"<unrepr:{type(obj).__name__}>"
        return (text[: max_len - 1] + "…") if len(text) > max_len else text

    @staticmethod
    def _redact_kwargs(kwargs: dict, keys: set[str]) -> dict:
        return {k: ("<omitted>" if k in keys else v) for k, v in kwargs.items()}

    @staticmethod
    def _simplify_output(value: Any) -> Any:
        """Return primitives as-is; otherwise return the type name."""
        if isinstance(value, (str, int, float, bool, type(None))):
            return value
        return type(value).__name__

    def _send(self, payload: dict) -> None:
        try:
            self._session.post(
                self.endpoint, data=json.dumps(payload), timeout=DEFAULT_TIMEOUT
            )
        except Exception as e:
            logging.debug(f"autolog send failed: {e}")

    def _patch(self, target: Any, method: str) -> None:
        try:
            original = getattr(target, method)
        except AttributeError:
            return
        if getattr(original, "__autolog_wrapped__", False):
            return

        @wraps(original)
        def wrapper(self_runnable: Any, *args, **kwargs):
            name = (
                getattr(self_runnable, "name", None) or self_runnable.__class__.__name__
            )
            base = {
                "run_id": self._run_id,
                "node_type": self_runnable.__class__.__name__,
                "name": name,
            }

            self._send(
                {
                    **base,
                    "event": "start",
                    "t": time.time(),
                    "args": self._preview(args),
                    "kwargs": self._preview(
                        self._redact_kwargs(kwargs, self._redact_keys)
                    ),
                }
            )

            t0 = time.perf_counter()

            def ms_since() -> int:
                return int((time.perf_counter() - t0) * 1000)

            def send(event: str, **extra: Any) -> None:
                self._send(
                    {
                        **base,
                        "event": event,
                        "t": time.time(),
                        "duration_ms": ms_since(),
                        **extra,
                    }
                )

            try:
                out = original(self_runnable, *args, **kwargs)
            except Exception as err:
                send("error", error=self._preview(err))
                raise
            else:
                simple = self._simplify_output(out)
                send("end", output=self._preview(simple))
                return out

        wrapper.__autolog_wrapped__ = True
        setattr(target, method, wrapper)

    def autolog(
        self, mode: str = "production", include_sequences: bool = False
    ) -> None:
        try:
            from langchain_core.runnables import RunnableLambda, RunnableSequence
        except ImportError as e:
            raise RuntimeError(f"LangChain core not available: {e}")

        if mode == "simple":

            def interceptor(*_a, **_k):
                print("Intercepted! The original function was never called.")
                return

            setattr(RunnableLambda, "invoke", interceptor)

        elif mode == "production":
            print("\n>>> ACTIVATING PRODUCTION LOGGING MODE <<<")
            self._patch(RunnableLambda, "invoke")
            if include_sequences:
                self._patch(RunnableSequence, "invoke")
        else:
            raise ValueError(f"Unknown mode: {mode}. Choose 'production' or 'simple'.")
