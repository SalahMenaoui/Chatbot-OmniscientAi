# Workflow: generate_prompt

## Objective
Use the scraped data to generate a rich, personalized system prompt for the client's chatbot.

## Inputs Required
- Client name
- `clients/<client_name>/scraped_data.json` — must exist (run `scrape_sources` first)
- `ANTHROPIC_API_KEY` set in `.env`

## ⚠️ API Cost Warning
This step calls the Claude API (claude-sonnet-4-6). **Confirm with me before running if you haven't already.**

## Steps

### 1. Verify inputs
- Check `clients/<client_name>/scraped_data.json` exists and is non-empty.
- Check `.env` contains `ANTHROPIC_API_KEY`.
- If either is missing, stop and report the issue.

### 2. Run the generator
```
python tools/generate_system_prompt.py <client_name>
```

### 3. Review the output
Open `clients/<client_name>/system_prompt.txt` and check:
- Does it accurately represent the business?
- Is all key information present (services, hours, contact, tone)?
- Are there any hallucinated facts that weren't in the scraped data?
- Does the tone match the business's style?

Flag any issues in your response before proceeding.

### 4. Report
- Confirm `system_prompt.txt` was created.
- Summarize what information the prompt covers.
- List anything that was missing from the scraped data that weakens the prompt.

## Expected Output
- `clients/<client_name>/system_prompt.txt` — complete personalized system prompt

## Edge Cases
- **Scraped data is too thin** — generate what's possible, flag the gaps explicitly.
- **API error** — report the error, do not retry without confirmation.
- **Client has unusual business type** — adapt the prompt structure accordingly.

## Next Step
Once complete, proceed to → `workflows/build_chatbot.md`
