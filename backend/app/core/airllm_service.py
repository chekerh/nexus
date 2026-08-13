import importlib.util
import threading

from .config import settings


class AirLLMService:
    def __init__(self):
        self._lock = threading.Lock()
        self._model = None
        self._model_id = ""
        self._last_error = ""

    def is_available(self) -> bool:
        return importlib.util.find_spec("airllm") is not None

    def ensure_loaded(self) -> tuple[bool, str]:
        """Loads model once and reuses it for subsequent requests."""
        if not self.is_available():
            return False, "airllm package not installed"

        model_id = (settings.AIRLLM_MODEL_ID or "Qwen/Qwen2.5-3B-Instruct").strip()
        compression = (settings.AIRLLM_COMPRESSION or "").strip() or None

        with self._lock:
            if self._model is not None and self._model_id == model_id:
                return True, f"airllm model ready ({self._model_id})"

            try:
                from airllm import AutoModel

                kwargs = {}
                if compression:
                    kwargs["compression"] = compression

                self._model = AutoModel.from_pretrained(model_id, **kwargs)
                self._model_id = model_id
                self._last_error = ""
                return True, f"airllm model loaded ({self._model_id}, compression={compression or 'none'})"
            except Exception as e:
                self._model = None
                self._model_id = ""
                self._last_error = str(e)
                return False, f"airllm load failed: {e}"

    def unload(self) -> tuple[bool, str]:
        with self._lock:
            if self._model is None:
                return True, "airllm model already unloaded"
            try:
                self._model = None
                self._model_id = ""
                try:
                    import gc

                    gc.collect()
                except Exception:
                    pass
                try:
                    import torch

                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                    elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
                        # Best effort on Apple Silicon.
                        torch.mps.empty_cache()
                except Exception:
                    pass
                return True, "airllm model unloaded"
            except Exception as e:
                return False, f"airllm unload failed: {e}"

    def status(self) -> dict:
        return {
            "installed": self.is_available(),
            "loaded": self._model is not None,
            "model_id": self._model_id,
            "last_error": self._last_error,
            "compression": (settings.AIRLLM_COMPRESSION or "").strip() or "none",
        }

    def generate(self, prompt: str, max_length: int, max_new_tokens: int) -> str | None:
        ok, _ = self.ensure_loaded()
        if not ok or self._model is None:
            return None

        try:
            input_tokens = self._model.tokenizer(
                [prompt],
                return_tensors="pt",
                return_attention_mask=False,
                truncation=True,
                max_length=max_length,
                padding=False,
            )

            input_ids = input_tokens["input_ids"]
            try:
                import torch

                if torch.cuda.is_available():
                    input_ids = input_ids.cuda()
                elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
                    input_ids = input_ids.to("mps")
            except Exception:
                pass

            generation_output = self._model.generate(
                input_ids,
                max_new_tokens=max_new_tokens,
                use_cache=True,
                return_dict_in_generate=True,
            )
            return self._model.tokenizer.decode(generation_output.sequences[0])
        except Exception:
            return None


airllm_service = AirLLMService()
