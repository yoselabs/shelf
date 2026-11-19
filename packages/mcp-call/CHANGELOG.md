# mcp-call CHANGELOG

## mcp-call-v0.2.0

- Redirect policy implicit (`follow_redirects=True`, httpx's 20 hops) => explicit and bounded: still followed (a 307 moves `/mcp/` to `/mcp`), at most 3 hops. Timeout was already explicit. No response body cap: replies are small JSON-RPC bodies read whole; a cap would bound nothing the library buffers anyway.
