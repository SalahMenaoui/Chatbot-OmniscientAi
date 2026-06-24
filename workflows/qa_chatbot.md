# Workflow: qa_chatbot

## Objective
Test the chatbot against a standard set of questions to verify it responds correctly,
stays on topic, and accurately represents the business.

## Inputs Required
- Client name
- `clients/<client_name>/chatbot/config.json` — must contain the system prompt
- `ANTHROPIC_API_KEY` set in `.env`

## ⚠️ API Cost Warning
This step calls the Claude API (claude-haiku for economy). Each run sends ~10 questions.
**Confirm with me before running.**

## Steps

### 1. Verify inputs
- Confirm `clients/<client_name>/chatbot/config.json` exists and contains a `systemPrompt`.
- Confirm `REVIEW_NEEDED.md` has been deleted (manual review is complete).
- If review file still exists, stop and remind me to complete the review first.

### 2. Run QA tests
```
python tools/qa_test.py <client_name>
```

To use custom questions instead of the default set:
```
python tools/qa_test.py <client_name> path/to/questions.txt
```

Custom questions file format: one question per line.

### 3. Review results
Open `clients/<client_name>/qa_results.md` and evaluate each answer:

**Pass criteria:**
- Answers questions about the business accurately
- Uses information from the system prompt (not hallucinated)
- Maintains the right tone and persona
- Politely deflects off-topic questions
- Mentions contact/booking info when relevant

**Fail criteria:**
- Invents facts not in the system prompt
- Answers off-topic questions as if it's a general assistant
- Gives wrong contact info, hours, or pricing
- Sounds robotic or generic

### 4. Report findings
Summarize results to me:
- Total pass/fail ratio
- Any answers that need attention (quote them)
- Suggested adjustments to the system prompt if needed

### 5. Iterate if needed
If issues are found:
1. Adjust `clients/<client_name>/chatbot/config.json` → `systemPrompt`
2. Re-run QA: `python tools/qa_test.py <client_name>`
3. Report again

Only proceed to delivery when results are satisfactory.

## Expected Output
- `clients/<client_name>/qa_results.json` — raw results
- `clients/<client_name>/qa_results.md` — human-readable report

## Edge Cases
- **All answers look generic** — system prompt likely not loaded correctly; check `config.json`.
- **Wrong business info in answers** — the scraped data was incomplete; update system prompt manually.
- **API error during QA** — report error, do not retry automatically.

## Next Step
Once QA passes → `workflows/deliver_chatbot.md`
