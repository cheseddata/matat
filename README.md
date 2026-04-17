# Operator Feedback

Auto-generated tickets from the sandbox PC's in-browser "Report issue" widget.

Each ticket lives at `tickets/<id>/` and contains:

- `ticket.json` — issue text, user, URL, timestamp, browser console errors, user-agent
- `screenshot.png` — full-page html2canvas render of what the operator saw

Another Claude can clone this branch standalone:

```
git clone -b operator-feedback --single-branch \
    https://github.com/cheseddata/matat.git matat-feedback
```

…and read every ticket without pulling the full code repo.

Pushed automatically by `/claude/feedback/submit` in a background thread
after each operator report.
