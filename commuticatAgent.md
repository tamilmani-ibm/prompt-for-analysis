# Summary Generator Toolkit

A reusable guide for turning raw context (chat threads, emails, or meeting notes) into clear, structured summaries. Paste your context under the relevant section's "Input" placeholder and follow the format.

---

## 1. Message / Chat Summary

**Use for:** Slack threads, group chats, WhatsApp/Teams conversations.

**Input:**
```
[Paste raw message thread here]
```

**Output format:**
```markdown
### Chat Summary — [Topic/Channel Name]
**Participants:** [Names]
**Date/Time:** [If known]

**Key Points:**
- Point 1
- Point 2

**Decisions Made:**
- Decision 1

**Open Questions / Unresolved:**
- Question 1

**Action Items:**
- [ ] Task — Owner — Due date
```

---

## 2. Email / Mail Summary

**Use for:** Single emails or email threads/chains.

**Input:**
```
[Paste email(s) here]
```

**Output format:**
```markdown
### Email Summary — [Subject Line]
**From:** [Sender] | **To:** [Recipient(s)]
**Date:** [Date]

**Purpose of Email:**
One or two lines on why this email was sent.

**Key Information:**
- Detail 1
- Detail 2

**Requests/Asks:**
- What the sender wants from the recipient

**Action Items:**
- [ ] Task — Owner — Due date

**Suggested Reply Tone:** [e.g., Confirm, Decline, Ask for clarification]
```

---

## 3. Meeting Summary

**Use for:** Meeting transcripts, notes, or recordings (transcribed).

**Input:**
```
[Paste meeting transcript/notes here]
```

**Output format:**
```markdown
### Meeting Summary — [Meeting Title]
**Date:** [Date] | **Attendees:** [Names]
**Duration:** [If known]

**Agenda / Topics Discussed:**
1. Topic 1
2. Topic 2

**Key Discussion Points:**
- Point 1 (mention who raised it, if relevant)
- Point 2

**Decisions Made:**
- Decision 1

**Action Items:**
| Task | Owner | Due Date |
|------|-------|----------|
|      |       |          |

**Next Steps / Follow-up Meeting:** [Date or TBD]
```

---

## How to Use This File

1. Pick the section matching your content type (message, email, or meeting).
2. Paste the raw context into the **Input** block.
3. Ask Claude (or any assistant): *"Summarize this using the [message/email/meeting] format from my template."*
4. Fill in / adjust the generated output as needed.

**Tip:** For recurring use, keep this file handy and just swap the pasted content — the structure stays consistent every time, making summaries easy to scan and compare across weeks.
