# Real writing acceptance

`scripts/run-writing-acceptance.ps1` exercises EmberWriter's actual local Ollama writing path repeatedly instead of relying on scripted model fixtures.

The default suite runs 10 generations and requires at least 90% to pass. It checks the author word ceiling, direct-delivery evidence, prose degeneration, completion, and internal-marker leakage. The harness never prints or saves generated manuscript prose; it stores only metrics and output hashes in `.ember/acceptance/writing-acceptance-latest.json`.

The harness automatically pulls the configured baseline creative/RP model when no recognized creative model is installed. Use `-PromptFile` to test a private author prompt without committing it to the repository.
