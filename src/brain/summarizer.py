# This Script is responsible for producing a running summary of a conversation's older turns
# Triggered by ConversationService once a batch of turns falls outside HISTORY_WINDOW -- folds
# them into (and replaces) the conversation's stored summary, so a long single-session
# conversation degrades gracefully instead of silently losing its early turns once the raw
# history window fills up. Deliberately synchronous: this runs inline on whichever turn crosses
# SUMMARY_BATCH_SIZE, adding one extra model call's latency to that turn -- acceptable for a
# personal assistant; move it to a background thread later if that latency spike ever matters.
from typing import List, Optional
from src.brain.client import ModelClient
from src.brain.request_schema import OpenAIRequestSchema
from src.database.models import Message
from src.core.config import BASE_URL, API_KEY, MODEL

SUMMARY_SYSTEM_PROMPT = (
    "You maintain a running summary of an ongoing conversation, for another AI "
    "assistant's own future reference -- not for the end user to read. Given the "
    "previous summary (if any) and a batch of new messages, write an updated "
    "summary that preserves facts, decisions, names, and context a continuation "
    "of this conversation would need. Be concise: a few sentences to a short "
    "paragraph. Output only the summary text, nothing else."
)


class Summarizer:
    def __init__(self, base_url: str = BASE_URL, api_key: str = API_KEY, model: str = MODEL) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.model = model

    def summarize(self, previous_summary: Optional[str], messages: List[Message]) -> str:
        transcript = "\n".join(f"{m.role}: {m.content}" for m in messages)
        user_content = (
            f"Previous summary:\n{previous_summary or '(none yet)'}\n\n"
            f"New messages to fold in:\n{transcript}"
        )
        request = OpenAIRequestSchema(
            model=self.model,
            messages=[
                {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            stream=False,   # this is a one-off structured call, not a chat turn -- no need to stream
            thinking=False, # condensing text doesn't need extended reasoning; keeps this call fast
            tools=[],
        )
        client = ModelClient(request, base_url=self.base_url, api_key=self.api_key)
        response = client.post()
        if response is None:
            raise RuntimeError("Summarization request failed")
        return response.json()["choices"][0]["message"]["content"].strip()
