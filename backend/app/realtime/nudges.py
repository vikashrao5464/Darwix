import uuid

ACTIONS = {
 'compliance_risk':('compliance_correction','Correct the guarantee. Explain that approval depends on verified eligibility and review.'),
 'missed_opportunity':('explore_need','Ask about the additional need and offer a relevant human referral; verify product availability first.'),
 'rising_frustration':('acknowledge_concern','Acknowledge the concern and confirm what the customer needs before another question.'),
 'payment_difficulty':('payment_support','Acknowledge payment difficulty and offer an approved support callback; promise no waiver or extension.'),
 'callback_need':('arrange_callback','Ask for a convenient callback time and confirm it before recording the request.'),
}
def make_nudge(signal, now, expiry_seconds):
    kind, text = ACTIONS[signal['type']]
    return {'nudge_id':'nudge_' + uuid.uuid4().hex, 'signal_id':signal['signal_id'], 'call_id':signal['call_id'],
        'type':kind, 'text':text, 'priority':signal['priority'], 'confidence':signal['confidence'],
        'created_at_ms':round(now), 'expires_at_ms':round(now + expiry_seconds * 1000), 'suppression_key':signal['type']}
