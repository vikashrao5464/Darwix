import asyncio
import io
import json
import wave
import math
import struct

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm.exc import StaleDataError

from app.db.models import Call, Callback, Escalation, Lead
from app.db.session import initialize_database
from app.schemas.voice import ASRResult, InterpretedTurn, QualificationState
from app.voice.interpretation import field_value, parse_number
from app.voice.qualification import update_field


def start(client, call_id="voice_fixture", recording=False, consent=True):
    reply = client.post("/api/voice/calls", json={"call_id":call_id, "recording_consent":recording})
    assert reply.status_code == 200, reply.text
    if consent:
        assert client.post("/api/voice/consent", json={"call_id":call_id,"consent":True}).status_code == 200
    return call_id


def turn(client, call_id, text, turn_id="turn_1"):
    response = client.post(f"/api/voice/calls/{call_id}/turn", json={"turn_id":turn_id,"text":text})
    assert response.status_code == 200, response.text
    return response.json()


def fill(client, call_id, **overrides):
    values = dict(requested_amount=500000,business_type="retail",business_age_months=48,
                  annual_turnover=2400000,existing_loan=False,city="Demo City",callback_preference=False)
    values.update(overrides)
    for field, value in values.items():
        response = client.post("/api/voice/tools/update_qualification", json={"call_id":call_id,"field":field,"value":value})
        assert response.status_code == 200, response.text


def wav(silent=False):
    stream = io.BytesIO()
    with wave.open(stream,"wb") as file:
        file.setnchannels(1); file.setsampwidth(2); file.setframerate(16000)
        file.writeframes(b"\x00\x00" * 16000 if silent else b"".join(struct.pack("<h",int(5000*math.sin(2*math.pi*300*i/16000))) for i in range(16000)))
    return stream.getvalue()


def test_consent_decline_and_preconsent_pii_are_not_retained(client):
    call = start(client, consent=False)
    reply = turn(client,call,"Email me at demo@example.test and lend me 500000")
    assert reply["status"] == "awaiting_consent"
    assert all(f["status"] == "missing" for f in reply["qualification"]["fields"].values())
    assert client.post("/api/voice/qualification",json={"call_id":call,"field":"city","value":"Demo City"}).status_code == 403
    turn(client,call,"No","turn_2")
    snapshot = client.get(f"/api/voice/calls/{call}").json()
    assert snapshot["status"] == "declined"
    assert all(s["speaker"] == "agent" for s in snapshot["transcript"])
    assert "demo@example.test" not in json.dumps(snapshot)
    assert client.post(f"/api/voice/calls/{call}/turn",json={"turn_id":"turn_3","text":"Yes"}).status_code == 409


def test_unclear_consent_then_yes_records_only_consent(client):
    call = start(client, consent=False)
    turn(client,call,"Maybe","turn_1")
    reply = turn(client,call,"Yes","turn_2")
    assert reply["next_field"] == "requested_amount"
    customers = [s for s in client.get(f"/api/voice/calls/{call}").json()["transcript"] if s["speaker"] == "customer"]
    assert [s["text"] for s in customers] == ["Consent granted."]


def test_tentative_conflict_and_explicit_resolution_preserve_values(client):
    call = start(client)
    reply = turn(client,call,"Maybe five hundred thousand")
    assert reply["qualification"]["fields"]["requested_amount"]["status"] == "tentative"
    reply = turn(client,call,"Yes","turn_2")
    assert reply["qualification"]["fields"]["requested_amount"]["status"] == "confirmed"
    reply = turn(client,call,"Requested amount is 600000","turn_3")
    field = reply["qualification"]["fields"]["requested_amount"]
    assert field["value"] == 500000 and field["status"] == "conflicting"
    assert field["candidates"] == [500000,600000]
    reply = turn(client,call,"600000","turn_4")
    field = reply["qualification"]["fields"]["requested_amount"]
    assert field["value"] == 600000 and field["status"] == "confirmed"


@pytest.mark.parametrize("field,value",[("business_age_months",True),("business_age_months",1.2),
    ("requested_amount",-4),("annual_turnover","lots"),("existing_loan","false"),("city"," "),("unknown",3)])
def test_malformed_qualification_is_safe(client,field,value):
    call = start(client)
    result = client.post("/api/voice/tools/update_qualification",json={"call_id":call,"field":field,"value":value})
    assert result.status_code == 422


@pytest.mark.parametrize("value,expected",[("500,000",500000),("five hundred thousand",500000),
    ("two million four hundred thousand",2400000),("500000 or 600000",None),("minus three",None),
    ("half a million",None),("no amount provided",None)])
def test_number_interpretation_does_not_guess(value,expected):
    assert parse_number(value) == expected
    assert field_value("business_age_months","four") is None


def test_unknown_detail_keeps_missing(client):
    call = start(client)
    reply = turn(client,call,"I don't know")
    assert reply["qualification"]["fields"]["requested_amount"]["status"] == "missing"
    assert "explicit value" in reply["text"]


