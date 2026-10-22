# Brand Library Fixtures

This directory contains offline test fixtures for local development, unit tests, and the offline benchmark.

## Important Notice

The policy fixture `nimbus_db.json` represents a **fictional brand** ("Nimbus Cloud") created exclusively for local testing, offline test suites, and deterministic engine benchmarks.

- **Never treat `nimbus_db.json` as a production policy source.**
- Production brand rules, approved facts, and access policies are strictly retrieved from the authoritative Supabase integration.
- If Supabase connectivity fails or credentials are not supplied, production requests must return an operational failure or incomplete status rather than falling back to this fixture.
