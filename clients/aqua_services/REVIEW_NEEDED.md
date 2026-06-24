# Manual Review Checklist — aqua_services

Before proceeding to QA, review the following:

- [ ] Open `chatbot/config.json` and verify the system prompt reads naturally
- [ ] Check `botName` and `welcomeMessage` are correct
- [ ] Adjust `primaryColor` / `secondaryColor` to match brand colors
- [ ] Remove any hallucinated details from the system prompt
- [ ] Add any missing info the scraper may have missed
- [ ] Verify contact info (phone, email, address) is accurate
- [ ] Set `proxyUrl` in config.json to the client's server endpoint

Once satisfied, delete this file and run workflows/qa_chatbot.md.
