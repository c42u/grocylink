# Changelog

All notable changes to Grocylink will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.3] - 2026-02-20

### Fixed

- **CalDAV bidirectional chore sync broken on many servers** (e.g. PrivateEmail, Dovecot-based):
  - Replaced `calendar.search(todo=True)` with `calendar.todos(include_completed=True)` in
    `_find_vtodo_by_uid` and `_sync_caldav_to_grocy`. Several CalDAV servers exclude completed
    VTODOs from REPORT query results by default, which caused completed reminders to be invisible
    to the sync engine — marking a reminder done never triggered chore execution in Grocy.
  - `_find_vtodo_by_uid` no longer misses completed VTODOs, preventing duplicate chore entries
    from being created in CalDAV after a chore was marked done in a client like Apple Reminders.
  - Extended the update check in `_sync_chores_to_caldav` to also compare the due date
    (`next_estimated_execution_time`) in addition to the chore name. Previously, only a name
    change triggered a CalDAV update — meaning the due date in CalDAV was never refreshed after
    a chore was executed in Grocy. After execution, the new due date is now correctly propagated
    to CalDAV and the VTODO status is reset to `NEEDS-ACTION` on the next sync cycle.

---

## [1.0.0] - 2026-01-01

### Added

- Initial release of Grocylink
- Dashboard with real-time overview of expiring, expired and missing products
- 6 notification channels: Email (SMTP), Pushover, Telegram, Slack, Discord, Gotify
- Individual warning days per product
- CalDAV synchronization: bidirectional sync of Grocy tasks and chores
- New tasks created in CalDAV clients are automatically added to Grocy
- Automatic scheduler with configurable interval
- Test function for each notification channel
- Full notification log with filtering and sorting
- Encrypted storage of all passwords and API keys (Fernet/AES)
- Dark/Light mode (automatic + manual toggle)
- Multilingual support: German and English
- Non-root Docker container with minimal privileges
