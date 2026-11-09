# Generation Access

**Without usable `ark-mcp`, deliver prompts instead of starting generation.**
Apply this contract before generation, production intake or Studio setup. It
takes precedence over older skill recipes that permit MCP-to-CLI fallback.
This is an agent instruction contract, not a new runtime mode or CLI flag.

## Connection And Intent

Check the current agent's exposed tools with read-only tool discovery. A
repository configuration, installed CLI, environment key or previous session
does not prove that `ark-mcp` is connected. Usable means the relevant tool is
exposed and its verified model, operation and required parameters can satisfy
the request. Missing tools, authentication failures and incompatible capabilities
make that operation unavailable or unusable. Never submit a paid probe merely
to check connectivity, and never invent unsupported parameters.

Connection is not permission. A prompt-only request stays prompt-only even when
MCP is usable. Preserve explicit generation consent for the current scope; do
not repeat consent for already authorized actions or carry it into unrelated
tasks. `review_mode` controls review depth and `approval_mode` controls creative
selection; neither enables generation or authorizes a transport fallback.

| MCP availability | Request | Action |
| --- | --- | --- |
| Any | Prompt-only request | Prompt handoff |
| Unavailable | No explicit alternative transport | Prompt handoff |
| Unusable | No explicit alternative transport | Prompt handoff |
| Usable | No generation consent | Prompt handoff |
| Usable | Explicit generation scope | MCP generation with existing safeguards |
| Any | Explicit Ark CLI generation | Ark CLI generation if usable; otherwise prompt handoff |
| Any | Explicit HTTP/curl generation | HTTP generation if securely configured; otherwise prompt handoff |

Never automatically fall back to Ark CLI, direct HTTP/curl or another generation
service when MCP is missing or unusable. A generic "generate this" or "use agent
mode" does not select an alternative transport. "Generate this with Ark CLI"
does. Explicit HTTP/curl retains the existing secure runtime-configuration
requirement. Do not install tools, configure credentials or start authentication
just to deliver prompts; those setup actions require their own requested scope.
If explicitly requested alternatives conflict with a prompt-only instruction,
clarify the intended scope before submission.

## Prompt Handoff

Return paste-ready prompt text, ordered reference bindings and separate model parameters
in chat. State briefly that generation was not run because usable MCP or
generation consent is missing. Describe missing references as inputs the user
must supply, not acquired or approved assets. Mark unverified capabilities and
required inputs honestly; do not present speculative settings as verified.

No Studio initialization, production manifests, task registration, asset
generation, production locks or render pipeline is required for prompt delivery.
Keep brief, shot and performance direction inline when needed. Save prompt drafts only when requested.
Do not invent task IDs, approvals, review evidence or generated outputs.
Prompt drafting still preserves rights, consent, exact dialogue and claims.
Explicitly requested repository maintenance, analysis, local editing/rendering
of existing assets and platform administration remain in scope without MCP;
they do not authorize new generation or an automatic generation fallback.

## Generation And Recovery

Authorized generation retains the [production policy](production-policy.md):
registration before submission, immutable prompts, current reference hashes,
capability checks, native draft-first video, required review, rights/consent,
creative selections, local persistence and duplicate-submission protection.

After possible submission, connection loss is recovery, not a new generation:

| Existing operation | Action |
| --- | --- |
| Known provider task ID | Resume or reconcile that task; no new submission |
| Unknown submission acceptance | Preserve submission_unknown; reconcile before any retry |
| Completed task, failed download | Retry the existing artifact download; do not regenerate |

Keep registry records, task IDs and historical hashes intact. When tools are
unavailable, report recovery as pending instead of silently abandoning the job.
An explicitly requested alternative may inspect or download the same task if
supported; it never authorizes a duplicate submission. A replacement after
verified terminal failure needs its own authorized scope and prepared operation.