@pytest.mark.parametrize("override,status",[({},"preliminarily_qualified"),({"business_age_months":12},"not_preliminarily_qualified"),
    ({"existing_loan":True},"needs_human_review"),({"city":"Elsewhere"},"needs_human_review")])
def test_source_backed_eligibility(indexed_client,override,status):
    client = indexed_client; call = start(client); fill(client,call,**override)
    response = client.post("/api/voice/tools/evaluate_preliminary_eligibility",json={"call_id":call})
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == status and len(result["rules"]) == 6
    assert all(r["citation"]["record_id"] and r["citation"]["version"] == "1.0" for r in result["rules"])


def test_incomplete_and_conflicting_eligibility_do_not_guess(client):
    call = start(client)
    response = client.post("/api/voice/eligibility",json={"call_id":call}).json()
    assert response["status"] == "incomplete" and len(response["missing_fields"]) == 6
    fill(client,call)
    client.post("/api/voice/qualification",json={"call_id":call,"field":"requested_amount","value":600000})
    assert client.post("/api/voice/eligibility",json={"call_id":call}).json()["status"] == "needs_human_review"


@pytest.mark.parametrize("mode",["stale","changed_threshold","missing_index","timeout"])
def test_eligibility_unavailable_evidence_falls_back(indexed_client,tmp_path,monkeypatch,mode):
    client=indexed_client; call=start(client); fill(client,call)
    settings=client.app.state.settings
    if mode in {"stale","changed_threshold"}:
        config=json.loads(settings.qualification_rules_path.read_text())
        config["rules"][0]["source_checksum" if mode=="stale" else "value"] = "bad" if mode=="stale" else 100001
        path=tmp_path/"rules.json"; path.write_text(json.dumps(config)); settings.qualification_rules_path=path
    else:
        async def unavailable():
            if mode=="timeout": await asyncio.sleep(2)
            return []
        settings.provider_timeout_seconds=.01
        monkeypatch.setattr(client.app.state.knowledge.index,"records",unavailable)
    result=client.post("/api/voice/eligibility",json={"call_id":call}).json()
    assert result["status"] == "unavailable" and result["rules"] == []


def test_faq_and_objection_use_kb_and_unknown_falls_back(indexed_client):
    client=indexed_client; call=start(client)
    for i,query in enumerate(["What is the processing fee?","I do not want to share documents."]):
        result=turn(client,call,query,f"turn_{i}")
        assert result["grounded"] and result["citations"] and result["tools_called"] == ["search_knowledge"]
    result=turn(client,call,"What cashback applies to lunar tourism?","unknown")
    assert result["grounded"] is False and result["citations"] == [] and "verified information" in result["text"]


def test_all_action_tools_are_http_testable_and_idempotent(indexed_client):
    client=indexed_client; call=start(client); fill(client,call)
    callback={"call_id":call,"requested_time":"Tomorrow at 3 PM","reason":"Email demo@example.test"}
    first=client.post("/api/voice/tools/schedule_callback",json=callback).json()
    assert first == client.post("/api/callbacks",json=callback).json()
    assert client.post("/api/callbacks",json={**callback,"requested_time":"Friday at 4 PM"}).status_code == 409
    first=client.post("/api/voice/tools/create_lead",json={"call_id":call}).json()
    assert first == client.post("/api/leads",json={"call_id":call}).json()
    call2=start(client,"escalation_fixture",consent=False)
    body={"call_id":call2,"reason":"My account is 1234567890123456"}
    first=client.post("/api/voice/tools/request_human_escalation",json=body).json()
    assert first == client.post("/api/escalations",json=body).json()
    with client.app.state.sessions() as session:
        assert len(session.scalars(select(Lead)).all()) == 1
        assert len(session.scalars(select(Callback)).all()) == 1
        assert "demo@example.test" not in session.scalars(select(Callback)).one().reason
        assert session.scalars(select(Escalation)).one().reason == "Human assistance requested before consent"


def test_turn_retries_are_idempotent_and_conflicting_id_is_rejected(client):
    call=start(client)
    reply=turn(client,call,"500000")
    assert reply == turn(client,call,"500000")
    assert client.post(f"/api/voice/calls/{call}/turn",json={"turn_id":"turn_1","text":"600000"}).status_code == 409
    snapshot=client.get(f"/api/voice/calls/{call}").json()
    assert snapshot["revision"] == reply["revision"]
    assert len([s for s in snapshot["transcript"] if s["speaker"] == "customer"]) == 1


def test_callback_conversation_and_mock_lead_completion(indexed_client):
    client=indexed_client; call=start(client); fill(client,call)
    reply=turn(client,call,"Call me back")
    assert "day and time" in reply["text"]
    reply=turn(client,call,"Tomorrow at three PM","turn_2")
    assert reply["callback_id"]
    reply=turn(client,call,"Yes","turn_3")
    assert reply["lead_id"] and reply["status"] == "completed"
    with client.app.state.sessions() as session:
        assert session.get(Lead,reply["lead_id"]).callback_requested is True


