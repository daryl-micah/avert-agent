# Avert — Product Specification

**Version:** 0.1 (pre-build)
**Status:** Draft for validation
**Last updated:** August 2026

---

## 1. Thesis

External APIs change underneath running code, and nothing in the consuming repository moves when they do. Existing tooling — Dependabot, Renovate, SBOM scanners, OpenAPI diffing tools — all assume a *declared artifact*: a manifest entry, a lockfile, a version string. When a provider changes server-side behaviour, retires a model, alters a response shape, or tightens a rate limit, there is no artifact to bump and therefore nothing for existing tools to detect.

Avert closes that gap by joining two things nobody currently joins:

1. **A multi-source change feed** for external APIs — built from SDK artifact diffs, spec diffs, sunset headers, vendor emails, and observed production traffic.
2. **A semantic index of customer code** — every external API call site, resolved to a canonical identity.

The join produces something no existing tool can emit: *"this specific change affects these specific lines in your codebase, here is the patch, and here is proof it is safe."*

### The one-sentence positioning

> Dependabot for APIs — except APIs don't have a lockfile to bump. The server changes underneath you and nothing in your repo moves, so we detect the change from SDK diffs and your own production traffic, then map it to the exact call sites that care.

---

## 2. Problem statement

### For the API consumer (primary user)

- Breaking changes arrive by email to a dev alias nobody reads, or not at all.
- Silent behavioural changes (new enum values, changed nullability, altered defaults) produce no notification of any kind and fail *inside* the consumer's own code, after a successful 200 response.
- Nobody in the organisation can accurately answer "which external APIs do we depend on, and where?"
- LLM model deprecations are entirely invisible to dependency tooling, because the version is a string literal argument, not a package version.
- Migration work is unplanned, urgent, and lands on whoever is on call.

### For the API provider (secondary buyer, phase 3)

- Deprecation campaigns take engineering quarters and never fully complete.
- Old API versions are maintained indefinitely because a long tail of customers never migrated.
- No visibility into which customers are on which version, or how much work migration would be for them.

### Why now

- Agentic coding tools have normalised granting external tools access to codebases. This was not true two years ago.
- Frontier models can generate correct migration patches given a well-scoped change description.
- LLM provider APIs have made the problem acute: model retirement cycles are measured in months, and model identifiers are string literals scattered through production code.

---

## 3. What Avert is not

Explicitly out of scope, to keep the product honest:

- **Not an APM or uptime monitor.** Avert does not page you when an API is down.
- **Not a general code-migration agent.** Avert only acts on external API surface changes.
- **Not a vendor upsell channel.** Avert will surface newly available API capabilities as *notifications only*, never as pull requests. The moment the tool is perceived as a sales channel for providers, developer trust — and therefore repository access — is lost.
- **Not an internal API contract tool.** Avert concerns APIs the customer *consumes* and does not control. (Optic, the YC-backed spec-diffing company, archived its repository in January 2026 in part because spec-file-only tooling could not help with third-party APIs. That failure mode is deliberately avoided here.)

---

## 4. Users and buyers

| Role | Relationship | What they care about |
|---|---|---|
| Platform / infrastructure engineer | Primary user and champion | Not getting paged; reducing unplanned migration work |
| Engineering manager | Economic buyer at seed–Series B | Predictable capacity; fewer surprise fire drills |
| Head of platform / VP Eng | Economic buyer at Series C+ | Org-wide visibility; audit trail; vendor risk |
| Security / vendor risk | Blocker | Scope of repository access; data handling |
| Provider DevRel / API platform lead | Phase 3 buyer | Migration completion rate; ability to sunset old versions |

**Beachhead segment:** Series A–C engineering organisations with 20–200 engineers, heavy AI API usage, no dedicated platform team large enough to track vendor changes manually.

---

## 5. Product surface

Avert ships as three layers. Each is independently valuable and each is a prerequisite for the next.

