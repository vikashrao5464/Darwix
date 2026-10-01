import uuid

from app.db.models import Escalation


def request_escalation(session, call, reason):
    identifier = "esc_" + uuid.uuid5(uuid.NAMESPACE_URL, call.call_id).hex
    existing = session.get(Escalation, identifier)
    if existing is None:
        session.add(Escalation(escalation_id=identifier, call_id=call.call_id, reason=reason))
    call.status = "escalated"
    return identifier
