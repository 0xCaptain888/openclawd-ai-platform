/**
 * chat.js - AI Chat Widget
 *
 * Floating chat widget that connects to /api/chat.
 * Features: open/close panel, message history, typing effect, auto-scroll.
 */

(function () {
  "use strict";

  // -- State --
  const state = {
    isOpen: false,
    isLoading: false,
    history: [], // {role: "user"|"assistant", content: string}
  };

  // -- DOM references (set after inject) --
  let chatPanel, chatMessages, chatInput, chatSendBtn, chatToggleBtn;

  // -- Helpers --

  function scrollToBottom() {
    requestAnimationFrame(() => {
      chatMessages.scrollTop = chatMessages.scrollHeight;
    });
  }

  function createMessageEl(role, text) {
    const wrapper = document.createElement("div");
    wrapper.className =
      "chat-msg flex " + (role === "user" ? "justify-end" : "justify-start") + " mb-3";

    const bubble = document.createElement("div");
    bubble.className =
      role === "user"
        ? "max-w-[80%] px-4 py-2 rounded-2xl bg-blue-600 text-white rounded-br-sm text-sm leading-relaxed"
        : "max-w-[80%] px-4 py-2 rounded-2xl bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-gray-100 rounded-bl-sm text-sm leading-relaxed";

    bubble.textContent = text;
    wrapper.appendChild(bubble);
    return { wrapper, bubble };
  }

  /** Typing effect: reveal text character by character */
  function typeText(el, text, speed) {
    return new Promise((resolve) => {
      let i = 0;
      el.textContent = "";
      const interval = setInterval(() => {
        // Add a few chars at a time for speed
        const chunk = text.slice(i, i + 2);
        el.textContent += chunk;
        i += 2;
        scrollToBottom();
        if (i >= text.length) {
          clearInterval(interval);
          el.textContent = text; // ensure full text
          resolve();
        }
      }, speed);
    });
  }

  // -- Core logic --

  function toggleChat() {
    state.isOpen = !state.isOpen;
    chatPanel.classList.toggle("hidden", !state.isOpen);
    chatToggleBtn.setAttribute("aria-expanded", state.isOpen);
    if (state.isOpen) {
      chatInput.focus();
      scrollToBottom();
    }
  }

  async function sendMessage() {
    const text = chatInput.value.trim();
    if (!text || state.isLoading) return;

    // Show user message
    const { wrapper: userEl } = createMessageEl("user", text);
    chatMessages.appendChild(userEl);
    state.history.push({ role: "user", content: text });
    chatInput.value = "";
    scrollToBottom();

    // Show loading indicator
    state.isLoading = true;
    chatSendBtn.disabled = true;
    const loadingEl = document.createElement("div");
    loadingEl.className = "chat-msg flex justify-start mb-3";
    loadingEl.innerHTML =
      '<div class="px-4 py-2 rounded-2xl bg-gray-200 dark:bg-gray-700 rounded-bl-sm text-sm text-gray-500 dark:text-gray-400 animate-pulse">AI 正在思考...</div>';
    chatMessages.appendChild(loadingEl);
    scrollToBottom();

    try {
      const resp = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          history: state.history.slice(-10),
        }),
      });

      if (!resp.ok) throw new Error("API error " + resp.status);
      const data = await resp.json();
      const reply = data.reply || "Sorry, no response.";

      // Remove loading, show reply with typing effect
      loadingEl.remove();
      const { wrapper: botEl, bubble } = createMessageEl("assistant", "");
      chatMessages.appendChild(botEl);
      await typeText(bubble, reply, 15);

      state.history.push({ role: "assistant", content: reply });
    } catch (err) {
      loadingEl.remove();
      const { wrapper: errEl } = createMessageEl(
        "assistant",
        "抱歉，连接出现问题，请稍后再试。"
      );
      chatMessages.appendChild(errEl);
      console.error("Chat error:", err);
    } finally {
      state.isLoading = false;
      chatSendBtn.disabled = false;
      chatInput.focus();
      scrollToBottom();
    }
  }

  // -- Inject widget HTML --

  function injectWidget() {
    const container = document.createElement("div");
    container.id = "chat-widget";
    container.innerHTML = `
      <!-- Toggle button -->
      <button id="chat-toggle-btn"
        aria-label="Open chat"
        aria-expanded="false"
        class="fixed bottom-6 right-6 z-50 w-14 h-14 rounded-full bg-blue-600 hover:bg-blue-700 text-white shadow-lg flex items-center justify-center transition-transform hover:scale-105 focus:outline-none focus:ring-2 focus:ring-blue-400">
        <svg id="chat-icon-open" class="w-6 h-6" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round"
            d="M8 10h.01M12 10h.01M16 10h.01M21 12c0 4.418-4.03 8-9 8a9.77 9.77 0 01-4-.8L3 21l1.8-4A7.44 7.44 0 013 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/>
        </svg>
        <svg id="chat-icon-close" class="w-6 h-6 hidden" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
        </svg>
      </button>

      <!-- Chat panel -->
      <div id="chat-panel"
        class="hidden fixed bottom-24 right-6 z-50 w-[360px] max-w-[calc(100vw-2rem)] h-[500px] max-h-[70vh] rounded-2xl shadow-2xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 flex flex-col overflow-hidden">
        <!-- Header -->
        <div class="flex items-center gap-3 px-4 py-3 bg-blue-600 text-white shrink-0">
          <div class="w-8 h-8 rounded-full bg-white/20 flex items-center justify-center text-sm font-bold">AI</div>
          <div>
            <div class="font-semibold text-sm">智能助手</div>
            <div class="text-xs opacity-80">有什么可以帮您？</div>
          </div>
        </div>
        <!-- Messages -->
        <div id="chat-messages" class="flex-1 overflow-y-auto p-4 space-y-1">
          <div class="flex justify-start mb-3">
            <div class="max-w-[80%] px-4 py-2 rounded-2xl bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-gray-100 rounded-bl-sm text-sm leading-relaxed">
              您好！我是智能助手，有什么可以帮您的吗？
            </div>
          </div>
        </div>
        <!-- Input -->
        <div class="shrink-0 border-t border-gray-200 dark:border-gray-700 px-3 py-2 flex items-center gap-2 bg-gray-50 dark:bg-gray-900">
          <input id="chat-input" type="text" placeholder="输入您的问题..."
            class="flex-1 px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
            autocomplete="off" />
          <button id="chat-send-btn"
            class="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-blue-400">
            发送
          </button>
        </div>
      </div>
    `;
    document.body.appendChild(container);

    // Cache DOM references
    chatPanel = document.getElementById("chat-panel");
    chatMessages = document.getElementById("chat-messages");
    chatInput = document.getElementById("chat-input");
    chatSendBtn = document.getElementById("chat-send-btn");
    chatToggleBtn = document.getElementById("chat-toggle-btn");

    // Bind events
    chatToggleBtn.addEventListener("click", () => {
      toggleChat();
      document.getElementById("chat-icon-open").classList.toggle("hidden", state.isOpen);
      document.getElementById("chat-icon-close").classList.toggle("hidden", !state.isOpen);
    });

    chatSendBtn.addEventListener("click", sendMessage);
    chatInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });
  }

  // -- Initialize on DOM ready --
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", injectWidget);
  } else {
    injectWidget();
  }
})();