### 5.1 Layer 1 — Inventory (the wedge)

**Access required:** read-only.

A live map of every external API dependency across an organisation's repositories.

For each dependency:
- Provider, resource, operation
- Version or model identifier in use
- Every call site: file, line, owning service, owning team
- Whether the call site sits in a critical path (payment, auth, checkout)
- Auth pattern in use
- Lifecycle status: current / deprecated / retiring on date / retired

**Why this is the entry point:**
- Read-only scope clears a security review in days, not months.
- No false positives are possible — Avert is reporting facts, not proposing changes. The first impression with a platform team is accuracy.
- It is independently valuable. No organisation can currently produce this list.
- It is the substrate everything else depends on. The impact join is impossible without it.

**Deliverable formats:** web dashboard, JSON export, and an "API SBOM" report suitable for vendor risk review.

### 5.2 Layer 2 — Change feed and impact alerts

**Access required:** read-only, plus optional runtime collector.

Avert continuously ingests changes across tracked providers, normalises them to canonical surface identities, and joins them against the customer's code index.

Output per change event:
- What changed, in plain language
- Severity and effective date
- Exactly which call sites are affected
- Blast radius statement ("3 files, 1 in the payment path, owned by team-billing")
- Recommended action

Alerts route to Slack, email, or webhook. Alerts optimise for **recall** — missing a breaking change is the cardinal failure.

### 5.3 Layer 3 — Verified remediation

**Access required:** write (opt-in, per-repository).

For change events above a confidence threshold, Avert opens a pull request containing:

- The patch
- **An evidence bundle** (see §9)
- A plain-English explanation of what changed and why the patch is correct

Pull requests optimise for **precision**. Below the confidence threshold, Avert emits a diagnostic alert and does not open a PR. Conflating the two thresholds is how a tool of this kind becomes noise and gets disabled.

### 5.4 Layer 4 — Agent-facing feed (strategic hedge)

Avert exposes its change intelligence as an API and an MCP server, so that coding agents (Claude Code, Cursor, Devin, and successors) can query:

> "What changed in provider X between date A and B, and what is the verified migration?"

**Rationale:** the primary existential risk to this business is that coding agents absorb API migration as a built-in feature. If patch *execution* commoditises, Avert should own the data layer the executors depend on. This converts the worst-case scenario into a distribution channel.

---

## 6. Architecture

Two independent pipelines that meet only at the canonical registry.

```
Change sources                          Customer repos
(SDK diffs, spec diffs,                 (read-only access)
 sunset headers, email,
 runtime traffic)
      |                                       |
      v                                       v
  Normalise                                 Index
  (events → surface IDs)              (tree-sitter → call sites)
      |                                       |
      +------------------+--------------------+
                         v
                   Impact join
              (change → affected lines)
                         |
                         v
                 Patch and verify
            (generate, replay, test, score)
                         |
            +------------+------------+
            v                         v
      Pull request                 Alert
   (high confidence only)      (with diagnosis)
```

The two top branches never communicate directly. This decoupling means Layer 1 (right branch alone) and the change feed (left branch alone) can each ship and generate revenue before the join is reliable.

### 6.1 The load-bearing abstraction

Everything depends on **canonical surface identity**. Both pipelines resolve into it; the join is then a database query rather than an AI problem.

```python
class SurfaceID(BaseModel):
    provider: str           # "stripe", "openai"
    resource: str           # "charge", "chat.completions"
    operation: str | None   # "create"
    field_path: str | None  # "metadata.customer_id", "model"
    value: str | None       # "gpt-4-0613", "eu_bank_transfer"
```

This schema is the single hardest thing to change later — every stored call site and historical change event references it. Everything else in the system is replaceable.

#### Why `value` is part of identity

`value` names an *inhabitant* of a surface rather than the surface itself: a model identifier, an enum member, a webhook event type, an API version string passed as an argument.

