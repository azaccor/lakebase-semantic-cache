"""Ask Genie: a thin wrapper over the Genie Conversation API for the app's Genie tab. The space
(resources/genie.yml) sits over the semantic_cache_metrics gold tables, so answers are SQL over
governed data; each answer returns Genie's text, the SQL it ran, and the first rows of the result."""
from __future__ import annotations

from datetime import timedelta

MAX_ROWS = 50
TIMEOUT = timedelta(seconds=120)


class GenieChat:
    def __init__(self, w, space_id: str | None):
        self.w, self.space_id = w, space_id or None

    def ask(self, question: str, conversation_id: str | None = None) -> dict:
        if not self.space_id:
            raise RuntimeError("No Genie space is attached to this app (GENIE_SPACE_ID is unset)")
        g = self.w.genie
        msg = (g.create_message_and_wait(self.space_id, conversation_id, question, timeout=TIMEOUT) if conversation_id
               else g.start_conversation_and_wait(self.space_id, question, timeout=TIMEOUT))
        message_id = msg.message_id or msg.id
        out = {"conversation_id": msg.conversation_id, "message_id": message_id,
               "status": msg.status.value if msg.status else None,
               "error": msg.error.error if msg.error else None,
               "text": [], "queries": [], "suggested_questions": []}
        for a in msg.attachments or []:
            if a.text and a.text.content:
                out["text"].append(a.text.content)
            if a.query:
                out["queries"].append({"title": a.query.title, "description": a.query.description, "sql": a.query.query,
                                       **self._result(msg.conversation_id, message_id, a.attachment_id)})
            if a.suggested_questions and a.suggested_questions.questions:
                out["suggested_questions"] += a.suggested_questions.questions
        return out

    def _result(self, conversation_id: str, message_id: str, attachment_id: str) -> dict:
        resp = self.w.genie.get_message_attachment_query_result(self.space_id, conversation_id, message_id, attachment_id)
        sr = resp.statement_response
        if not sr or not sr.manifest or not sr.manifest.schema:
            return {"columns": [], "rows": [], "row_count": 0}
        rows = (sr.result.data_array or []) if sr.result else []
        return {"columns": [c.name for c in sr.manifest.schema.columns], "rows": rows[:MAX_ROWS],
                "row_count": sr.manifest.total_row_count if sr.manifest.total_row_count is not None else len(rows)}
