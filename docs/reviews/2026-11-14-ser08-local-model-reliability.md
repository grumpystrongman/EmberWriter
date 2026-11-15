# SER-08 local-model reliability review — 2026-11-14

Scope: synthetic local-model diagnostics and writing stream transport. No proprietary source text or actual model inference was used in this work.

- Benchmark cases now have a wall-clock timeout in addition to HTTP inactivity limits. An overall timeout retains completed results and marks remaining cases `not_run`; it cannot report a pass. Results include the SHA-256 of the canonical serialized case set and configured deadlines. The hash identifies cases, not model weights, software versions, or a complete reproducibility receipt.
- Writing streams require Ollama's completion marker and have first-content, inter-content, and 30-minute total stream deadlines. Empty or metadata events do not reset the content watchdog. Disconnect cancellation behavior is covered by existing diagnostic tests; a delivered partial delta may already be visible before a stream failure.
- Synthetic tests cover wall timeouts, preserved partial evidence, missing completion, empty event trickles, continuous-output total deadline, and unsupported-answer grading requiring an empty quote.

Validation: from `backend`, `py -3.14 -m pytest tests/test_series_model_evidence_benchmark.py tests/test_local_model_stream_reliability.py tests/test_series_model_probe.py tests/test_series_model_readiness.py tests/test_series_model_stream_probe.py -q --basetemp=../.test-temp-ser08-5` — 34 passed. Initial default Python lacked pytest; default temporary directory was inaccessible, so the successful run used a workspace-local temporary directory.

Limits: no actual Ollama model run, throughput measurement, long-form or real-series evaluation, model digest capture, independent human review, or release certification was performed. The stream deadline covers streaming after model lookup/gate acquisition, not queue waiting or all preparation. The battery remains a narrow synthetic diagnostic and cannot verify canon or establish literary quality.