Without it the beachhead is inexpressible. Every call to `chat.completions.create` collapses to a single identity regardless of which model it names, and "`gpt-4-0613` retires on date D" has no identity to attach to — which is precisely the blind spot §11 claims to close. It also makes the §13 cross-customer aggregate and the §15 Phase 3 pitch (*"400 codebases are using this"*) countable at the granularity that matters, because the thing being retired is the value, not the endpoint.

Semantics: `value = None` means the surface itself, not a specific inhabitant. A change event at `(openai, chat.completions, create, model, None)` concerns the parameter; at `(…, model, "gpt-4-0613")` it concerns one model. The join stays a query — a null event value covers every value:

```sql
event.value IS NULL OR event.value = call_site.value
```

#### Why version is *not* part of identity

Version is a statement about *when a surface claim holds*, not about which surface it is. Putting it in the tuple would fragment `charge.create` into one identity per API version, break aggregation across the cross-customer graph, and make a call site unresolvable whenever the version cannot be determined statically — which is most of the time.

Version therefore lives on the two edges, and the join applies it as a filter after identity match:

- `ChangeEvent.applies_from` / `applies_to` — the version range the change is in effect for
- `CallSite.api_version` — the version pinned at or around that call site, `None` when unpinned

Note that SDK package version is a different thing again: a property of the artifact that was diffed (§7.1), recorded as ChangeEvent provenance. It is not a property of the surface and must not be conflated with the provider's API version.

#### Resolution state

A null on a call site means "unknown", while a null on a change event means "all". Same SQL null, opposite meanings — so call sites record how the value was obtained rather than leaving it implicit:

```python
value_binding: Literal["literal", "dynamic", "absent"]
```

`literal` — statically resolved. `dynamic` — the argument is present but assembled from config, environment, or a variable. `absent` — not supplied at the call site, so the provider default applies.

`dynamic` sites join as *possible* impact and route to alert-with-diagnosis rather than a pull request, reusing the §9 confidence gate rather than adding a second mechanism. They are not noise to be suppressed: an unresolvable model string with no evaluation baseline is the unpinned-fallback bug class of §11, and `absent` combined with a provider-side default change is the silent shift of §7.3.

#### Canonicalisation

`provider`, `resource`, and `operation` are lowercase dotted paths drawn from a controlled vocabulary, never free text — `openai` and `open-ai` resolving to different identities would silently halve every count in the system. `value` is stored verbatim as the provider writes it, since it is an opaque token the provider owns.

### 6.2 Tech stack

| Component | Technology | Rationale |
|---|---|---|
| Change detection workers | Python | LLM SDKs are Python-first |
| Code indexing | Python + tree-sitter | Best-in-class multi-language parsing bindings |
| SDK surface extraction (JS/TS) | TypeScript compiler API | `.d.ts` parsing is native to TS |
| Patch generation | Python + frontier model | Quality-critical, low volume |
| Verification harness | Python + Docker | Ephemeral sandboxes |
| GitHub App | TypeScript + Octokit | Native ecosystem |
| Dashboard | TypeScript + Next.js | — |
| Runtime collectors | Python and Node libraries | Import, not infrastructure |
| Database | Postgres + pgvector | One database; no separate vector store |
| Job queue | Postgres `SKIP LOCKED` | No Redis/Celery until scale demands it |
| Spec diffing | `oasdiff` (shell out) | 509 classified change types already implemented |
| Candidate file scan | `ripgrep` (shell out) | — |

**Explicitly deferred:** Go. The only legitimate future use is a network-level sidecar proxy for runtime collection. Start with per-language SDK wrapper libraries instead — a library is an import, a proxy is an infrastructure ask.

### 6.3 Repository layout

```
/engine        Python — detection, indexing, patching, verification
/app           TypeScript — GitHub App + Next.js dashboard
/collectors
  /python      runtime collector library
  /node        runtime collector library
/shared        JSON Schema → generates Pydantic + TS types
```

