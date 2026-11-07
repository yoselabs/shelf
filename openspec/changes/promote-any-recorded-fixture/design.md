# Design

A typed Case holds group, case, directory and metadata. Discovery visits sorted group and case directories
and requires meta.json. JSON uses UTF-8, indent=1 and a final newline. Recording takes complete filenames.
Golden comparison raises GoldenMismatch with a unified diff, including for missing files; explicit update
writes actual text. Scrubbing replaces longest nonempty values first. Environment updates are opt-in.
No runtime dependencies, consumer imports, atomicity or locking. Callers own paths and concurrency.