@pytest.mark.parametrize("failure",["timeout","invented_evidence"])
def test_interpretation_failure_cannot_update_state(client,monkeypatch,failure):
    call=start(client); client.app.state.settings.llm_provider="openai"
    client.app.state.settings.provider_timeout_seconds=.01
    async def broken(*args):
        if failure=="timeout": await asyncio.sleep(2)
        return InterpretedTurn(intent="details",field="requested_amount",evidence="invented amount",uncertain=False)
    monkeypatch.setattr(client.app.state.conversation.llm,"interpret_turn",broken)
    reply=turn(client,call,"500000")
    assert "reliably" in reply["text"]
    assert reply["qualification"]["fields"]["requested_amount"]["status"] == "missing"


@pytest.mark.parametrize("failure",["low_confidence","timeout","provider_error"])
def test_asr_failure_does_not_update_state(client,monkeypatch,failure):
    call=start(client); client.app.state.settings.asr_timeout_seconds=.01
    async def recognize(audio):
        if failure=="timeout": await asyncio.sleep(2)
        if failure=="provider_error": raise RuntimeError("private provider details")
        return ASRResult(text="500000",confidence=.2)
    monkeypatch.setattr(client.app.state.asr,"transcribe",recognize)
    result=client.post(f"/api/voice/calls/{call}/audio-turn?turn_id=audio_1",content=wav()).json()
    assert result["accepted"] is False
    assert "private provider details" not in json.dumps(result)
    assert client.get(f"/api/voice/calls/{call}").json()["qualification"]["fields"]["requested_amount"]["status"] == "missing"


def test_audio_success_redaction_invalid_wav_and_tts_fallback(client,monkeypatch):
    call=start(client)
    async def recognize(audio): return ASRResult(text="500000",confidence=.9)
    monkeypatch.setattr(client.app.state.asr,"transcribe",recognize)
    result=client.post(f"/api/voice/calls/{call}/audio-turn?turn_id=audio_1",content=wav()).json()
    assert result["accepted"] and result["reply"]["tools_called"] == ["update_qualification"]
    assert result["reply"]["qualification"]["fields"]["requested_amount"]["status"] == "tentative"
    async def confirm(audio): return ASRResult(text="Yes",confidence=.9)
    monkeypatch.setattr(client.app.state.asr,"transcribe",confirm)
    confirmed=client.post(f"/api/voice/calls/{call}/audio-turn?turn_id=audio_confirm",content=wav()).json()
    assert confirmed["reply"]["qualification"]["fields"]["requested_amount"]["status"] == "confirmed"
    assert client.post(f"/api/voice/calls/{call}/audio-turn?turn_id=audio_2",content=b"not wav").status_code == 422
    async def broken(*args): raise TimeoutError("private error")
    monkeypatch.setattr(client.app.state.tts,"synthesize",broken)
    response=client.get(f"/api/voice/calls/{call}/speech/greeting")
    assert response.status_code == 503 and "private error" not in response.text


def test_withdrawn_consent_stops_recording_and_future_tools(client):
    call=start(client,recording=True)
    reply=turn(client,call,"Withdraw consent")
    assert reply["status"] == "ended" and reply["recording_allowed"] is False
    assert client.post(f"/api/voice/calls/{call}/recording",content=wav()).status_code == 403
    assert client.post("/api/voice/qualification",json={"call_id":call,"field":"city","value":"Demo City"}).status_code == 403


def test_recording_requires_separate_consent_and_is_private(client):
    call=start(client)
    assert client.post(f"/api/voice/calls/{call}/recording",content=wav()).status_code == 403
    call=start(client,"record_fixture",recording=True)
    response=client.post(f"/api/voice/calls/{call}/recording",content=wav())
    assert response.status_code == 200
    assert client.get(response.json()["download_url"]).content == wav()
    assert len(list(client.app.state.settings.recordings_dir.glob("*.wav"))) == 1
    assert client.post("/api/voice/calls",json={"call_id":"../../outside"}).status_code == 422


def test_migration_preserves_existing_calls(tmp_path):
    url=f"sqlite:///{(tmp_path/'old.db').as_posix()}"
    engine=create_engine(url)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE calls (call_id VARCHAR PRIMARY KEY, product VARCHAR, language VARCHAR, status VARCHAR, consent_obtained BOOLEAN, state JSON, created_at VARCHAR)"))
        connection.execute(text("INSERT INTO calls VALUES ('old','business_loan','en','active',1,'{}','synthetic')"))
    engine.dispose()
    engine,sessions=initialize_database(url)
    with sessions() as session:
        row=session.get(Call,"old")
        assert row.status == "active" and row.revision == 1
    engine.dispose()


def test_concurrent_call_write_cannot_silently_overwrite(client):
    call=start(client)
    with client.app.state.sessions() as first, client.app.state.sessions() as second:
        a=first.get(Call,call); b=second.get(Call,call)
        a.state={**a.state,"writer":"first"}; first.commit()
        b.state={**b.state,"writer":"second"}
        with pytest.raises(StaleDataError): second.commit()
