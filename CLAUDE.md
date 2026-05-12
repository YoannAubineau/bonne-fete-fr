# Project conventions

## Em dashes are forbidden

The em dash character (Unicode codepoint U+2014; often produced by autocorrect from `--`, or via `Alt+Shift+-` on macOS) must not appear anywhere in this project: not in code, comments, identifiers, user-facing strings (French or English), prose docs (`SPEC.md`, `README.md`), iCalendar descriptions, HTML, or YAML workflows.

Replace them with a colon ` : `, surrounding commas ` , `, or parentheses `(...)`, depending on the intended meaning.

En dashes (U+2013) remain allowed for numeric ranges (e.g. `50–100`).
