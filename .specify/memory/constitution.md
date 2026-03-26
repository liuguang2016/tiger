# Tigger Constitution

## Core Principles

### I. Data Integrity
Data accuracy is non-negotiable for trading systems. All external API responses MUST be validated before use. The system MUST implement fallback mechanisms when primary data sources fail.

**Rationale**: A-Share and crypto markets require reliable data. Users make financial decisions based on system data.

### II. Graceful Degradation
Long-running operations (screening 5000+ stocks) MUST run asynchronously in background threads. UI MUST remain responsive during data fetching. API failures MUST NOT crash the application.

**Rationale**: Users expect responsive interfaces even during heavy operations. Network/API issues are common and must not break functionality.

### III. Risk Management Enforcement
Trading modules MUST implement risk controls including stop-loss, tiered take-profit, and position sizing. Paper trading MUST be clearly distinguished from live trading.

**Rationale**: Real money is at stake. Risk controls prevent catastrophic losses.

### IV. Module Autonomy
Each service module (screener, trading, backtesting, data) MUST be self-contained with clear interfaces. Dependencies between modules MUST be explicit via function signatures.

**Rationale**: Enables independent testing, debugging, and future modifications without cascading effects.

### V. Observable Operations
All trading operations, data fetches, and strategy signals MUST be logged with sufficient detail for debugging and audit. Logs MUST include timestamps and relevant context.

**Rationale**: Trading systems require audit trails. Debugging without logs is impossible in production.

## Additional Constraints

### API Resilience
- **Snapshot Cache**: 30-minute TTL cache for A-share snapshots to handle rate limiting
- **Multi-source Fallback**: Stock data MUST try multiple sources (akshare EastMoney → Sina → cache)
- **Retry Logic**: Failed API calls MUST retry with exponential backoff (max 3 rounds)

### Security Requirements
- API keys for Binance MUST be stored securely (environment variables, not in code)
- Paper trading mode MUST be the default; live trading requires explicit opt-in
- Database (SQLite) stores no sensitive plaintext credentials

### Performance Standards
- Stock screening MUST complete within reasonable time (target: <10 minutes for 5000+ stocks)
- K-line data retrieval MUST use caching to minimize API calls
- Background threads MUST be daemon threads to allow clean shutdown

## Development Workflow

### Code Review
- All PRs/reviews MUST verify compliance with these principles
- Changes to trading/risk logic require explicit test coverage
- Breaking changes to data formats MUST update all consumers

### Testing Expectations
- Unit tests for individual service functions
- Integration tests for data flow between modules
- Manual verification for UI components (K-line charts, IndexBar)

### Complexity Justification
- Architectural complexity MUST be justified in plan.md
- YAGNI: Avoid over-engineering for hypothetical future requirements

## Governance

This constitution supersedes all other development practices. Amendments require:
1. Documentation of proposed change
2. Migration plan for existing code
3. Review and approval

Version updates follow semantic versioning:
- **MAJOR**: Backward-incompatible principle removals or redefinitions
- **MINOR**: New principles or materially expanded guidance
- **PATCH**: Clarifications, wording, typo fixes

All team members MUST use `.specify/` templates for feature planning. Runtime development guidance is in `CLAUDE.md`.

**Version**: 1.0.0 | **Ratified**: 2026-03-26 | **Last Amended**: 2026-03-26