Define `ChangeEvent`, `CallSite`, and `SurfaceID` once in `/shared` as JSON Schema; generate both Pydantic models and TypeScript types. This prevents the specific class of bug where the Python engine and TS app disagree about a field name.

---

## 7. Change detection sources

Ranked by signal-to-effort. Each source emits normalised `ChangeEvent` records carrying `source` and `confidence` fields.

### 7.1 SDK artifact diffing (highest value, build first)

Download two published versions of a provider's SDK from npm or PyPI, extract the public surface, diff the surfaces.

- **TypeScript:** parse `.d.ts` via the TypeScript compiler API
- **Python:** AST walk over stubs and public modules

This free-rides on the provider's own code generation pipeline. It yields precise, machine-readable change sets — new parameters, removed fields, changed types, renamed methods — without depending on prose changelogs or accurate specs.

### 7.2 OpenAPI spec diffing

Shell out to `oasdiff`. Excellent where specs are public, versioned, and accurate. That set is smaller than expected and specs frequently lag the live API. Treat as supplement, not foundation.

### 7.3 Runtime drift detection (the differentiator)

Lightweight collector libraries wrap the customer's SDK client, sample responses, and reduce each to a **structural skeleton with all values discarded at the point of collection**.

Detects:
- New or removed fields
- Type changes
- Enum value expansion
- Nullability changes
- Status code distribution shifts
- `Sunset` and `Deprecation` headers (RFC 8594)
- Rate limit and latency shifts

**Implementation requirements (learned from existing drift tools):**
- Never compare raw responses — reduce to structure first
- Baseline over N observations before flagging
- Require a change to persist across multiple observations before alerting
- Treat first sighting of any endpoint as profile creation, not a finding

This is the only source that catches a change with **no artifact anywhere** — the silent server-side shift. It is also what makes patches verifiable (§9).

### 7.4 Email ingestion

Each customer receives a dedicated ingest address. Vendor notification emails are forwarded to it; Avert extracts structured change events (provider, endpoint, effective date, action required).

Low-tech, high-signal, and nobody is doing it. This is how deprecation news actually arrives today.

### 7.5 Changelog and documentation crawling

Necessary for coverage, lowest reliability, most LLM-dependent. Do it; do not build on it.

### 7.6 Corroboration

A change confirmed by two independent sources receives a higher confidence tier than a changelog mention alone. Confidence tiering is what makes safe PR gating possible.

---

## 8. Code indexing

### 8.1 The cost funnel

Never send whole repositories to an LLM. The funnel is both a quality and a cost architecture:

1. **`ripgrep`** — candidate file identification (SDK imports, URL literals, model strings, fetch calls). Free. Reduces ~1M tokens to ~30k of candidate windows.
2. **tree-sitter** — structured call site extraction from candidates. Free.
3. **Embeddings** — semantic search over ambiguous remainder. Negligible cost.
4. **Small model** — classification: "is this an external API call, to which provider?" High volume, easy task.
5. **Frontier model** — hard disambiguation only. Low volume.

Every call site resolved by static analysis rather than a model is one never paid for again, across every customer, forever. Static analysis is the cost moat.

### 8.2 Incremental re-indexing

**Non-negotiable from day one.** Index keyed on file content hash; on every push, re-index only changed files. This is the difference between roughly $2 and $40 per customer per month. Retrofitting it means rewriting the indexer.

### 8.3 Hard cases

Resolvable with types: SDK method calls in typed languages.
Requires LLM classification: raw `fetch` with templated URLs, endpoints assembled from config, string literals in YAML, calls inside generated or vendored code.

Avert reports confidence per call site rather than presenting uniform accuracy.

---

## 9. Verification — the moat

Patch *generation* is commodity; any frontier model can rewrite call sites given a migration guide. Patch *verification* is not.

