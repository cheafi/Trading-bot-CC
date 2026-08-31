# AGENTS.md

This file provides guidance to agents when working with code in this repository.

- Settings View Pattern: When working on `SettingsView`, inputs must bind to the local `cachedState`, NOT the live `useExtensionState()`. The `cachedState` acts as a buffer for user edits, isolating them from the `ContextProxy` source-of-truth until the user explicitly clicks "Save". Wiring inputs directly to the live state causes race conditions.

- **Four Questions PR gate (IDOS):** Before proposing or implementing any CC X feature, answer convincingly: (1) What do we know better? (2) What uncertainty does it reduce? (3) How does it improve future capital allocation? (4) What complexity can be removed? Every surface must serve at least one of Know / Believe / Doubt / Act. If a change cannot answer any → reject or do not build. Full gate → [`docs/CC_X_INVESTMENT_COMMITTEE_RESOLUTION.md`](docs/CC_X_INVESTMENT_COMMITTEE_RESOLUTION.md).
