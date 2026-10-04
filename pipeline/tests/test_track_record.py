from pipeline.track_record import earned_quota, level, records


def claim(cid, who, ok=1, seq=1, subject="MONDO:1"):
    return {"claim_id": cid, "assertion_id": "a" + cid, "subject": subject, "predicate": "has_symptom", "object": "HP:1",
            "body": "{}", "contributor": who, "origin": "contributed", "kernel_ok": ok, "created_seq": seq}


def review(cid, who, verdict, seq, family="openai-gpt6"):
    return {"claim_id": cid, "reviewer": who, "reviewer_kind": "model", "model_family": family, "model": "m", "verdict": verdict,
            "reason": "r", "seq": seq, "event_id": f"e{seq}"}


def test_levels_and_earned_limits():
    assert level(3, 1) == "new"
    assert level(9, 1) == "reliable" and level(4, 1) == "mixed" and level(2, 4) == "unreliable"
    assert earned_quota(100, "reliable") == 200 and earned_quota(100, "unreliable") == 25 and earned_quota(10, "unreliable") == 5


def test_records_count_outcomes_and_reviewer_agreement():
    claims = [claim("c1", "agent:mcp-a", seq=1), claim("c2", "agent:mcp-a", seq=2), claim("c3", "agent:mcp-a", ok=0, seq=3),
              claim("c4", "agent:mcp-a", seq=4)]
    reviews = [review("c1", "agent:referee", "supports", 10), review("c2", "agent:referee", "does_not_support", 11),
               review("c1", "agent:mcp-b", "supports", 12, "google-gemini"), review("c2", "agent:mcp-b", "supports", 13, "google-gemini")]
    out = records(claims, reviews, [{"target": "c1", "challenger": "agent:mcp-b"}], lambda s: f"t{s}", lambda c: "Seizure", lambda c: "Cond")
    a = out["agent:mcp-a"]
    assert (a["submitted"], a["quote_failed"], a["accepted"], a["disputed"], a["pending"], a["challenged"]) == (4, 1, 1, 1, 1, 1)
    assert [r["status"] for r in a["recent"]] == ["unreviewed", "quote_check_failed", "review_disagreement", "independently_reviewed"]
    b = out["agent:mcp-b"]
    assert b["reviews_given"] == 2 and b["challenges_made"] == 1 and b["reviews_compared"] == 2 and b["reviews_agreed"] == 1
