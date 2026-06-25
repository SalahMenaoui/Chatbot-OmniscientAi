(function () {
  var script = document.currentScript;
  var clientId = script.getAttribute('data-client');
  if (!clientId) return;

  var base = new URL(script.src).origin;
  var chatUrl = base + '/clients/' + clientId + '/chatbot/';

  /* ── Styles ─────────────────────────────────────────────── */
  var s = document.createElement('style');
  s.textContent =
    '#_oai_btn{position:fixed;bottom:24px;right:24px;width:56px;height:56px;border-radius:50%;background:#dc4545;border:none;cursor:pointer;z-index:2147483646;box-shadow:0 4px 20px rgba(220,69,69,.45);transition:transform .2s,box-shadow .2s;display:flex;align-items:center;justify-content:center}' +
    '#_oai_btn:hover{transform:scale(1.07);box-shadow:0 6px 28px rgba(220,69,69,.55)}' +
    '#_oai_frame{position:fixed;bottom:92px;right:24px;width:390px;height:600px;border:none;border-radius:20px;z-index:2147483645;box-shadow:0 16px 56px rgba(0,0,0,.25);opacity:0;pointer-events:none;transform:translateY(14px) scale(.97);transition:opacity .22s ease,transform .22s ease}' +
    '#_oai_frame.oai-open{opacity:1;pointer-events:auto;transform:none}' +
    '@media(max-width:460px){#_oai_frame{width:calc(100vw - 16px);height:calc(100svh - 88px);right:8px;bottom:76px;border-radius:16px}}' +
    '@keyframes _oai_nudge{0%,100%{transform:translateY(0) scale(1)}18%{transform:translateY(-9px) scale(1.07)}32%{transform:translateY(0) scale(1)}46%{transform:translateY(-5px) scale(1.03)}60%,100%{transform:translateY(0) scale(1)}}' +
    '@keyframes _oai_glow{0%,100%{box-shadow:0 4px 20px rgba(220,69,69,.45)}25%{box-shadow:0 4px 20px rgba(220,69,69,.45),0 0 0 10px rgba(220,69,69,.18),0 0 32px rgba(220,69,69,.3)}55%{box-shadow:0 4px 20px rgba(220,69,69,.45)}}' +
    '#_oai_btn._oai_idle{animation:_oai_nudge .9s ease,_oai_glow .9s ease}';
  document.head.appendChild(s);

  /* ── Icons ──────────────────────────────────────────────── */
  var ICON_CHAT  = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>';
  var ICON_CLOSE = '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';

  /* ── Elements ───────────────────────────────────────────── */
  var btn = document.createElement('button');
  btn.id = '_oai_btn';
  btn.setAttribute('aria-label', 'Ouvrir le chat');
  btn.innerHTML = ICON_CHAT;

  var frame = document.createElement('iframe');
  frame.id = '_oai_frame';
  frame.src = chatUrl;
  frame.setAttribute('allow', 'clipboard-write');
  frame.setAttribute('title', 'Chat');

  document.body.appendChild(frame);
  document.body.appendChild(btn);

  /* ── Toggle ─────────────────────────────────────────────── */
  var open = false;
  btn.addEventListener('click', function () {
    open = !open;
    frame.classList.toggle('oai-open', open);
    btn.innerHTML = open ? ICON_CLOSE : ICON_CHAT;
    btn.setAttribute('aria-label', open ? 'Fermer le chat' : 'Ouvrir le chat');
  });

  /* ── Idle bounce + glow ─────────────────────────────────── */
  btn.addEventListener('animationend', function () {
    btn.classList.remove('_oai_idle');
  });
  function nudge() {
    if (open) return;
    btn.classList.remove('_oai_idle');
    void btn.offsetWidth; // force reflow so animation restarts
    btn.classList.add('_oai_idle');
  }
  setTimeout(nudge, 3000);
  setInterval(nudge, 7000);
})();
