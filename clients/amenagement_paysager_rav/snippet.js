/**
 * Aménagement Paysager AV Chatbot Widget
 * Generated: 2026-06-23
 * Client: amenagement_paysager_rav
 *
 * INSTALLATION:
 * Paste this entire script tag just before </body> in your website's HTML.
 * Make sure to host the chatbot files and set CHATBOT_URL below.
 *
 * <script src="https://your-domain.com/chatbot/snippet.js"></script>
 */

(function () {
  var CHATBOT_URL = "https://YOUR_DOMAIN/clients/amenagement_paysager_rav/chatbot/";  // ← UPDATE THIS to where you host the chatbot files
  var PRIMARY_COLOR = "#6ab04c";
  var BOT_NAME = "Aménagement Paysager AV";
  var AVATAR_INITIAL = "A";

  // Inject iframe styles
  var style = document.createElement("style");
  style.textContent = [
    "#chatbot-launcher {",
    "  position: fixed; bottom: 24px; right: 24px; z-index: 99999;",
    "  width: 56px; height: 56px; border-radius: 50%;",
    "  background: " + PRIMARY_COLOR + "; color: #fff;",
    "  border: none; cursor: pointer; box-shadow: 0 4px 20px rgba(0,0,0,0.2);",
    "  font-size: 24px; display: flex; align-items: center; justify-content: center;",
    "  transition: transform 0.2s;",
    "}",
    "#chatbot-launcher:hover { transform: scale(1.08); }",
    "#chatbot-iframe-wrapper {",
    "  display: none; position: fixed; bottom: 92px; right: 24px; z-index: 99998;",
    "  width: 420px; height: 620px; max-width: calc(100vw - 32px);",
    "  max-height: calc(100vh - 108px);",
    "  border-radius: 16px; overflow: hidden;",
    "  box-shadow: 0 8px 40px rgba(0,0,0,0.2);",
    "  animation: chatSlideIn 0.25s ease;",
    "}",
    "@keyframes chatSlideIn {",
    "  from { opacity: 0; transform: translateY(16px); }",
    "  to   { opacity: 1; transform: translateY(0); }",
    "}",
    "#chatbot-iframe { width: 100%; height: 100%; border: none; }",
  ].join("\n");
  document.head.appendChild(style);

  // Create launcher button
  var btn = document.createElement("button");
  btn.id = "chatbot-launcher";
  btn.title = "Chat with " + BOT_NAME;
  btn.innerHTML = "&#x1F4AC;";
  document.body.appendChild(btn);

  // Create iframe wrapper
  var wrapper = document.createElement("div");
  wrapper.id = "chatbot-iframe-wrapper";

  var iframe = document.createElement("iframe");
  iframe.id = "chatbot-iframe";
  iframe.src = CHATBOT_URL;
  iframe.allow = "clipboard-write";
  wrapper.appendChild(iframe);
  document.body.appendChild(wrapper);

  // Toggle open/close
  var isOpen = false;
  btn.addEventListener("click", function () {
    isOpen = !isOpen;
    wrapper.style.display = isOpen ? "block" : "none";
    btn.innerHTML = isOpen ? "&#x2715;" : "&#x1F4AC;";
    btn.title = isOpen ? "Close chat" : ("Chat with " + BOT_NAME);
  });

  // Close on outside click
  document.addEventListener("click", function (e) {
    if (isOpen && !wrapper.contains(e.target) && e.target !== btn) {
      isOpen = false;
      wrapper.style.display = "none";
      btn.innerHTML = "&#x1F4AC;";
    }
  });
})();
