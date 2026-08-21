"""
ai_engine.py
------------
Talks to the Hugging Face **Inference API** (hosted) instead of loading
the model locally. This means:
  - No multi-GB download onto your machine.
  - No GPU/VRAM requirement on your end -- inference runs on HF's servers.
  - Each answer is just a normal HTTP call.

You need a (free) Hugging Face account + access token:
  1. Create a token at https://huggingface.co/settings/tokens
     (a "Read" token is enough for the Inference API/Providers).
  2. Set it as an environment variable before running the app:
       export HF_TOKEN="hf_xxxxxxxxxxxxxxxxxxxx"      (macOS/Linux)
       setx HF_TOKEN "hf_xxxxxxxxxxxxxxxxxxxx"          (Windows)
  3. Some models require you to accept their license on the model page
     first (visit https://huggingface.co/openai/gpt-oss-20b and click
     "Agree and access repository" if prompted).
"""

import os
import traceback

from huggingface_hub import InferenceClient

MODEL_NAME = "openai/gpt-oss-20b"

SYSTEM_PROMPT = (
    "You are a helpful assistant that answers questions using ONLY the "
    "document context provided by the user. If the answer cannot be found "
    "in the context, say clearly that the document does not contain that "
    "information. Be concise and accurate."
)


class AIEngine:
    """
    Thin wrapper around huggingface_hub.InferenceClient.

    Unlike loading the model locally, there's no big download/load step to
    wait on -- "status" here just reflects whether we have a usable token
    and the client initialized successfully.

    status values: "not_started" -> "ready" | "error"
    """

    status = "not_started"
    error_message = None
    _client = None

    @classmethod
    def start_loading(cls):
        """Initialize the InferenceClient. Cheap & fast (no model download)."""
        if cls.status == "ready":
            return
        token = os.environ.get("HF_TOKEN")
        if not token:
            cls.status = "error"
            cls.error_message = (
                "HF_TOKEN environment variable is not set. Get a token from "
                "https://huggingface.co/settings/tokens and set it as HF_TOKEN "
                "before running the app."
            )
            print(f"[ai_engine] {cls.error_message}", flush=True)
            return

        try:
            cls._client = InferenceClient(model=MODEL_NAME, token=token)
            cls.status = "ready"
            print(
                f"[ai_engine] Inference client ready for '{MODEL_NAME}' "
                f"(hosted on Hugging Face, no local download).",
                flush=True,
            )
        except Exception as exc:  # noqa: BLE001
            cls.status = "error"
            cls.error_message = str(exc)
            print("[ai_engine] FAILED to initialize Inference client:", flush=True)
            traceback.print_exc()

    @classmethod
    def answer_question(cls, context: str, question: str, max_new_tokens: int = 300) -> str:
        """
        Build a chat-formatted prompt containing the retrieved document
        context plus the user's question, call the hosted Inference API,
        and return the generated answer text.
        """
        if cls.status != "ready":
            raise RuntimeError(
                f"Model client is not ready (status={cls.status}). "
                f"Check /model-status. {cls.error_message or ''}"
            )

        user_content = (
            f"Document context:\n\"\"\"\n{context}\n\"\"\"\n\n"
            f"Question: {question}\n"
            f"Answer using only the context above."
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        print(f"[ai_engine] Sending question to hosted API: {question!r}", flush=True)
        try:
            response = cls._client.chat_completion(
                messages=messages,
                max_tokens=max_new_tokens,
                temperature=0.3,
            )
        except Exception as exc:  # noqa: BLE001
            print("[ai_engine] Inference API call failed:", flush=True)
            traceback.print_exc()
            raise RuntimeError(f"Hugging Face Inference API error: {exc}") from exc

        answer = response.choices[0].message.content
        return answer.strip()
