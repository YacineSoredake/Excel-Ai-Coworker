"""'Ask your Excel' (report §8): question -> restricted query plan -> validated -> executed by code -> re-verified -> answer.

The LLM (when enabled) only turns a question into a plan and phrases the result. It never calculates.
Without an LLM, a rule-based planner answers the common questions.
"""
