# Changelog

## 0.2.0

- Opening the database makes its parent folder in a worker thread (`asyncio.to_thread`), no longer on the event loop. No API change.
