# Workflow: build_chatbot

## Objective
Copy the base chatbot template into the client's folder and inject the generated system prompt.

## Inputs Required
- Client name
- `clients/<client_name>/system_prompt.txt` — must exist (run `generate_prompt` first)
- `templates/base_chatbot/` — base template must be intact

## Steps

### 1. Verify inputs
- Confirm `system_prompt.txt` exists.
- Confirm `templates/base_chatbot/` contains all 4 files: `index.html`, `style.css`, `chatbot.js`, `config.json`.
- If anything is missing, stop and report.

### 2. Run the injector
```
python tools/inject_prompt.py <client_name>
```
This will:
- Copy `templates/base_chatbot/` → `clients/<client_name>/chatbot/`
- Inject the system prompt into `clients/<client_name>/chatbot/config.json`
- Create `clients/<client_name>/REVIEW_NEEDED.md` with a checklist

### 3. Flag for manual review
After running, report the following to me:
- Confirm the chatbot folder was created.
- Show the auto-detected `botName` and `welcomeMessage` from the config.
- List items from `REVIEW_NEEDED.md` so I know what to check.

### 4. Wait for manual review
**Do not proceed to QA until I confirm the review is done.**
I will manually:
- Adjust brand colors in `config.json` if needed
- Fix the system prompt if needed
- Set the `proxyUrl` if already known
- Delete `REVIEW_NEEDED.md` when satisfied

## Expected Output
- `clients/<client_name>/chatbot/` — complete personalized chatbot, ready to test
- `clients/<client_name>/REVIEW_NEEDED.md` — manual review checklist

## Edge Cases
- **`chatbot/` folder already exists** — the tool will overwrite it. Warn me before proceeding if I haven't explicitly said to overwrite.
- **Bot name looks wrong** — flag it and suggest an alternative from the scraped data.

## Next Step
After manual review is complete → `workflows/qa_chatbot.md`