Every pull request carries an evidence bundle:

| Evidence | Description |
|---|---|
| Contract tests | Generated tests for the changed surface |
| Traffic replay | Sampled production request shapes run against old and new code paths, with results diffed |
| Type check | Full typecheck result |
| Test suite | The repository's own tests, before and after |
| Blast radius | Explicit statement of files touched and criticality |
| Confidence score | Composite, with the inputs shown |

**Gating rule:**

- Confidence ≥ threshold → pull request with evidence bundle
- Confidence < threshold → alert with diagnosis, no pull request

The failure mode this prevents: a 90%-correct patch in a payments integration is worse than no patch, because it consumes review time and occasionally gets merged. The dominant failure mode of Dependabot is being ignored or disabled due to PR volume; Avert must generate fewer, better PRs.

---

## 10. Trust and security model

Repository access is the entire business. Losing it once loses it permanently.

**Principles:**

- **Read-only by default.** Write access is opt-in per repository, never org-wide by default.
- **Structure-only runtime collection.** Response values are discarded at the point of collection, inside the customer's own process, before anything leaves their network. This is stated prominently — it is both correct privacy posture and a materially easier security review.
- **No code retention.** Repositories are cloned into ephemeral storage, indexed, and discarded. Only the derived index (surface IDs, file paths, line numbers) is retained.
- **No cross-customer code leakage.** The cross-customer graph (§13) stores only aggregate surface usage counts, never code or identifiable usage patterns.
- **Neutral party, not vendor-installed.** A provider-installed agent with write access to a customer monorepo fails security review, and no organisation will accept ten such agents. One integration, one security review, one vendor of record.
- **Never a sales channel.** New-capability notifications are informational only, never pull requests.

Target compliance posture by Series A: SOC 2 Type II, penetration test report, documented data handling and retention.

---

## 11. Beachhead: LLM provider APIs

The first vertical is AI provider APIs, specifically **model deprecation**.

### Why this is the right wedge

- **The breaking change is a string literal, not a version number.** `model="gpt-4-0613"` is invisible to Dependabot, Renovate, every SBOM tool, and every spec differ. This is a genuine blind spot in the existing tooling stack, not a marginal improvement on it.
- **Hard dates and known migration targets.** The rare case where high-precision automated patching is genuinely achievable.
- **Nasty failure modes in both directions.** Hard failure on retirement, or silent quality degradation when a rolling alias resolves to a model that was never evaluated.
- **Wide and growing blast radius.** These calls now appear in nearly every production codebase, often in dozens of scattered locations.
- **Brutal change cadence.** Snapshot retirement measured in months, not years.
- **Competitive vacuum.** Multiple independent point solutions exist (GitHub Actions, CLI tools, community registries covering hundreds of models across a dozen-plus providers) — which proves the pain is real — but all stop at detection against a static registry. None offer runtime verification, eval-backed migration, cross-repository organisational views, or proof the swap is safe. The registry is trivially copyable; the verified migration is not.

### High-value detection case: unpinned fallback models

Retry routers and fallback chains typically hardcode unpinned model aliases. These are not on any deprecation calendar and not in the evaluation suite, so when a fallback actually fires it silently routes to whatever the alias resolves to that day, with no evaluation baseline. This is a specific, findable, high-severity bug class that no existing tooling flags. It is the cold-open demo.

### Expansion path

Same machinery, outward along change type: auth and OAuth changes → webhook payload changes → pagination changes → rate limit tier changes → payments, communications, and cloud providers.

Coverage strategy: be genuinely excellent at the 20–50 APIs that appear in most production codebases rather than shallow across thousands. SDK-diffing amortises across providers; bespoke per-provider integrations do not and must be avoided.

---

## 12. Competitive landscape

