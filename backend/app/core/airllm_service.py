import importlib
import threading
from typing import Optional, Tuple

from .config import settings


class AirLLMService:
    def __init__(self):
        self._lock = threading.Lock()
        self._model = None
        self._model_id = ""

    def is_available(self) -> bool:
        return importlib.util.find_spec("airllm") is not None

    def ensure_loaded(self) -> Tuple[bool, str]:
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
                return True, f"airllm model loaded ({self._model_id}, compression={compression or 'none'})"
            except Exception as e:
                self._model = None
                self._model_id = ""
                return False, f"airllm load failed: {e}"

    def generate(self, prompt: str, max_length: int, max_new_tokens: int) -> Optional[str]:
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
