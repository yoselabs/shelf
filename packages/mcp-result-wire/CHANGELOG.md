# mcp-result-wire CHANGELOG

Arrow-notation, AI-facing: `old shape => new shape`.

## mcp-result-wire-v0.3.0 (breaking)

- `FormatRoutingMiddleware(plans, consumer, compact=, structured_output=)` => `FormatRoutingMiddleware(plans, consumer)`. The two constructor flags chose a compressed or marker-only wire result (Article IX: one behaviour, no output-shape switch). Both removed with their code; no shelf consumer passed them (a2kay's use-case needs `plans` and `consumer` only; not checked against a2kay's own source). Default behaviour is unchanged: `content` re-derived from the plan, `structured_content` kept whole. Migration: a consumer that needs a different wire shape writes its own middleware.