| Layer | Players | Why they don't close the gap |
|---|---|---|
| Package dependency bots | Dependabot, Renovate/Mend | Manifest-only. Blind to string literals and server-side change. Renovate runs on 1.3M+ hosted repositories — a serious distribution advantage if they move, but semantic code indexing is a different engineering discipline from manifest parsing. |
| Spec diffing | oasdiff, pb33f/openapi-changes, APInotes | No code awareness. Optic (YC-backed) archived January 2026 — spec-only tooling cannot help with third-party APIs or stale specs. |
| Runtime drift monitoring | FlareCanary, ShiftGraph, API Drift Alert, APIShift | Endpoint pollers with alert routing. Priced $19–149/month. No repository access, no knowledge of where the drifted field is consumed, no remediation. |
| SDK generation | Stainless, Speakeasy, Fern (Postman) | Provider-side. Structurally the most dangerous long-term — one product step from customer-side migration. Layer is consolidating; reported Stainless acquisition in 2026 created churn worth exploiting. |
| Agentic migration | FOSSA upgrade agent, coding agents generally | Dependency upgrades, not HTTP API changes. Will drift toward this. |
| LLM deprecation trackers | llmstatus.ai, llm-model-deprecation, llmaudit | Registry plus grep. No verification, no code index, no organisational view. |

### The unoccupied cell

|  | No code awareness | Code-aware |
|---|---|---|
| Manifest | — | Dependabot, Renovate |
| Spec diff | oasdiff, APInotes | *empty* |
| Runtime | FlareCanary, ShiftGraph | **empty** |
| Multi-source fused | *empty* | **empty — Avert** |

Everyone code-aware is manifest-only. Everyone with good detection is code-blind. The gap persists because closing it requires a code index *and* a change feed *and* the canonical identity to join them. Monitoring companies cannot easily add repository indexing (different trust model, security review they have never done at $19/month pricing). Dependency bots have never touched production traffic.

---

## 13. Differentiation, ranked by defensibility

1. **The join.** Competitors output "field X changed on endpoint Y." Avert outputs "field X changed on endpoint Y, consumed at `checkout/refunds.py:142` and `billing/webhooks.ts:88`, the first in your payment path, here is the patch." That distance is the distance between a $29/month utility and a platform. It is also the only version that can ever open a pull request.

2. **Multi-source fusion.** Better recall, and — more importantly — corroboration, which enables confidence tiering, which enables safe PR gating.

3. **Verified remediation.** The evidence bundle. Nobody has this.

4. **The cross-customer change graph.** Indexing many codebases against a canonical surface identity yields knowledge no single participant has: which providers ship undocumented changes most often, real-world migration duration, which endpoints are load-bearing ecosystem-wide. Compounding data asset, basis for provider-side revenue, and the only element here a well-funded competitor cannot replicate by shipping a feature.

---

## 14. Business model

### Pricing principle

**Do not anchor against dependency tooling.** "Dependabot for APIs" sets a mental price of $0–29/month, which is where every runtime drift tool landed and why none became companies. Price against incident cost and migration engineering hours instead.

### Structure

| Tier | Audience | Price | Includes |
|---|---|---|---|
| Free | Individual developers, OSS | $0 | Inventory, up to N repositories, detection alerts |
| Team | Series A–B | $500–1,000/mo | Full inventory, all change sources, alerts, limited PRs |
| Business | Series C+ | $2,000–5,000/mo | Unlimited PRs, runtime collector, SSO, audit log, SLA |
| Provider | API vendors (phase 3) | Custom | Migration campaign tooling, customer version visibility |

### Unit economics

**Shared costs** (amortised across all customers, independent of customer count):
- Change detection across 50 providers: ~$30–100/month total

**Per-customer costs:**
- Initial index of ~50 repositories: $10–30 one-time
- Incremental re-index: $1–3/month (scan changed files only)
- Patch generation: 5–20 events/month × $0.30–2 each
- Runtime drift analysis: near-zero (structural reduction is deterministic code, not LLM)

