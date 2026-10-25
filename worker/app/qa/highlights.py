"""'What should I pay attention to?' / 'Find suspicious data' (report §8): answered from the stored insights, never invented."""
import re

ATTENTION = re.compile(
    r"\bwhat (?:should|do) i (?:pay attention|look at|focus|check)|\bwhat stands out\b|\banything (?:unusual|strange|odd|wrong|suspicious)\b|"
    r"\bfind (?:any )?(?:suspicious|unusual|strange|odd|wrong|bad|problem)|\bsuspicious\b|\banomal(?:y|ies)\b|"
    r"\b(?:ce qui ressort|points? d.attention|donn[ée]es suspectes|rien d.anormal)\b", re.I)
SUSPICIOUS = re.compile(r"\bsuspicious\b|\bunusual\b|\bstrange\b|\bodd\b|\bwrong\b|\bbad\b|\bproblem|\banomal|suspectes|anormal", re.I)
SUSPECT_CATEGORIES = {"anomaly", "consistency", "quality"}


def is_attention(question: str) -> bool:
    return bool(ATTENTION.search(question or ""))


def highlights_answer(question: str, insights: list) -> dict:
    """insights: rows with category, priority, statement, next_check, next_plan."""
    suspicious = bool(SUSPICIOUS.search(question))
    rows = sorted(insights, key=lambda r: r["priority"])
    if suspicious:
        rows = [r for r in rows if r["category"] in SUSPECT_CATEGORIES]
    rows = rows[:5]
    base = {"status": "ok", "plan": None, "plan_summary": None, "definition": None, "chart": None, "caveats": [], "notes": [],
            "sample_rows": [], "options": None, "source": {"plan": "rules", "text": "template", "text_issues": [], "ai_error": None, "ai_detail": None}}
    if not rows:
        return {**base, "text": ("Nothing looks suspicious: no unusual values, inconsistencies or data-quality issues stood out."
                                 if suspicious else "Nothing in particular stands out in this workbook."),
                "result": {"kind": "highlights", "data": {"items": []}, "rows_used": 0, "rows_after_filters": 0}, "followups": []}
    items, seen = [], set()
    for r in rows:
        nc, plan = r.get("next_check") or "", r.get("next_plan")
        if nc in seen:  # several findings can suggest the same next question: offer it once, on the first
            nc, plan = "", None
        seen.add(nc)
        items.append({"statement": r["statement"], "category": r["category"], "next_check": nc, "next_plan": plan})
    follow = [{"text": i["next_check"], "plan": i["next_plan"]} for i in items if i["next_plan"]][:3]
    return {**base, "text": ("Here is what looks unusual or inconsistent, most important first. These are patterns to check, not conclusions."
                             if suspicious else "Here is what stands out, most important first. These are patterns in the data, not explanations."),
            "result": {"kind": "highlights", "data": {"items": items}, "rows_used": 0, "rows_after_filters": 0}, "followups": follow}
