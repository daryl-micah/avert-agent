# Experiment 2 — first corpus run (2026-09-18)

**Status:** unlabelled. Numbers below are extractor output, not recall. The decision rule
(SPEC §15: <85% recall kills the inventory product) cannot be applied until the label templates
are reviewed.

**Command:** `uv run avert experiment2 --out <dir>` against `engine/tests/fixtures/experiment2/corpus.json`
(20 public repositories, 13 Python / 7 TypeScript, pinned by commit). Raw report: [experiment2-2026-09-18.json](experiment2-2026-09-18.json).

| repository | sites | literal / dynamic / absent |
|---|---:|---|
| simonw/llm | 9 | 0 / 8 / 1 |
| Aider-AI/aider | 0 | — |
| assafelovic/gpt-researcher | 0 | — |
| 567-labs/instructor | 226 | 117 / 53 / 56 |
| crewAIInc/crewAI | 29 | 7 / 5 / 17 |
| microsoft/autogen | 12 | 2 / 2 / 8 |
| vibrantlabsai/ragas | 22 | 8 / 14 / 0 |
| openai/swarm | 12 | 1 / 5 / 6 |
| browser-use/browser-use | 25 | 1 / 20 / 4 |
| stanfordnlp/dspy | 1 | 0 / 1 / 0 |
| mem0ai/mem0 | 41 | 3 / 24 / 14 |
| huggingface/smolagents | 1 | 0 / 1 / 0 |
| run-llama/llama_index | 59 | 0 / 32 / 27 |
| mckaywrigley/chatbot-ui | 14 | 4 / 10 / 0 |
| cline/cline | 3 | 3 / 0 / 0 |
| promptfoo/promptfoo | 10 | 3 / 1 / 6 |
| anthropics/claude-code-action | 0 | — |
| e2b-dev/fragments | 0 | — |
| danny-avila/LibreChat | 1 | 0 / 0 / 1 |
| continuedev/continue | 7 | 0 / 1 / 6 |
| **total** | **472** | **149 / 177 / 146** |

## Findings

1. **A fifth hard class: aggregator SDKs.** Every repository at 0–1 sites calls providers through
   a wrapper the vocabulary does not know: `litellm.completion` (aider ×8, dspy ×15, smolagents ×32),
   LangChain `ChatOpenAI` (gpt-researcher ×14), Vercel AI SDK `createOpenAI` (fragments ×3), and the
   Claude Agent SDK (claude-code-action ×9). Counts are GitHub code-search hits, not labels. This
   class is absent from `engine/tests/fixtures/` (raw fetch, config-assembled, YAML literal, vendored).
   Unlike those four it is a typed SDK call — resolvable by tree-sitter with vocabulary entries, no
   LLM tier needed. In litellm the model string carries the provider (`anthropic/claude-…`), so the
   `SurfaceID` tuple holds; the aggregator is a call path, not a provider.
2. **Literal model strings are a minority (32%).** Two thirds of detected call sites bind the model
   dynamically or omit it. The literal-only patch generator (`patch/model_replacement.py`) therefore
   covers under a third of sites even where detection is perfect. Dynamic sites are where the
   `possible` match kind in `join.py` matters.
3. **Precision needs a look at the high-count repos.** instructor (226) and llama_index (59) are
   themselves provider wrappers; a meaningful share of their sites will be library internals rather
   than application call sites. Whether that counts as a false positive is a labelling policy
   question to settle before review starts.

## Next

- Review templates (`<owner>__<repo>.labels.jsonl` in the output directory), commit under a labels
  directory, re-run with `--labels`.
- Add an `aggregator_sdk` fixture and ground truth, locked at 0% recall like the other hard classes,
  so lifting it is a conscious change.
