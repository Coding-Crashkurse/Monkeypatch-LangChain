import json
import logging
import time
import uuid
from functools import wraps
from typing import Any, Callable, Optional

import requests
from requests.adapters import HTTPAdapter

DEFAULT_TIMEOUT = (0.2, 0.2)
MAX_PREVIEW_LEN = 120
DEFAULT_REDACT_KEYS = {"callbacks", "metadata", "tags"}


class Patcher:
    def __init__(self, base_url: str, *, redact_keys: Optional[set[str]] = None):
        base = base_url.strip().rstrip("/")
        if not base.startswith(("http://", "https://")):
            base = "http://" + base
        self.endpoint = base + "/api/log"
        self._session = requests.Session()
        self._session.trust_env = False
        self._session.headers.update({"Content-Type": "application/json"})
        adapter = HTTPAdapter(pool_connections=2, pool_maxsize=4, max_retries=0)
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)
        self._run_id = uuid.uuid4().hex
        self._redact_keys = set(DEFAULT_REDACT_KEYS if redact_keys is None else redact_keys)
    
    @staticmethod
    def _preview(obj: Any, max_len: int = MAX_PREVIEW_LEN) -> str:
        try: text = repr(obj)
        except Exception: text = f"<unrepr:{type(obj).__name__}>"
        return (text[: max_len - 1] + "…") if len(text) > max_len else text
    @staticmethod
    def _redact_kwargs(kwargs: dict, redact_keys: set[str]) -> dict:
        return {k: "<omitted>" if k in redact_keys else v for k, v in kwargs.items()}
    def _send(self, payload: dict) -> None:
        try: self._session.post(self.endpoint, data=json.dumps(payload), timeout=DEFAULT_TIMEOUT)
        except Exception as e: logging.debug(f"autolog send failed: {e}")


    def _patch_logging_method(self, target: Any, method_name: str) -> None:
        try:
            original: Callable = getattr(target, method_name)
        except AttributeError:
            return
        if getattr(original, "__autolog_wrapped__", False):
            return

        @wraps(original)
        def wrapper(self_runnable: Any, *args, **kwargs):
            node_name = getattr(self_runnable, "name", None) or self_runnable.__class__.__name__
            base_payload = {"run_id": self._run_id, "node_type": self_runnable.__class__.__name__, "name": node_name}
            
            start_payload = {**base_payload, "event": "start", "t": time.time(), "args": Patcher._preview(args), "kwargs": Patcher._preview(Patcher._redact_kwargs(kwargs, self._redact_keys))}
            self._send(start_payload)
            
            t0 = time.perf_counter()

            error = None
            output = None
            try:
                output = original(self_runnable, *args, **kwargs)
                return output
            except Exception as e:
                error = e
                raise
            finally:
                duration_ms = int((time.perf_counter() - t0) * 1000)
                final_payload = {**base_payload, "duration_ms": duration_ms, "t": time.time()}
                if error:
                    final_payload["event"] = "error"
                    final_payload["error"] = Patcher._preview(error)
                else:
                    simple_out = output if isinstance(output, (str, int, float, bool, type(None))) else type(output).__name__
                    final_payload["event"] = "end"
                    final_payload["output"] = Patcher._preview(simple_out)
                self._send(final_payload)
        
        wrapper.__autolog_wrapped__ = True
        setattr(target, method_name, wrapper)

    def autolog(self, mode: str = "production", include_sequences: bool = False) -> None:
        try:
            from langchain_core.runnables import RunnableLambda, RunnableSequence
        except ImportError as e:
            raise RuntimeError(f"LangChain core not available: {e}")

        if mode == "simple":
            interceptor = lambda *args, **kwargs: "Intercepted! The original function was never called."
            setattr(RunnableLambda, "invoke", interceptor)
            
        elif mode == "production":
            print("\n>>> ACTIVATING PRODUCTION LOGGING MODE <<<")
            self._patch_logging_method(RunnableLambda, "invoke")
            if include_sequences:
                self._patch_logging_method(RunnableSequence, "invoke")
        else:
            raise ValueError(f"Unknown mode: {mode}. Choose 'production' or 'simple'.")