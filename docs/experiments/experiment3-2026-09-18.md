# Experiment 3 — first real-repository run (2026-09-18)

**Status:** mechanically verified, not graded. The merge-as-is rate (SPEC §15: <70% means ship
alerts, gate PRs) still needs an experienced engineer to grade each diff.

**Command:** `uv run avert experiment3 --cases engine/tests/fixtures/experiment3/corpus.json --out <report>`.
Ten public repositories, one per registry lifecycle event, pinned by commit, each containing the
retired model string in a typed SDK file found by GitHub code search. No per-repository `checks`
were configured, so "verified" means: patch applied in a disposable copy and re-indexing found the
replacement model at the patched call site. Raw report: [experiment3-2026-09-18.json](experiment3-2026-09-18.json).

| case | repository | matching sites | proposals | verified |
|---|---|---:|---:|---|
| self-operating-computer-claude-3-opus | OthersideAI/self-operating-computer | 2 | 2 | yes |
| claude-engineer-sonnet-3-5-october | Doriandarko/claude-engineer | 1 | 1 | yes |
| olmocr-sonnet-3-7 | allenai/olmocr | 2 | 2 | yes |
| fastrtc-haiku-3-5 | gradio-app/fastrtc | 2 | 2 | yes |
| fasthtml-example-haiku-3 | AnswerDotAI/fasthtml-example | 2 | 2 | yes |
| ffufai-sonnet-4 | jthack/ffufai | 2 | 2 | yes |
| headroom-opus-4 | headroomlabs-ai/headroom | 0 | 0 | **no** |
| longrag-sonnet-3-5-june | TIGER-AI-Lab/LongRAG | 1 | 1 | yes |
| ibm-compositional-gpt-4-0613 | IBM/limitations-lm-algorithmic-compositional-learning | 0 | 0 | **no** |
| vision-agents-opus-4-1 | GetStream/Vision-Agents | 0 | 0 | **no** |

**7/10 mechanically verified.**

## Findings

1. **Every miss is the same shape: the literal is not at the call.** In all three failures the
   retired model string is a function default (`def prompt(..., model="gpt-4-0613")`), a
   constructor argument (`anthropic.LLM(model="claude-opus-4-1-20250805")`), or a wrapper argument,
   and the provider call itself reads `model=model` / `model=self.model`. The extractor correctly
   classifies those calls as `dynamic`; the literal-only generator (`patch/model_replacement.py`)
   then has nothing to patch. This is the patch-side counterpart of experiment 2's finding that
   68% of real call sites bind the model dynamically. A one-hop definition lookup (default
   parameter, module constant, `self.model` assigned from a literal in `__init__`) would cover all
   three without a model call.
2. **Where the literal is at the call, the generator is exact.** Seven of seven such cases
   produced one proposal per site and re-indexed cleanly, including files with two sites.
3. **"Verified" is still weak.** No case ran the repository's own tests (`checks`). The
   `replacement_index` check proves the edit is syntactically and identity-correct, not that the
   code works with the new model. The synthetic corpus (`cases.json`) remains the offline lock.

## Next

- Grade the seven diffs (`avert remediate` writes them) and record `grades.json`.
- Decide whether the one-hop definition lookup belongs in the extractor (raising `dynamic` →
  `literal` with a lower confidence) or in the patch generator only.
