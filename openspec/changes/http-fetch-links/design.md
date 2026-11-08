# Design

Use async bounded workers, each awaiting cancellable DNS and curl_cffi transport. Pin validated addresses with CURLOPT_RESOLVE while retaining TLS hostname verification; refuse mixed public/private DNS answers and unexpected connected peers. Fresh sessions disable proxies and automatic redirects. NOBODY plus CUSTOMREQUEST checks headers for both HEAD and GET without a streaming background task. DNS runs in a child process because stdlib executor resolution cannot be cancelled; cancellation kills and reaps that child. Inject resolver, opener and monotonic clock for offline scenarios.

Alive means a successful response below 400; HTTP errors and transport failures are dead with a reason. Unknown is reserved for checks unfinished at the batch deadline. Batch cancellation joins all workers. No results cache.
