/**
 * chatbot.js — AI Chatbot Widget Core
 *
 * Loads config.json, applies full theme via CSS variables,
 * renders markdown, shows typing indicator, proxies to Claude API.
 * Supports optional visitor capture (Tier 2+) and conversation logging.
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
    clientId       = null,
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

  // ── Capture state ────────────────────────────────────────────────
  const serverBase     = (() => { try { return new URL(proxyUrl).origin; } catch { return window.location.origin; } })();
  let   conversationId = null;

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
          ...(conversationId != null ? { conversation_id: conversationId } : {}),
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

  // ── Capture ───────────────────────────────────────────────────────
  async function initCapture() {
    if (!clientId || !serverBase) return;

    const SK = `omni_${clientId}`;
    const stored = (() => { try { return JSON.parse(sessionStorage.getItem(SK)); } catch { return null; } })();
    if (stored?.conversationId) { conversationId = stored.conversationId; return; }

    const overlay = document.getElementById("capture-overlay");
    if (!overlay) return;

    overlay.hidden = false;

    let tier = 1;
    try {
      const r = await fetch(`${serverBase}/api/client-config/${encodeURIComponent(clientId)}`);
      if (r.ok) tier = (await r.json()).tier ?? 1;
    } catch {}

    if (tier < 2) { overlay.hidden = true; return; }

    await new Promise((resolve) => {
      const form  = document.getElementById("capture-form");
      const errEl = document.getElementById("capture-error");
      const btn   = document.getElementById("capture-btn");

      form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const name  = document.getElementById("capture-name").value.trim();
        const email = document.getElementById("capture-email").value.trim();

        if (!name || !email) {
          errEl.textContent = "Veuillez remplir tous les champs.";
          errEl.hidden = false;
          return;
        }

        btn.disabled    = true;
        btn.textContent = "…";
        errEl.hidden    = true;

        try {
          const res = await fetch(`${serverBase}/api/capture`, {
            method:  "POST",
            headers: { "Content-Type": "application/json" },
            body:    JSON.stringify({ client_key: clientId, name, email }),
          });
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          const data     = await res.json();
          conversationId = data.conversation_id;
          sessionStorage.setItem(SK, JSON.stringify({ conversationId }));
          overlay.hidden = true;
          resolve();
        } catch {
          btn.disabled    = false;
          btn.textContent = "Commencer →";
          errEl.textContent = "Une erreur est survenue. Réessayez.";
          errEl.hidden = false;
        }
      });
    });
  }

  // ── Widget: draggable button + resizable panel ───────────────────
  (function setupWidget() {
    const toggle = document.getElementById("chat-toggle");
    const panel  = document.getElementById("chat-panel");
    if (!toggle || !panel) return;

    const BTN    = 58;
    const MARGIN = 10;
    const MIN_W  = 300, MAX_W = 620;
    const MIN_H  = 360;

    // ── State persistence ─────────────────────────────────────────
    const KEY = "chatwidget";
    const load = () => { try { return JSON.parse(localStorage.getItem(KEY) || "{}"); } catch { return {}; } };
    const save = (d)  => localStorage.setItem(KEY, JSON.stringify({ ...load(), ...d }));

    const st = load();
    let btnRight  = st.btnRight  ?? 20;
    let btnBottom = st.btnBottom ?? 20;
    let panelW    = st.panelW    ?? 380;
    let panelH    = st.panelH    ?? 560;

    function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

    // ── Apply button position ──────────────────────────────────────
    function applyBtn() {
      btnRight  = clamp(btnRight,  MARGIN, window.innerWidth  - BTN - MARGIN);
      btnBottom = clamp(btnBottom, MARGIN, window.innerHeight - BTN - MARGIN);
      toggle.style.right  = btnRight  + "px";
      toggle.style.bottom = btnBottom + "px";
      toggle.style.left = toggle.style.top = "auto";
    }

    // ── Apply panel size ───────────────────────────────────────────
    function applySize() {
      panelW = clamp(panelW, MIN_W, MAX_W);
      panelH = clamp(panelH, MIN_H, window.innerHeight - 80);
      panel.style.width  = panelW + "px";
      panel.style.height = panelH + "px";
    }

    // ── Position panel relative to button ─────────────────────────
    function positionPanel() {
      const r = toggle.getBoundingClientRect();
      const gap = 10;

      // Vertical: above if space, else below
      let top = (r.top - panelH - gap >= gap)
        ? r.top - panelH - gap
        : r.bottom + gap;

      // Horizontal: right-align with button
      let left = r.right - panelW;

      top  = clamp(top,  MARGIN, window.innerHeight - panelH - MARGIN);
      left = clamp(left, MARGIN, window.innerWidth  - panelW - MARGIN);

      panel.style.top    = top  + "px";
      panel.style.left   = left + "px";
      panel.style.bottom = "auto";
      panel.style.right  = "auto";

      // transform-origin: corner closest to button
      const btnCX = r.left + BTN / 2;
      const btnCY = r.top  + BTN / 2;
      const ox = btnCX < left + panelW / 2 ? "left" : "right";
      const oy = btnCY < top  + panelH / 2 ? "top"  : "bottom";
      panel.style.transformOrigin = `${oy} ${ox}`;

      // Move resize handle to opposite corner
      const handle = document.getElementById("resize-handle");
      if (handle) {
        handle.className = "";
        handle.classList.add(oy === "top" ? "rh-bottom" : "rh-top");
        handle.classList.add(ox === "left" ? "rh-right"  : "rh-left");
      }
    }

    // ── Toggle panel ──────────────────────────────────────────────
    function togglePanel() {
      const open = document.body.classList.toggle("panel-open");
      panel.setAttribute("aria-hidden", String(!open));
      if (open) { applySize(); positionPanel(); setTimeout(scrollToBottom, 40); inputEl.focus(); }
    }

    // ── Drag button ───────────────────────────────────────────────
    let drag = null;

    toggle.addEventListener("mousedown", (e) => {
      if (e.button !== 0) return;
      drag = { x0: e.clientX, y0: e.clientY, r0: btnRight, b0: btnBottom, moved: false };
      toggle.style.transition = "none";
      e.preventDefault();
    });
    toggle.addEventListener("touchstart", (e) => {
      const t = e.touches[0];
      drag = { x0: t.clientX, y0: t.clientY, r0: btnRight, b0: btnBottom, moved: false };
      toggle.style.transition = "none";
      e.preventDefault();
    }, { passive: false });

    window.addEventListener("mousemove", (e) => {
      if (!drag) return;
      const dx = e.clientX - drag.x0, dy = e.clientY - drag.y0;
      if (!drag.moved && Math.hypot(dx, dy) > 5) drag.moved = true;
      if (!drag.moved) return;
      btnRight = drag.r0 - dx; btnBottom = drag.b0 - dy;
      applyBtn();
      if (document.body.classList.contains("panel-open")) positionPanel();
    });
    window.addEventListener("touchmove", (e) => {
      if (!drag) return;
      const t = e.touches[0];
      const dx = t.clientX - drag.x0, dy = t.clientY - drag.y0;
      if (!drag.moved && Math.hypot(dx, dy) > 5) drag.moved = true;
      if (!drag.moved) return;
      btnRight = drag.r0 - dx; btnBottom = drag.b0 - dy;
      applyBtn();
      if (document.body.classList.contains("panel-open")) positionPanel();
      e.preventDefault();
    }, { passive: false });

    window.addEventListener("mouseup",  () => { if (!drag) return; toggle.style.transition = ""; if (!drag.moved) togglePanel(); else save({ btnRight, btnBottom }); drag = null; });
    window.addEventListener("touchend", () => { if (!drag) return; toggle.style.transition = ""; if (!drag.moved) togglePanel(); else save({ btnRight, btnBottom }); drag = null; });

    // ── Resize handle ──────────────────────────────────────────────
    const handle = document.createElement("div");
    handle.id = "resize-handle";
    handle.innerHTML = `<svg viewBox="0 0 10 10" fill="none"><circle cx="2" cy="2" r="1" fill="currentColor"/><circle cx="5" cy="2" r="1" fill="currentColor"/><circle cx="8" cy="2" r="1" fill="currentColor"/><circle cx="2" cy="5" r="1" fill="currentColor"/><circle cx="5" cy="5" r="1" fill="currentColor"/><circle cx="8" cy="5" r="1" fill="currentColor"/><circle cx="2" cy="8" r="1" fill="currentColor"/><circle cx="5" cy="8" r="1" fill="currentColor"/><circle cx="8" cy="8" r="1" fill="currentColor"/></svg>`;
    panel.appendChild(handle);

    let rz = null;

    handle.addEventListener("mousedown", (e) => {
      const cls = handle.className;
      rz = { x0: e.clientX, y0: e.clientY, w0: panelW, h0: panelH, cls };
      document.body.style.userSelect = "none";
      e.preventDefault(); e.stopPropagation();
    });

    window.addEventListener("mousemove", (e) => {
      if (!rz) return;
      const dx = e.clientX - rz.x0, dy = e.clientY - rz.y0;
      if (rz.cls.includes("rh-right"))  panelW = clamp(rz.w0 + dx, MIN_W, MAX_W);
      if (rz.cls.includes("rh-left"))   panelW = clamp(rz.w0 - dx, MIN_W, MAX_W);
      if (rz.cls.includes("rh-bottom")) panelH = clamp(rz.h0 + dy, MIN_H, window.innerHeight - 80);
      if (rz.cls.includes("rh-top"))    panelH = clamp(rz.h0 - dy, MIN_H, window.innerHeight - 80);
      applySize(); positionPanel();
    });

    window.addEventListener("mouseup", () => {
      if (!rz) return;
      save({ panelW, panelH }); rz = null;
      document.body.style.userSelect = "";
    });

    // ── Init + window resize ──────────────────────────────────────
    applyBtn(); applySize();
    window.addEventListener("resize", () => { applyBtn(); if (document.body.classList.contains("panel-open")) { applySize(); positionPanel(); } });

    // ── Idle bounce animation ─────────────────────────────────────
    toggle.addEventListener("animationend", () => toggle.classList.remove("idle-bounce"));
    function nudge() {
      if (document.body.classList.contains("panel-open")) return;
      toggle.classList.remove("idle-bounce");
      void toggle.offsetWidth;
      toggle.classList.add("idle-bounce");
    }
    setTimeout(nudge, 3000);
    setInterval(nudge, 7000);
  })();

  // ── Async init: capture form → then show chat ─────────────────────
  (async () => {
    await initCapture();

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

    renderMessage("bot", welcomeMessage);
  })();

})();
