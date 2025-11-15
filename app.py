import os
import uuid
from collections import defaultdict
from typing import Dict, List, Literal, Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field
from llama_stack_client import LlamaStackClient

#
# === CONFIG ===
#
# Możesz nadpisać to zmiennymi środowiskowymi:
#   LLAMA_BASE_URL, LLAMA_MODEL_ID
#
BASE_URL = os.getenv("LLAMA_BASE_URL", "http://lsd-llama-milvus-inline-service:8321/")
MODEL_ID = os.getenv("LLAMA_MODEL_ID", "llama-32-8b-instruct")

client = LlamaStackClient(base_url=BASE_URL)

app = FastAPI(
    title="LLM Chat API",
    description="Prosty FastAPI wrapper na Llama Stack (chat.completions) z historią rozmowy.",
    version="0.2.0",
)

# ====== KONFIG HISTORII ======

SYSTEM_PROMPT = (
    "You are a helpful assistant. Answer briefly, clearly and politely. "
    "You can use previous turns in the conversation to stay on topic."
)

# Ile ostatnich wiadomości trzymać (łącznie: user + assistant)
MAX_HISTORY_MESSAGES = 20


class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., description="Nowa wiadomość użytkownika.")
    conversation_id: Optional[str] = Field(
        default=None,
        description=(
            "Identyfikator konwersacji. Jeśli pusty, serwer utworzy nowy "
            "i zwróci go w odpowiedzi."
        ),
    )


class ChatResponse(BaseModel):
    answer: str
    model_id: str
    conversation_id: str = Field(
        ..., description="Id tej konwersacji – frontend powinien go zapamiętać."
    )


# Pamięć konwersacji w RAM-ie: conversation_id -> lista Message
ConversationHistory = List[Message]
conversation_store: Dict[str, ConversationHistory] = defaultdict(list)


def _append_to_history(
    conversation_id: str,
    user_message: Message,
    assistant_message: Message,
) -> None:
    """Zapisz parę (user, assistant) w historii i przytnij do MAX_HISTORY_MESSAGES."""
    history = conversation_store[conversation_id]
    history.append(user_message)
    history.append(assistant_message)

    # Przytnij historię do ostatnich N wiadomości
    if len(history) > MAX_HISTORY_MESSAGES:
        conversation_store[conversation_id] = history[-MAX_HISTORY_MESSAGES:]


@app.get("/health")
def health_check() -> dict:
    """Prosty endpoint zdrowotny."""
    return {"status": "ok", "model_id": MODEL_ID, "base_url": BASE_URL}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """
    Główne wejście dla frontendu / klienta.

    Przyjmuje:
    - `message`: aktualne pytanie użytkownika,
    - `conversation_id`: opcjonalny identyfikator konwersacji (session / chat id).

    Zwraca:
    - `answer`: odpowiedź LLM,
    - `conversation_id`: id konwersacji, które frontend powinien zapamiętać
      i przesyłać przy kolejnych zapytaniach.
    """
    # 1) Ustal conversation_id (nowy albo istniejący)
    if request.conversation_id:
        conversation_id = request.conversation_id
    else:
        conversation_id = str(uuid.uuid4())

    history = conversation_store[conversation_id]

    # 2) Zbuduj listę messages dla LLM
    messages: List[dict] = []

    # Stały system prompt (persona bota)
    messages.append({"role": "system", "content": SYSTEM_PROMPT})

    # Historia konwersacji z pamięci
    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})

    # Bieżąca wiadomość usera
    user_msg = Message(role="user", content=request.message)
    messages.append({"role": user_msg.role, "content": user_msg.content})

    # 3) Wywołaj LLM przez LlamaStack (OpenAI-compatible API)
    completion = client.chat.completions.create(
        model=MODEL_ID,
        messages=messages,
    )

    # message jest obiektem, nie dict!
    answer_text = completion.choices[0].message.content
    assistant_msg = Message(role="assistant", content=answer_text)

    # 4) Zapisz do historii
    _append_to_history(conversation_id, user_msg, assistant_msg)

    # 5) Zwróć odpowiedź + conversation_id
    return ChatResponse(
        answer=answer_text,
        model_id=MODEL_ID,
        conversation_id=conversation_id,
    )


if __name__ == "__main__":
    import os
    import uvicorn

    port = int(os.getenv("PORT", "8080"))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