**Total: roughly $15–60 per customer per month** against a $500–5,000 price point. Gross margin above 90%.

**The failure mode that destroys this:** full repository re-scans with a frontier model on a schedule. That is 10–20× the cost and converts a software business into an inference reseller. If full re-scans appear, something upstream is architecturally wrong.

---

## 15. Roadmap

### Phase 0 — Validation (3 weeks, ~$50–95 in API credits)

Four experiments, each capable of killing or reshaping the plan:

| # | Question | Method | Decision rule |
|---|---|---|---|
| 1 | Is advance detection possible? | 20 APIs, 12 months of history, hand-label every breaking change; measure what fraction was discoverable pre-impact from a machine-readable source | >70% → static pipeline is core. <40% → runtime detection is the whole company; build the collector first |
| 2 | Can the inventory be built accurately? | Run extractor across 20 real repositories of varying quality; hand-label ground truth | <85% recall → inventory product does not stand up; everything downstream inherits the error |
| 3 | Are patches merge-ready? | 10 real historical breaking changes; experienced engineer grades merge-as-is / merge-with-edits / wrong | <70% merge-as-is → ship high-quality alerts with diagnosis; gate PRs behind confidence threshold |
| 4 | How do people actually find out? | 15 platform engineer conversations: "what's the last external API change that broke you, and how did you learn?" | Modal answer of "error rate spiked" or "a customer told us" confirms runtime-first and becomes marketing copy |

Be stingy on experiment 2 (high-volume, low-difficulty; if a cheap model fails, that is itself a finding). Be generous on experiment 3 (measuring the ceiling of patch quality — an underpowered model produces a pessimistically wrong kill signal).

Secure credits before starting: Anthropic and OpenAI startup programmes, AWS Activate / Google for Startups / Azure (cloud credits convert to inference via Bedrock and Vertex), GitHub Models free tier, open-weight models on cheap inference for the bulk classification layer.

### Phase 1 — Build (weeks 1–4)

| Week | Deliverable |
|---|---|
| 1 | Postgres schema + `SurfaceID`. Tree-sitter extractor (Python, TypeScript) targeting LLM API calls and model strings only. Run against 20 repositories → this *is* experiment 2 |
| 2 | SDK differ for AI providers + static model lifecycle registry. Both branches now exist; real join possible |
| 3 | Patch generation + verification harness. Run against 10 historical model deprecations → this *is* experiment 3 |
| 4 | Read-only GitHub App + inventory dashboard. This is the demo |

Runtime collection follows, once the static pipeline works and a customer with production traffic exists.

**Resist:** building the multi-provider abstraction layer in week 1. Hardcode OpenAI and Anthropic, get the full pipeline working end to end, then generalise once the seams are known from experience. Premature abstraction encodes wrong assumptions about what a "change" is.

### Phase 2 — Go to market (months 2–6)

- Free tier, open-source the model deprecation registry (drives adoption, is trivially copyable anyway, and the verified migration is the actual moat)
- Expand to auth, webhooks, pagination change types
- Ship runtime collector libraries
- Target: 10 paying design partners

### Phase 3 — Expansion (months 6–18)

- Broaden to payments, communications, cloud providers
- Ship the agent-facing feed and MCP server
- Launch provider-side product once consumer coverage supports the pitch: *"we can see 400 codebases using your v1 endpoint — want us to migrate them?"*

---

## 16. Metrics

**Primary:**
- **PR merge rate without modification.** The single metric. Below 70% the product generates work rather than removing it.

**Supporting:**
- **Silent-change catch rate** — changes detected that had no changelog entry anywhere. This is the number proving Avert is not a changelog scraper. It belongs in the YC application.
- **Time-to-detect relative to vendor announcement.** Negative is the goal for runtime detection.
- **Inventory coverage per repository** — gates everything downstream.
- **Alert-to-action rate** — proxy for alert fatigue.
- Cost per customer per month (must stay under ~$60).

