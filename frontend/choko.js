/* ================================================================
   Choko — Nexus-UGC AI Companion (Vanilla JS)
   v2: Page-aware, expandable chat, simplified section tracking
   ================================================================ */
(function () {
  "use strict";

  const DEV = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
  function log(...args) { if (DEV) console.log(...args); }
  const _t = (k, f) => (typeof __ === 'function' ? (__(k) || f) : f);

  const ASSET_PREFIX = "/mascot";
  const ASSET_VERSION = "20260607";

  const spritePath = (state) =>
    `${ASSET_PREFIX}/${state}/pose.webp?v=${ASSET_VERSION}`;

  const SPRITE_STATES = {
    idle: spritePath("idle"),
    welcome: spritePath("welcome"),
    about: spritePath("about"),
    skills: spritePath("skills"),
    projects: spritePath("projects"),
    experience: spritePath("experience"),
    education: spritePath("education"),
    leadership: spritePath("leadership"),
    erasmus: spritePath("erasmus"),
    contact: spritePath("contact"),
    loading: spritePath("loading"),
    celebration: spritePath("celebration"),
    goodbye: spritePath("goodbye"),
    error: spritePath("error"),
  };

  Object.values(SPRITE_STATES).forEach((src) => {
    const img = new Image();
    img.src = src;
  });

  const PAGE_CONFIG = {
    dashboard: { name: "Dashboard", state: "welcome", message: "Welcome to Nexus-UGC! Upload videos, generate clips with AI, and publish to social media. Need help? Just ask!" },
    brainrot: { name: "Brain Rot", state: "projects", message: "Brain Rot Shorts Generator — pick a niche, caption style, and platform. AI writes the script, renders the video, and creates a post in one click!" },
    queue: { name: "Queue", state: "loading", message: "Post Queue — review, approve, schedule, or cancel posts. Auto-publishing runs every 60 seconds. Approve a post and it goes live!" },
    accounts: { name: "Accounts", state: "skills", message: "Social Accounts — connect YouTube, TikTok, Instagram, Twitter, Facebook, LinkedIn. Or use System Accounts from .env for auto-provisioning." },
    billing: { name: "Billing", state: "celebration", message: "Billing & Plans — Free ($0), Pro ($19/mo), Enterprise ($99/mo). Claim a Whop license or upgrade anytime." },
    calendar: { name: "Calendar", state: "education", message: "Content Calendar — monthly grid of scheduled posts. Create, approve, or reschedule posts right from the calendar." },
    personas: { name: "Personas", state: "experience", message: "Personas — brand identities with voice, tone, audience, and content pillars. Auto-approve for hands-off publishing." },
    campaigns: { name: "Campaigns", state: "leadership", message: "Campaigns — organize content around themes. Assign personas, select platforms, set dates, track progress." },
    admin: { name: "Admin", state: "about", message: "Admin Panel — system health, publishing analytics, user management, connected accounts, and license management." },
    login: { name: "Login", state: "contact", message: "Sign in or register to access all features. Admin: admin@nexusugc.com" },
    unknown: { name: "Nexus-UGC", state: "idle", message: "Welcome to Nexus-UGC! Ask me about any page, feature, or workflow." },
  };

  const HEAD_NEUTRAL_ZONE = { x: 44, y: 38 };
  const HEAD_DIRECTION_TRANSFORMS = {
    neutral: { rotateY: 0, rotateZ: 0, translateY: 0 },
    left: { rotateY: 18, rotateZ: -2, translateY: 0 },
    right: { rotateY: -18, rotateZ: 2, translateY: 0 },
    up: { rotateY: 0, rotateZ: -3, translateY: -4 },
    down: { rotateY: 0, rotateZ: 2, translateY: 4 },
  };

  let currentPage = "unknown";
  let showBubble = true;
  let displayedMessage = "";
  let isPreparingMessage = true;
  let isPinned = false;
  let isDragging = false;
  let isChatOpen = false;
  let isChatMaximized = false;
  let chatMessages = [];
  let headDirection = "neutral";
  let isBlinking = false;
  let isReducedMotion = false;
  let position = { x: 0, y: 0 };
  let dragOffset = { x: 0, y: 0 };
  let lastDirection = "neutral";

  let hideTimer = null;
  let messageTimer = null;
  let blinkTimer = null;
  let blinkResetTimer = null;
  let directionTimer = null;

  let root = null;
  let stage = null;
  let spriteImg = null;
  let bubble = null;
  let bubbleText = null;
  let signal = null;
  let nameplate = null;
  let chatToggle = null;
  let chatPanel = null;
  let chatMessagesEl = null;
  let chatForm = null;
  let chatInputEl = null;
  let chatSuggestionsEl = null;
  let chatMaximizeBtn = null;

  const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

  const getCompanionSize = () => root?.offsetWidth || 156;

  const detectPage = () => {
    const path = window.location.pathname;
    if (path === "/" || path === "/index.html") return "dashboard";
    if (path.includes("brainrot")) return "brainrot";
    if (path.includes("queue")) return "queue";
    if (path.includes("accounts")) return "accounts";
    if (path.includes("billing")) return "billing";
    if (path.includes("calendar")) return "calendar";
    if (path.includes("personas")) return "personas";
    if (path.includes("campaigns")) return "campaigns";
    if (path.includes("admin")) return "admin";
    if (path.includes("login")) return "login";
    return "unknown";
  };

  const getPageConfig = () => PAGE_CONFIG[detectPage()] || PAGE_CONFIG.unknown;
  const getPageMsg = () => _t('choko.' + detectPage(), getPageConfig().message);

  const getDefaultPosition = () => {
    const size = getCompanionSize();
    const margin = Math.max(18, Math.min(34, window.innerWidth * 0.025));
    const defaultPos = { x: 86, y: 64 };
    return {
      x: clamp(
        (defaultPos.x / 100) * window.innerWidth,
        margin + size / 2,
        window.innerWidth - margin - size / 2
      ),
      y: clamp(
        (defaultPos.y / 100) * window.innerHeight,
        margin + size / 2,
        window.innerHeight - margin - size / 2
      ),
    };
  };

  const revealBubble = (duration, text, delay) => {
    const msg = text || getPageMsg() || "";
    showBubble = true;
    isPreparingMessage = !!delay;
    if (messageTimer) clearTimeout(messageTimer);
    if (hideTimer) clearTimeout(hideTimer);
    displayedMessage = "";
    updateBubble();

    if (delay) {
      messageTimer = setTimeout(() => {
        displayedMessage = msg;
        isPreparingMessage = false;
        updateBubble();
      }, delay);
    } else {
      displayedMessage = msg;
      isPreparingMessage = false;
      updateBubble();
    }

    hideTimer = setTimeout(() => {
      showBubble = false;
      updateBubble();
    }, duration || 9000);
  };

  const updatePosition = () => {
    if (!root) return;
    root.style.left = `${position.x}px`;
    root.style.top = `${position.y}px`;
  };

  const updateSide = () => {
    if (!root) return;
    const side = "right";
    root.classList.remove("stage-left", "stage-right");
    root.classList.add(`stage-${side}`);
  };

  const updateSprite = () => {
    if (!spriteImg) return;
    const cfg = getPageConfig();
    const state = cfg.state || "idle";
    const src = SPRITE_STATES[state] || SPRITE_STATES.idle;
    if (spriteImg.src !== src) {
      spriteImg.src = src;
    }
  };

  const updateHeadDirection = () => {
    if (!spriteImg || isReducedMotion) return;
    const dirKey = isBlinking ? "neutral" : headDirection;
    const transform = HEAD_DIRECTION_TRANSFORMS[dirKey] || HEAD_DIRECTION_TRANSFORMS.neutral;
    spriteImg.style.setProperty("--dir-rotate-y", `${transform.rotateY}deg`);
    spriteImg.style.setProperty("--dir-rotate-z", `${transform.rotateZ}deg`);
    spriteImg.style.setProperty("--dir-translate-y", `${transform.translateY}px`);
  };

  const updateBlink = () => {
    if (!spriteImg) return;
    spriteImg.classList.toggle("blinking", isBlinking);
  };

  const updateBubble = () => {
    if (!bubble) return;
    if (showBubble) {
      bubble.classList.add("visible");
      bubble.classList.toggle("thinking", isPreparingMessage);
      if (signal) signal.style.display = isPreparingMessage ? "" : "none";
      const textEl = bubble.querySelector(".choko-bubble-text");
      if (textEl) {
        textEl.textContent = displayedMessage;
        textEl.style.display = isPreparingMessage ? "none" : "";
      }
    } else {
      bubble.classList.remove("visible");
    }
  };

  const updateChatToggle = () => {
    if (!chatToggle) return;
    chatToggle.setAttribute("aria-expanded", String(isChatOpen));
    chatToggle.textContent = isChatOpen ? _t('choko.close-chat', 'Close Chat') : _t('choko.ask-choko', 'Ask Choko');
  };

  const updateChatPanel = () => {
    if (!chatPanel || !chatMessagesEl) return;
    if (isChatOpen) {
      chatPanel.style.display = "";
      chatPanel.classList.toggle("maximized", isChatMaximized);
      renderChatMessages();
    } else {
      chatPanel.style.display = "none";
      chatPanel.classList.remove("maximized");
    }
  };

  const updateMaximizeButton = () => {
    if (!chatMaximizeBtn) return;
    chatMaximizeBtn.innerHTML = isChatMaximized
      ? '<svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M3 11L11 3M11 3H5M11 3V9"/></svg>'
      : '<svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M2 12L12 2M12 2H6M12 2V8"/></svg>';
    chatMaximizeBtn.setAttribute("aria-label", isChatMaximized ? _t('choko.minimize-chat', 'Minimize chat') : _t('choko.maximize-chat', 'Maximize chat'));
  };

  const renderChatMessages = () => {
    if (!chatMessagesEl) return;
    chatMessagesEl.innerHTML = chatMessages
      .map(
        (msg, i) =>
          `<p class="${msg.role === "user" ? "choko-user-msg" : "choko-assistant-msg"}">${escHtml(msg.text)}</p>`
      )
      .join("");
    chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;
  };

  const renderSuggestions = () => {
    if (!chatSuggestionsEl) return;
    const suggestions = window.CHOKO_SUGGESTIONS || [
      "What is Nexus-UGC?",
      "How does the pipeline work?",
      "How do I publish?",
      "How do I connect accounts?",
    ];
    chatSuggestionsEl.innerHTML = suggestions.slice(0, 4)
      .map((s) => `<button type="button" class="choko-suggestion-btn">${s}</button>`)
      .join("");
  };

  const handlePointerDown = (e) => {
    if (window.innerWidth <= 720) return;
    const rect = root?.getBoundingClientRect();
    if (!rect) return;
    dragOffset = {
      x: e.clientX - (rect.left + rect.width / 2),
      y: e.clientY - (rect.top + rect.height / 2),
    };
    isPinned = true;
    isDragging = true;
    root?.classList.add("choko-dragging");
    revealBubble(6000, _t('choko.drag-hint', 'Drag me anywhere. Double-click me when you want me back on the guided path.'), isReducedMotion ? 0 : 360);
  };

  const handlePointerMove = (e) => {
    if (!isDragging) return;
    const size = getCompanionSize();
    const margin = 10;
    position = {
      x: clamp(e.clientX - dragOffset.x, margin + size / 2, window.innerWidth - margin - size / 2),
      y: clamp(e.clientY - dragOffset.y, margin + size / 2, window.innerHeight - margin - size / 2),
    };
    updatePosition();
  };

  const handlePointerUp = () => {
    if (!isDragging) return;
    isDragging = false;
    root?.classList.remove("choko-dragging");
    revealBubble(3200, "", isReducedMotion ? 0 : 420);
  };

  const handleDoubleClick = () => {
    isPinned = false;
    isDragging = false;
    position = getDefaultPosition();
    updatePosition();
    revealBubble(3600, _t('choko.back-to-default', "Back to default position. I'll stay right here."), isReducedMotion ? 0 : 420);
  };

  const handlePointerMoveHead = (e) => {
    if (isReducedMotion || isBlinking) return;
    const rect = root?.getBoundingClientRect();
    if (!rect) return;
    const eyeX = rect.left + rect.width * 0.5;
    const eyeY = rect.top + rect.height * 0.32;
    const dx = e.clientX - eyeX;
    const dy = e.clientY - eyeY;

    let dir = "neutral";
    if (Math.abs(dx) >= HEAD_NEUTRAL_ZONE.x || Math.abs(dy) >= HEAD_NEUTRAL_ZONE.y) {
      if (Math.abs(dx) > Math.abs(dy) * 1.1) {
        dir = dx < 0 ? "left" : "right";
      } else {
        dir = dy < 0 ? "up" : "down";
      }
    }
    if (dir === lastDirection) return;
    if (directionTimer) clearTimeout(directionTimer);
    directionTimer = setTimeout(() => {
      lastDirection = dir;
      headDirection = dir;
      updateHeadDirection();
    }, 80);
  };

  const handlePointerLeave = () => {
    if (directionTimer) clearTimeout(directionTimer);
    lastDirection = "neutral";
    headDirection = "neutral";
    updateHeadDirection();
  };

  const scheduleBlink = () => {
    if (isReducedMotion) return;
    blinkTimer = setTimeout(() => {
      isBlinking = true;
      updateBlink();
      blinkResetTimer = setTimeout(() => {
        isBlinking = false;
        updateBlink();
        scheduleBlink();
      }, 130);
    }, 3800 + Math.random() * 3000);
  };

  const askChoko = (question) => {
    const clean = question.trim();
    if (!clean) return;
    const answer =
      typeof answerChokoQuestion === "function" ? answerChokoQuestion(clean) : _t('choko.fallback-answer', "I'm not sure about that. Try asking about the pipeline, features, or pricing!");
    chatMessages.push({ role: "user", text: clean });
    chatMessages.push({ role: "assistant", text: answer });
    if (!isChatOpen) {
      isChatOpen = true;
    }
    showBubble = false;
    updateBubble();
    updateChatToggle();
    updateChatPanel();
  };

  const handleChatSubmit = (e) => {
    e.preventDefault();
    const value = chatInputEl?.value?.trim();
    if (!value) return;
    askChoko(value);
    if (chatInputEl) chatInputEl.value = "";
  };

  const toggleMaximize = () => {
    isChatMaximized = !isChatMaximized;
    updateMaximizeButton();
    updateChatPanel();
  };

  const buildMascot = () => {
    root = document.createElement("aside");
    root.className = "choko";

    stage = document.createElement("button");
    stage.className = "choko-stage";
    stage.type = "button";
    stage.setAttribute("aria-label", _t('choko.drag-aria', 'Drag Choko AI companion. Double click to return to default position.'));

    const halo = document.createElement("span");
    halo.className = "choko-halo";
    stage.appendChild(halo);

    const orbit = document.createElement("span");
    orbit.className = "choko-orbit";
    stage.appendChild(orbit);

    const sparkle = document.createElement("span");
    sparkle.className = "choko-sparkle";
    stage.appendChild(sparkle);

    const shadow = document.createElement("img");
    shadow.className = "choko-shadow";
    shadow.src = SPRITE_STATES.idle;
    shadow.alt = "";
    shadow.setAttribute("aria-hidden", "true");
    stage.appendChild(shadow);

    const depth = document.createElement("img");
    depth.className = "choko-depth";
    depth.src = SPRITE_STATES.idle;
    depth.alt = "";
    depth.setAttribute("aria-hidden", "true");
    stage.appendChild(depth);

    spriteImg = document.createElement("img");
    spriteImg.className = "choko-sprite";
    spriteImg.src = SPRITE_STATES.idle;
    spriteImg.alt = _t('choko.sprite-alt', 'Choko — Nexus-UGC AI companion');
    spriteImg.setAttribute("decoding", "async");
    stage.appendChild(spriteImg);

    nameplate = document.createElement("span");
    nameplate.className = "choko-nameplate";
    nameplate.innerHTML = '<strong>' + _t('choko.name', 'Choko') + '</strong><small>' + _t('choko.guide-label', 'AI Guide') + '</small>';
    stage.appendChild(nameplate);

    const dragHint = document.createElement("span");
    dragHint.className = "choko-drag-hint";
    dragHint.textContent = _t('choko.drag-hint-label', 'Drag me');
    dragHint.setAttribute("aria-hidden", "true");
    stage.appendChild(dragHint);

    root.appendChild(stage);

    bubble = document.createElement("div");
    bubble.className = "choko-bubble";

    signal = document.createElement("span");
    signal.className = "choko-signal";
    signal.innerHTML = '<span></span><span></span><span></span><strong>' + _t('choko.reading-page', 'Reading this page') + '</strong>';
    bubble.appendChild(signal);

    bubbleText = document.createElement("span");
    bubbleText.className = "choko-bubble-text";
    bubble.appendChild(bubbleText);

    root.appendChild(bubble);

    chatToggle = document.createElement("button");
    chatToggle.className = "choko-chat-toggle";
    chatToggle.type = "button";
    chatToggle.setAttribute("aria-expanded", "false");
    chatToggle.setAttribute("aria-controls", "choko-chat-panel");
    chatToggle.textContent = _t('choko.ask-choko', 'Ask Choko');
    root.appendChild(chatToggle);

    chatPanel = document.createElement("div");
    chatPanel.className = "choko-chat-panel";
    chatPanel.id = "choko-chat-panel";
    chatPanel.style.display = "none";
    chatPanel.setAttribute("role", "dialog");
    chatPanel.setAttribute("aria-label", _t('choko.ask-choko', 'Ask Choko'));

    chatPanel.innerHTML =
      '<div class="choko-chat-header">' +
        '<div>' +
          '<strong>' + _t('choko.chat-header', 'Choko chat') + '</strong>' +
          '<span>' + _t('choko.chat-subtitle', 'Nexus-UGC knowledge base') + '</span>' +
        '</div>' +
        '<div class="choko-chat-header-actions">' +
          '<button type="button" class="choko-chat-maximize" aria-label="' + _t('choko.maximize-chat', 'Maximize chat') + '"></button>' +
          '<button type="button" class="choko-chat-close" aria-label="' + _t('choko.close-chat', 'Close Choko chat') + '">&times;</button>' +
        '</div>' +
      '</div>' +
      '<div class="choko-chat-messages" aria-live="polite"></div>' +
      '<div class="choko-chat-suggestions"></div>' +
      '<form class="choko-chat-form">' +
        '<input type="text" placeholder="' + _t('choko.chat-placeholder', 'Ask about pipeline, features, publishing...') + '" aria-label="' + _t('choko.chat-input-label', 'Ask Choko a question') + '">' +
        '<button type="submit" aria-label="' + _t('choko.chat-submit-label', 'Send question to Choko') + '">&rarr;</button>' +
      '</form>';
    root.appendChild(chatPanel);

    return root;
  };

  const init = () => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    isReducedMotion = media.matches;
    media.addEventListener("change", () => {
      isReducedMotion = media.matches;
      if (isReducedMotion) {
        headDirection = "neutral";
        isBlinking = false;
        updateHeadDirection();
        updateBlink();
      }
    });

    const el = buildMascot();
    document.body.appendChild(el);

    currentPage = detectPage();
    position = getDefaultPosition();
    updateSide();
    updateSprite();
    updatePosition();
    updateBubble();

    requestAnimationFrame(() => {
      root.classList.add("ready");
    });

    stage = root.querySelector(".choko-stage");
    spriteImg = root.querySelector(".choko-sprite");
    bubble = root.querySelector(".choko-bubble");
    bubbleText = root.querySelector(".choko-bubble-text");
    signal = root.querySelector(".choko-signal");
    chatToggle = root.querySelector(".choko-chat-toggle");
    chatPanel = root.querySelector(".choko-chat-panel");
    chatMessagesEl = root.querySelector(".choko-chat-messages");
    chatForm = root.querySelector(".choko-chat-form");
    chatInputEl = root.querySelector(".choko-chat-form input");
    chatSuggestionsEl = root.querySelector(".choko-chat-suggestions");
    chatMaximizeBtn = root.querySelector(".choko-chat-maximize");

    chatMessages = [];
    const cfg = getPageConfig();
    chatMessages.push({ role: "assistant", text: cfg.message });
    renderSuggestions();
    updateMaximizeButton();
    chatMessagesEl.innerHTML = "";

    stage.addEventListener("pointerdown", handlePointerDown);
    stage.addEventListener("dblclick", handleDoubleClick);

    window.addEventListener("pointermove", handlePointerMoveHead, { passive: true });
    window.addEventListener("pointerleave", handlePointerLeave);
    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", handlePointerUp);
    window.addEventListener("pointercancel", handlePointerUp);

    const onResize = () => {
      if (isDragging || isPinned) return;
      position = getDefaultPosition();
      updatePosition();
    };
    window.addEventListener("resize", onResize, { passive: true });

    scheduleBlink();

    chatToggle.addEventListener("click", () => {
      isChatOpen = !isChatOpen;
      showBubble = false;
      updateBubble();
      updateChatToggle();
      updateChatPanel();
      if (isChatOpen && chatMessages.length === 0) {
    chatMessages.push({ role: "assistant", text: getPageMsg() });
      }
      if (isChatOpen) renderChatMessages();
    });

    const closeBtn = chatPanel?.querySelector(".choko-chat-close");
    closeBtn?.addEventListener("click", () => {
      isChatOpen = false;
      updateChatToggle();
      updateChatPanel();
    });

    chatMaximizeBtn?.addEventListener("click", toggleMaximize);

    chatForm?.addEventListener("submit", handleChatSubmit);

    chatSuggestionsEl?.addEventListener("click", (e) => {
      const btn = e.target.closest(".choko-suggestion-btn");
      if (btn) {
        askChoko(btn.textContent);
      }
    });

    stage.addEventListener("mouseenter", () => {
      if (!isChatOpen) revealBubble(5200);
    });
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
