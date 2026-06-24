# Workflow: deliver_chatbot

## Objective
Generate the final embeddable snippet and package everything in the client's folder
ready for delivery.

## Inputs Required
- Client name
- `clients/<client_name>/chatbot/` — personalized chatbot (QA passed)
- QA results reviewed and approved

## Steps

### 1. Verify QA is complete
- Confirm `qa_results.md` exists and was reviewed.
- Confirm I have explicitly approved the QA results before proceeding.

### 2. Final config check
Before generating the snippet, confirm with me:
- Is the `proxyUrl` in `config.json` set to the correct production endpoint?
  (Default is `/api/chat` — this must match the client's server setup)
- Are brand colors correct?
- Is the welcome message finalized?

### 3. Generate the snippet
```
python tools/generate_snippet.py <client_name> \
  --proxy-url https://web-production-42cf20.up.railway.app/api/chat \
  --chatbot-url https://web-production-42cf20.up.railway.app/clients/<client_name>/chatbot/
```
This creates:
- `clients/<client_name>/snippet.js` — the embeddable widget script
- `clients/<client_name>/DELIVERY.md` — client setup instructions

### 4. Deploy to Railway (required)
```
git add clients/<client_name>/
git commit -m "<client_name>: deploy"
git push
```
Railway redeploys automatically in ~30 seconds. The chatbot is then live at:
`https://web-production-42cf20.up.railway.app/clients/<client_name>/chatbot/`

### 4. Review the snippet
Open `snippet.js` and verify:
- `CHATBOT_URL` placeholder is visible (client must update this)
- `PRIMARY_COLOR` matches the brand
- `BOT_NAME` is correct

### 5. Package summary
Report the final delivery package contents:
```
clients/<client_name>/
├── sources.txt          ← original URLs
├── scraped_data.json    ← raw scraped data
├── system_prompt.txt    ← generated prompt
├── chatbot/             ← full chatbot application
│   ├── index.html
│   ├── style.css
│   ├── chatbot.js
│   └── config.json      ← contains system prompt + brand config
├── snippet.js           ← embed snippet for client's website
├── DELIVERY.md          ← setup instructions for client
└── qa_results.md        ← QA report (optional to share)
```

### 6. Deliver
Items to send to the client:
1. The `chatbot/` folder — host on their server
2. The `snippet.js` file — paste before `</body>` on their site
3. The `DELIVERY.md` instructions

**Remind me to:**
- Update `CHATBOT_URL` in `snippet.js` after hosting
- Set up the server-side API proxy before going live
- Test in a real browser after deployment

## Expected Output
- `clients/<client_name>/snippet.js` — final deliverable
- `clients/<client_name>/DELIVERY.md` — setup instructions

## Important Notes
- The API key is NEVER in the snippet or client-side code.
- The chatbot will not work without a server-side proxy.
- The `chatbot/` folder must be accessible via HTTPS for production use.

## Pipeline Complete ✓
```
scrape_sources → generate_prompt → build_chatbot → [manual review] → qa_chatbot → deliver_chatbot
```