---

## 17. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Alert fatigue → tool disabled | High | Asymmetric thresholds; PRs gated on confidence; fewer, better outputs |
| Coding agents absorb this as a feature | High | Layer 4 — become the data layer agents call, not their competitor |
| Renovate/Mend extends into semantic indexing | High | Different engineering discipline; runtime observation outside their product entirely. Timing bet, not a moat |
| Runtime drift tools add repository indexing | Medium | They are small and priced as utilities; the security review at $19/month pricing is a real barrier for them |
| SDK generation layer extends to customer codebases | Medium | They approach provider-first; Avert approaches consumer-first, where the cross-customer data asset accumulates |
| Coverage economics — per-provider work that doesn't amortise | Medium | SDK-diffing is generic; refuse bespoke per-provider integrations |
| "Optic already died doing this" | Medium | Optic diffed specs for APIs you own; Avert indexes code for APIs you don't own and observes them at runtime. Different signal, buyer, and failure mode. Have this answer ready |
| Patch quality below merge threshold | Medium | Experiment 3 answers this before the PR pipeline is built |
| Trademark conflict on "Avert" | Medium | Avert Pty Ltd (South Melbourne, AI development and data privacy, Antler-backed 2022) and Avert Network Services (managed IT) both trade under the name in adjacent sectors. Avert LLC holds registered marks in medical classes. Commission a Class 42 clearance search before incorporating or filing |
| npm/PyPI namespace | Low | npm `avert` is held by an abandoned HapiJS request sanitiser (v1.1.0, ~6 years stale, 0 dependents, 1 star). PyPI appears clear. Ship scoped as `@avert/*` or pursue a transfer request |
| SEO noise on "Avert" | Low | EPA's AVERT emissions tool and avert.org (HIV/AIDS charity) dominate generic search. Mitigate with a compound domain and a distinct product wordmark |

---

## 18. Open questions

1. Does experiment 1 favour static or runtime as the primary detection path? This determines build order.
2. What is the actual merge-as-is rate (experiment 3)? Determines whether Avert is a remediation product or a high-quality alerting product in year one.
3. Free tier boundary — where does inventory stop being free?
4. Does the API SBOM output have an independent vendor-risk buyer worth pursuing?
5. Is the provider-side product a second revenue line or a distraction? Revisit at 50 consumer customers.
6. Name — "Avert" is a working name, cleared informally against npm, PyPI and GitHub but not legally. Commission a Class 42 trademark clearance search before incorporating or filing. Confirm domain availability (`avert.dev`, `avert.sh`, `getavert.com`) in the same sitting.

---

## Appendix A — Positioning notes

**On the "Dependabot for APIs" comparison:** it is a legibility comp, not an architecture instruction. It buys instant comprehension, a proven behavioural precedent (engineers do merge bot PRs at scale), and an existing budget line. It costs a $0 price anchor, Dependabot's mixed reputation among practitioners, and — most dangerously — it points at the wrong architecture. Taken literally it produces a registry-plus-grep tool, which is exactly what the existing LLM deprecation point solutions are and exactly why none became companies.

Use it, then break it in the next sentence.

**On disagreeing with the YC RFS framing:** agree with the problem, disagree with the mechanism, and show the reasoning is empirical rather than contrarian.

- "Providers should apply changes, not just announce them" — agree entirely.
- "Install Stripe's update agent" — security review kills it. A vendor-installed bot with write access to a monorepo is a different trust question from a developer-installed one, and nobody accepts ten of them. Same goal, different topology.
- Note that Stripe is the RFS's own worst example: Stripe pins accounts to an API version specifically so they never have to ask customers to change code. The APIs that break you are the ones without that discipline, and the ones that changed behaviour without shipping a version at all.
- The RFS's evidence base (50 vendors, mostly early-stage) is precisely the segment that cannot pay — which is why Avert starts consumer-side.
