import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError

from app.db.models import Call, Callback, Escalation, LatencySample, Lead, Nudge, Signal, TranscriptSegment


def test_all_tables_insert_read_and_foreign_keys(client):
    app = client.app
    assert set(inspect(app.state.engine).get_table_names()) == {
        "calls", "leads", "callbacks", "escalations", "transcript_segments", "signals", "nudges", "latency_samples"}
    with app.state.sessions() as session:
        session.add(Call(call_id="fixture_call"))
        session.commit()
        session.add_all([
            Lead(lead_id="fixture_lead", call_id="fixture_call", name="Synthetic User"),
            Callback(callback_id="fixture_callback", call_id="fixture_call", reason="Synthetic callback"),
            Escalation(escalation_id="fixture_escalation", call_id="fixture_call", reason="Synthetic assistance"),
            TranscriptSegment(segment_id="fixture_segment", call_id="fixture_call", speaker="customer", text="Synthetic text", start_ms=0, end_ms=1000),
            Signal(signal_id="fixture_signal", call_id="fixture_call", type="callback_need", confidence=0.9, evidence="Synthetic text", speaker="customer", detected_at_ms=1000, priority="medium"),
        ])
        session.commit()
        session.add(Nudge(nudge_id="fixture_nudge", call_id="fixture_call", signal_id="fixture_signal", type="callback", text="Confirm callback time", priority="medium", confidence=0.9, created_at_ms=1000, expires_at_ms=2000, suppression_key="callback"))
        session.add(LatencySample(call_id="fixture_call", chunk_id=1, audio_received_ms=0, asr_done_ms=1, signal_done_ms=2, llm_done_ms=3, delivered_ms=4,
            asr_latency_ms=1, signal_latency_ms=1, llm_latency_ms=1, delivery_latency_ms=1, end_to_end_latency_ms=4))
        session.commit()
    with app.state.sessions() as session:
        for model in (Call, Lead, Callback, Escalation, TranscriptSegment, Signal, Nudge, LatencySample):
            assert len(session.scalars(select(model)).all()) == 1
        assert session.get(Lead, "fixture_lead").phone == "[REDACTED]"
        session.add(Callback(callback_id="bad", call_id="missing", reason="Synthetic"))
        with pytest.raises(IntegrityError):
            session.commit()
