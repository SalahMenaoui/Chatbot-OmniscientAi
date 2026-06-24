/**
 * chatbot.js — AI Chatbot Widget Core
 *
 * Loads config.json, applies full theme via CSS variables,
 * renders markdown, shows typing indicator, proxies to Claude API.
 *
 * SECURITY: API key is NEVER in client JS — all calls go to /api/chat (server-side proxy).
 */

(async function () {
  "use strict";

  // ── Load config ──────────────────────────────────────────────────
  let config = {};
  try {
    const res = await fetch("config.json?v=" + Date.now());
    if (!res.ok) throw new Error("config.json not found");
    config = await res.json();
  } catch (e) {
    console.warn("[Chatbot] Could not load config.json, using defaults.", e);
  }

  const {
    botName        = "Assistant",
    welcomeMessage = "Hi! How can I help you today?",
    placeholder    = "Type your message...",
    quickReplies   = [],
    proxyUrl       = "/api/chat",
    model          = "claude-haiku-4-5-20251001",
    maxTokens      = 1024,
    systemPrompt   = "You are a helpful assistant.",
    avatarInitial  = "A",
    avatarUrl      = null,
    avatarInvert   = false,
    googleFontsUrl = null,
    fontFamily     = null,
    // Color tokens
    colorPrimary          = null,
    colorPrimaryDark      = null,
    colorPrimaryContrast  = null,
    colorBg               = null,
    colorSurface          = null,
    colorSurface2         = null,
    colorText             = null,
    colorTextMuted        = null,
    colorBorder           = null,
    colorBotBubble        = null,
    colorBotText          = null,
    colorUserBubble       = null,
    colorUserText         = null,
    colorHeaderBg         = null,
    colorHeaderText       = null,
    colorHeaderSubtext    = null,
    // Shape
    radiusBubble  = null,
    radiusInput   = null,
    radiusSend    = null,
    // Avatar
    colorAvatarBg = null,
  } = config;

  // ── Google Fonts ─────────────────────────────────────────────────
  if (googleFontsUrl) {
    document.getElementById("google-fonts").href = googleFontsUrl;
  }

  // ── Apply CSS variables ───────────────────────────────────────────
  const r = document.documentElement.style;
  const set = (v, val) => { if (val) r.setProperty(v, val); };

  set("--font-family",            fontFamily);
  set("--color-primary",          colorPrimary);
  set("--color-primary-dark",     colorPrimaryDark);
  set("--color-primary-contrast", colorPrimaryContrast);
  set("--color-bg",               colorBg);
  set("--color-surface",          colorSurface);
  set("--color-surface-2",        colorSurface2);
  set("--color-text",             colorText);
  set("--color-text-muted",       colorTextMuted);
  set("--color-border",           colorBorder);
  set("--color-bot-bubble",       colorBotBubble);
  set("--color-bot-text",         colorBotText);
  set("--color-user-bubble",      colorUserBubble);
  set("--color-user-text",        colorUserText);
  set("--color-header-bg",        colorHeaderBg);
  set("--color-header-text",      colorHeaderText);
  set("--color-header-subtext",   colorHeaderSubtext);
  set("--radius-bubble",          radiusBubble);
  set("--radius-input",           radiusInput);
  set("--radius-send",            radiusSend);
  set("--color-avatar-bg",        colorAvatarBg);

  // ── DOM setup ────────────────────────────────────────────────────
  document.getElementById("chat-bot-name").textContent = botName;
  document.getElementById("chat-input").placeholder    = placeholder;

  // Header avatar
  const headerAvatar = document.getElementById("chat-avatar");
  if (avatarUrl) {
    const img = document.createElement("img");
    img.src = avatarUrl;
    img.alt = botName;
    if (avatarInvert) img.className = "invert";
    headerAvatar.textContent = "";
    headerAvatar.appendChild(img);
  } else {
    headerAvatar.textContent = avatarInitial;
  }

  // Typing indicator avatar (mirrors header avatar)
  const typingAvatar = document.getElementById("typing-avatar");
  if (avatarUrl) {
    const img = document.createElement("img");
    img.src = avatarUrl;
    img.alt = botName;
    if (avatarInvert) img.className = "invert";
    typingAvatar.appendChild(img);
  } else {
    typingAvatar.textContent = avatarInitial;
  }

  // ── State ────────────────────────────────────────────────────────
  const history = [];
  let waiting   = false;

  // ── DOM refs ─────────────────────────────────────────────────────
  const messagesEl      = document.getElementById("chat-messages");
  const inputEl         = document.getElementById("chat-input");
  const sendBtn         = document.getElementById("send-btn");
  const errorBanner     = document.getElementById("error-banner");
  const typingIndicator = document.getElementById("typing-indicator");

  // ── Markdown renderer ─────────────────────────────────────────────
  function renderMarkdown(text) {
    return text
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/\*\*\*(.+?)\*\*\*/g, "<strong><em>$1</em></strong>")
      .replace(/\*\*(.+?)\*\*/g,     "<strong>$1</strong>")
      .replace(/\*(.+?)\*/g,         "<em>$1</em>")
      .replace(/^#{1,4}\s+(.+)$/gm,  "<strong>$1</strong>")
      .replace(/\n/g,                "<br>");
  }

  // ── Helpers ──────────────────────────────────────────────────────
  function scrollToBottom() {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function setWaiting(val) {
    waiting = val;
    sendBtn.disabled        = val;
    inputEl.disabled        = val;
    typingIndicator.hidden  = !val;
    if (val) scrollToBottom();
  }

  function showError(msg) {
    errorBanner.textContent = msg;
    errorBanner.hidden      = false;
    setTimeout(() => { errorBanner.hidden = true; }, 5000);
  }

  function renderMessage(role, text) {
    const wrapper = document.createElement("div");
    wrapper.className = `message ${role}`;

    // Avatar
    const avatar = document.createElement("div");
    avatar.className = role === "user" ? "message-avatar user-avatar" : "message-avatar";

    if (role === "bot" && avatarUrl) {
      const img = document.createElement("img");
      img.src = avatarUrl;
      img.alt = botName;
      if (avatarInvert) img.className = "invert";
      avatar.appendChild(img);
    } else {
      avatar.textContent = role === "bot" ? avatarInitial : "U";
    }

    // Bubble
    const bubble = document.createElement("div");
    bubble.className  = "message-bubble";
    bubble.innerHTML  = renderMarkdown(text);

    wrapper.appendChild(avatar);
    wrapper.appendChild(bubble);
    messagesEl.appendChild(wrapper);
    scrollToBottom();
  }

  // ── Send message ──────────────────────────────────────────────────
  async function sendMessage() {
    const text = inputEl.value.trim();
    if (!text || waiting) return;

    inputEl.value = "";
    renderMessage("user", text);
    history.push({ role: "user", content: text });
    setWaiting(true);

    try {
      const res = await fetch(proxyUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model,
          max_tokens: maxTokens,
          system:     systemPrompt,
          messages:   history,
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.error?.message || `HTTP ${res.status}`);
      }

      const data  = await res.json();
      const reply = data?.content?.[0]?.text ?? "Sorry, I couldn't process that.";
      history.push({ role: "assistant", content: reply });
      setWaiting(false);
      renderMessage("bot", reply);

    } catch (e) {
      setWaiting(false);
      showError("Something went wrong. Please try again.");
      console.error("[Chatbot]", e);
    }
  }

  // ── Events ───────────────────────────────────────────────────────
  sendBtn.addEventListener("click", sendMessage);
  inputEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  // ── Quick replies ─────────────────────────────────────────────────
  const quickEl = document.getElementById("quick-replies");
  if (quickEl && quickReplies.length) {
    quickReplies.forEach(label => {
      const btn = document.createElement("button");
      btn.className = "quick-reply-btn";
      btn.textContent = label;
      btn.addEventListener("click", () => {
        quickEl.hidden = true;
        inputEl.value = label;
        sendMessage();
      });
      quickEl.appendChild(btn);
    });
    quickEl.hidden = false;
  }

  // ── Welcome message ───────────────────────────────────────────────
  renderMessage("bot", welcomeMessage);

  // ── Toggle panel open / close ─────────────────────────────────────
  const toggleBtn = document.getElementById("chat-toggle");
  if (toggleBtn) {
    toggleBtn.addEventListener("click", () => {
      const isOpen = document.body.classList.toggle("panel-open");
      document.getElementById("chat-panel").setAttribute("aria-hidden", String(!isOpen));
      if (isOpen) {
        scrollToBottom();
        inputEl.focus();
      }
    });
  }

})();
