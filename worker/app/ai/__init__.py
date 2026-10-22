"""Phase 5 — AI layer (report §6, §8, §12.4, §15).

The LLM is a *phrasing and question-understanding* component only:
  - it never sees raw rows, never calculates, and its output is never trusted;
  - every number, period and name it writes must be traceable to verified facts (claims.py);
  - anything that fails validation is replaced by deterministic text.
"""
