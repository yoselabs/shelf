# mcp-feedback CHANGELOG

## mcp-feedback-v0.3.1

- Report POST: timeout only => explicit `follow_redirects=False` (a redirect would resend the `X-Api-Key` header to another host) and the reply body is never read (`stream`, returns at the headers), so no body size can matter. Delivery stays best-effort; nothing a caller sees changes.
