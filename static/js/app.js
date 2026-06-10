// CodeRefine Client-Side Logic

let currentTab = "review";
let currentAuthTab = "login";
let screenStream = null;
let currentProfile = null;

// Chatbot and Undo/Redo/Restore State (Code Review)
let chatHistory = [];
let codeUndoStack = [];
let codeRedoStack = [];
let originalBaseCode = "";
let activeReviewId = null;

// Chatbot and Undo/Redo/Restore State (Screen Share)
let screenshareChatHistory = [];
let screenshareUndoStack = [];
let screenshareRedoStack = [];
let originalScreenshareBaseCode = "";

// Base API configuration
const API_URL = ""; // Relative paths since frontend is served by FastAPI

// Header helper to include JWT token
function getAuthHeaders() {
  const token = localStorage.getItem("token");
  return {
    "Content-Type": "application/json",
    "Authorization": token ? `Bearer ${token}` : ""
  };
}

// ================= SESSION INITIALIZATION =================
document.addEventListener("DOMContentLoaded", () => {
  checkSession();
  setupAuthTabToggles();
  setupCodeReviewListeners();
});

let autosaveTimeout = null;
function setupCodeReviewListeners() {
  const textarea = document.getElementById("textarea-review-code");
  if (textarea) {
    textarea.addEventListener("input", () => {
      // Clear stacks on manual edit
      codeUndoStack = [];
      codeRedoStack = [];
      updateUndoRedoRestoreButtons();
      
      // Debounced autosave
      if (autosaveTimeout) clearTimeout(autosaveTimeout);
      autosaveTimeout = setTimeout(() => {
        saveCurrentSessionCode();
      }, 1000);
    });
  }
  
  const langSelect = document.getElementById("select-review-lang");
  if (langSelect) {
    langSelect.addEventListener("change", () => {
      saveCurrentSessionCode();
    });
  }
}

function checkSession() {
  const token = localStorage.getItem("token");
  if (token) {
    showDashboardState();
    fetchProfile();
    loadHistory();
  } else {
    showAuthState();
  }
}

function showDashboardState() {
  document.getElementById("auth-portal").classList.add("hidden");
  document.getElementById("dashboard").classList.remove("hidden");
}

function showAuthState() {
  document.getElementById("auth-portal").classList.remove("hidden");
  document.getElementById("dashboard").classList.add("hidden");
}

// ================= AUTHENTICATION FLOWS =================
function setupAuthTabToggles() {
  const loginTabBtn = document.getElementById("auth-tab-login");
  const registerTabBtn = document.getElementById("auth-tab-register");
  const authSubmitBtn = document.getElementById("btn-auth-submit");

  loginTabBtn.addEventListener("click", () => {
    currentAuthTab = "login";
    loginTabBtn.className = "flex-1 pb-3 text-center font-medium border-b-2 border-indigo-500 text-slate-900 dark:text-white transition-all";
    registerTabBtn.className = "flex-1 pb-3 text-center font-medium border-b-2 border-transparent text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 transition-all";
    authSubmitBtn.querySelector("span").textContent = "Sign In";
    clearAuthBanners();
  });

  registerTabBtn.addEventListener("click", () => {
    currentAuthTab = "register";
    registerTabBtn.className = "flex-1 pb-3 text-center font-medium border-b-2 border-indigo-500 text-slate-900 dark:text-white transition-all";
    loginTabBtn.className = "flex-1 pb-3 text-center font-medium border-b-2 border-transparent text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 transition-all";
    authSubmitBtn.querySelector("span").textContent = "Register Account";
    clearAuthBanners();
  });
}

function clearAuthBanners() {
  document.getElementById("auth-error-banner").classList.add("hidden");
  document.getElementById("auth-success-banner").classList.add("hidden");
}

function showAuthError(msg) {
  const banner = document.getElementById("auth-error-banner");
  const text = document.getElementById("auth-error-msg");
  text.textContent = msg;
  banner.classList.remove("hidden");
}

function showAuthSuccess() {
  const banner = document.getElementById("auth-success-banner");
  banner.classList.remove("hidden");
}

async function handleAuthSubmit(event) {
  event.preventDefault();
  clearAuthBanners();

  const usernameInput = document.getElementById("input-username").value.trim();
  const passwordInput = document.getElementById("input-password").value;

  if (!usernameInput || !passwordInput) {
    showAuthError("Username and password are required.");
    return;
  }

  const endpoint = currentAuthTab === "login" ? "/api/auth/login" : "/api/auth/register";
  
  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: usernameInput, password: passwordInput })
    });

    const data = await response.json();

    if (!response.ok) {
      showAuthError(data.detail || "Authentication request failed.");
      return;
    }

    // Both login and registration now return access_token for instant login
    localStorage.setItem("token", data.access_token);
    document.getElementById("input-username").value = "";
    document.getElementById("input-password").value = "";
    showDashboardState();
    fetchProfile();
    loadHistory();
  } catch (err) {
    showAuthError("Server unavailable. Please verify the backend server is running.");
  }
}

async function fetchProfile() {
  try {
    const response = await fetch("/api/auth/me", {
      headers: getAuthHeaders()
    });
    
    if (response.status === 401) {
      logout();
      return;
    }

    const data = await response.json();
    currentProfile = data;

    // Update UI profile elements
    document.getElementById("user-display-name").textContent = data.username;
    document.getElementById("user-avatar-initial").textContent = data.username.charAt(0).toUpperCase();
    document.getElementById("settings-username").textContent = data.username;
    
    const keyStatusEl = document.getElementById("settings-key-status");
    if (data.has_groq_key) {
      keyStatusEl.textContent = `Configured (${data.groq_key_masked})`;
      keyStatusEl.className = "font-mono text-emerald-400 font-semibold";
      document.getElementById("input-groq-key").placeholder = "••••••••••••••••";
    } else {
      keyStatusEl.textContent = "Not Configured (Using System Default)";
      keyStatusEl.className = "font-mono text-slate-500 font-semibold";
      document.getElementById("input-groq-key").placeholder = "gsk-...";
    }
  } catch (err) {
    console.error("Failed to fetch user profile:", err);
  }
}

async function logout() {
  await saveCurrentSessionCode();
  
  localStorage.removeItem("token");
  currentProfile = null;
  activeReviewId = null;
  chatHistory = [];
  
  // Reset fields
  document.getElementById("textarea-review-code").value = "";
  document.getElementById("textarea-complexity-code").value = "";
  document.getElementById("textarea-error-code").value = "";
  document.getElementById("textarea-error-logs").value = "";
  
  // Reset stream
  stopScreenShare();
  
  // Show auth layout
  showAuthState();
}

// ================= HISTORIC REVIEWS =================
async function loadHistory() {
  const container = document.getElementById("history-list-container");
  try {
    const response = await fetch("/api/history", {
      headers: getAuthHeaders()
    });
    
    if (!response.ok) return;
    const history = await response.json();

    if (history.length === 0) {
      container.innerHTML = `<p class="text-xs text-slate-500 text-center py-6">No saved reviews yet.</p>`;
      return;
    }

    container.innerHTML = history.map(item => {
      const dateStr = new Date(item.created_at).toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
      
      return `
        <div onclick='selectHistoryItem(${JSON.stringify(item).replace(/'/g, "&apos;")})' class="glass-panel hover:bg-slate-100 dark:hover:bg-white/5 border border-slate-200 dark:border-white/5 hover:border-slate-300 dark:hover:border-white/10 rounded-xl p-3 flex flex-col gap-1 cursor-pointer transition-all relative group">
          <div class="flex items-center justify-between">
            <span class="text-xs font-semibold text-slate-900 dark:text-white truncate pr-6">${item.title}</span>
            <span class="text-[10px] text-slate-600 dark:text-slate-500 font-mono">${item.language}</span>
          </div>
          <div class="flex items-center justify-between mt-1 text-[10px] text-slate-600 dark:text-slate-500">
            <span>${dateStr}</span>
            <button onclick="deleteHistoryItem(${item.id}, event)" class="opacity-0 group-hover:opacity-100 hover:text-rose-400 p-1 rounded transition-all" title="Delete Review">
              <i class="fa-solid fa-trash-can"></i>
            </button>
          </div>
        </div>
      `;
    }).join("");

  } catch (err) {
    console.error("Error loading history list:", err);
  }
}

async function deleteHistoryItem(id, event) {
  event.stopPropagation(); // Prevent loading review when clicking delete
  
  if (!confirm("Are you sure you want to delete this code review from history?")) return;

  try {
    const response = await fetch(`/api/history/${id}`, {
      method: "DELETE",
      headers: getAuthHeaders()
    });

    if (response.ok) {
      loadHistory();
      // If we deleted the current active review on screen, hide result
      document.getElementById("review-result-container").classList.add("hidden");
      document.getElementById("review-empty-state").classList.remove("hidden");
    }
  } catch (err) {
    alert("Could not delete history item.");
  }
}

async function selectHistoryItem(item) {
  await saveCurrentSessionCode();
  
  switchTab("review");
  
  activeReviewId = item.id;
  
  // Pre-fill input
  document.getElementById("textarea-review-code").value = item.original_code || "";
  document.getElementById("select-review-lang").value = item.language || "python";
  
  // Set original base code and reset stacks
  originalBaseCode = item.original_code || "";
  codeUndoStack = [];
  codeRedoStack = [];
  updateUndoRedoRestoreButtons();
  
  // Populate result view directly
  displayCodeReviewResults(item);
  
  // Restore chatbot with historical messages
  chatHistory = item.chat_history || [];
  const chatbotBox = document.getElementById("chatbot-box");
  if (chatbotBox) {
    chatbotBox.innerHTML = `
      <div class="bg-indigo-500/10 border border-indigo-500/20 text-indigo-950 dark:text-indigo-200 text-xs p-3 rounded-xl max-w-[85%] self-start">
        Hello! I am your Code Review assistant. Ask me to modify, update, improve, or explain the uploaded code above.
      </div>
    `;
    chatHistory.forEach(msg => {
      renderChatbotBubble(msg.role, msg.text);
    });
  }
}

// ================= SETTINGS AND KEYS =================
function openSettingsModal() {
  document.getElementById("settings-modal").classList.remove("hidden");
}

function closeSettingsModal() {
  document.getElementById("settings-modal").classList.add("hidden");
  // Clear modal message
  const banner = document.getElementById("settings-message-banner");
  banner.classList.add("hidden");
}

async function handleSettingsSubmit(event) {
  event.preventDefault();
  const keyInput = document.getElementById("input-groq-key").value.trim();
  const banner = document.getElementById("settings-message-banner");
  const icon = document.getElementById("settings-message-icon");
  const text = document.getElementById("settings-message-text");

  try {
    const response = await fetch("/api/auth/settings", {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({ groq_key: keyInput })
    });

    if (response.ok) {
      banner.className = "mb-4 p-3 rounded-lg text-xs flex items-center gap-2 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400";
      text.textContent = keyInput ? "Groq API Key updated successfully!" : "Groq API Key cleared. Using shared server key.";
      banner.classList.remove("hidden");
      document.getElementById("input-groq-key").value = "";
      
      // Refresh configuration
      fetchProfile();
    } else {
      const data = await response.json();
      banner.className = "mb-4 p-3 rounded-lg text-xs flex items-center gap-2 bg-rose-500/10 border border-rose-500/20 text-rose-400";
      text.textContent = data.detail || "Failed to save settings.";
      banner.classList.remove("hidden");
    }
  } catch (err) {
    banner.className = "mb-4 p-3 rounded-lg text-xs flex items-center gap-2 bg-rose-500/10 border border-rose-500/20 text-rose-400";
    text.textContent = "API error. Please try again.";
    banner.classList.remove("hidden");
  }
}

// ================= WORKSPACE NAVIGATION =================
function switchTab(tabId) {
  currentTab = tabId;
  
  // Set tab button highlights
  const tabs = ["review", "complexity", "explain", "screenshare", "howitworks"];
  tabs.forEach(t => {
    const btn = document.getElementById(`tab-${t}`);
    const panel = document.getElementById(`panel-${t}`);
    
    if (t === tabId) {
      btn.className = "px-5 py-3.5 text-sm font-semibold border-b-2 tab-active flex items-center gap-2 transition-all";
      panel.classList.remove("hidden");
    } else {
      btn.className = "px-5 py-3.5 text-sm font-semibold border-b-2 tab-inactive flex items-center gap-2 transition-all";
      panel.classList.add("hidden");
    }
  });

  // Stop screen shares if navigating away from screenshare tab
  if (tabId !== "screenshare") {
    stopScreenShare();
  }
}

function toggleSidebar() {
  const sidebar = document.getElementById("sidebar");
  const expandBtn = document.getElementById("btn-expand-sidebar");
  
  if (sidebar.classList.contains("md:w-80")) {
    // Collapse
    sidebar.classList.remove("w-full", "md:w-80");
    sidebar.classList.add("w-0", "overflow-hidden");
    expandBtn.classList.remove("hidden");
  } else {
    // Expand
    sidebar.classList.remove("w-0", "overflow-hidden");
    sidebar.classList.add("w-full", "md:w-80");
    expandBtn.classList.add("hidden");
  }
}

// ================= CODE REVIEW HANDLERS =================
async function runCodeReview() {
  const code = document.getElementById("textarea-review-code").value;
  const lang = document.getElementById("select-review-lang").value;
  
  if (!code.trim()) {
    alert("Please enter some code to review first.");
    return;
  }

  if (!isValidSourceCode(code)) {
    alert("This is not code. Please enter valid source code.");
    return;
  }

  // Set UI States
  document.getElementById("review-empty-state").classList.add("hidden");
  document.getElementById("review-result-container").classList.add("hidden");
  document.getElementById("review-loading").classList.remove("hidden");

  try {
    const response = await fetch("/api/review", {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({ code: code, language: lang, review_id: activeReviewId })
    });
 
    if (!response.ok) {
      const errData = await response.json().catch(() => ({ detail: "Analysis failed. Verify your API Key." }));
      alert(errData.detail);
      resetReviewUI();
      return;
    }

    const data = await response.json();

    // Set baseline and reset chatbot session
    originalBaseCode = code;
    resetChatbot();
    activeReviewId = data.id || null;

    // Ensure fields are set to prevent isBlankSession evaluation failure
    data.original_code = code;
    data.language = lang;

    displayCodeReviewResults(data);
    loadHistory(); // Reload SQLite history logs

  } catch (err) {
    alert("Failed to connect to the backend. Please check server logs.");
    resetReviewUI();
  }
}

function resetReviewUI() {
  document.getElementById("review-loading").classList.add("hidden");
  document.getElementById("review-empty-state").classList.remove("hidden");
}

function displayCodeReviewResults(review) {
  document.getElementById("review-loading").classList.add("hidden");
  document.getElementById("review-empty-state").classList.add("hidden");
  document.getElementById("review-result-container").classList.remove("hidden");

  const isBlankSession = !review.original_code || !review.original_code.trim();

  const summaryCard = document.getElementById("review-summary-card");
  const diffsCard = document.getElementById("review-diffs-card");
  const bugsContainer = document.getElementById("review-bugs-container");

  if (isBlankSession) {
    if (summaryCard) summaryCard.classList.add("hidden");
    if (diffsCard) diffsCard.classList.add("hidden");
    if (bugsContainer) bugsContainer.classList.add("hidden");
  } else {
    if (summaryCard) summaryCard.classList.remove("hidden");
    if (diffsCard) diffsCard.classList.remove("hidden");
    
    // Populate values
    document.getElementById("review-result-title").textContent = review.title || "Code Optimization Review";
    
    // Populate recommendations list
    const improvementsList = document.getElementById("review-improvements-list");
    if (review.improvements && review.improvements.length > 0) {
      improvementsList.innerHTML = review.improvements.map(imp => `<li>${escapeHtml(imp)}</li>`).join("");
    } else {
      improvementsList.innerHTML = "<li>No critical optimization recommendations provided.</li>";
    }

    // Populate security badges
    const badgeContainer = document.getElementById("security-badge-container");
    if (review.security_badges && review.security_badges.length > 0) {
      badgeContainer.innerHTML = review.security_badges.map(badge => {
        let colorClass = "bg-indigo-50 dark:bg-indigo-500/10 border-indigo-100 dark:border-indigo-500/25 text-indigo-600 dark:text-indigo-400";
        if (badge.status === "danger") {
          colorClass = "bg-rose-50 dark:bg-rose-500/10 border-rose-100 dark:border-rose-500/25 text-rose-600 dark:text-rose-400";
        } else if (badge.status === "warning") {
          colorClass = "bg-amber-50 dark:bg-amber-500/10 border-amber-100 dark:border-amber-500/25 text-amber-700 dark:text-amber-400";
        } else if (badge.status === "success") {
          colorClass = "bg-emerald-50 dark:bg-emerald-500/10 border-emerald-100 dark:border-emerald-500/25 text-emerald-600 dark:text-emerald-400";
        }
        return `
          <span class="text-[10px] font-semibold ${colorClass} border px-2.5 py-1 rounded-full uppercase tracking-wider" title="${escapeHtml(badge.description)}">
            ${escapeHtml(badge.name)}
          </span>
        `;
      }).join("");
    } else {
      badgeContainer.innerHTML = `<span class="text-[10px] bg-slate-500/10 border-slate-500/25 border text-slate-400 px-2.5 py-1 rounded-full uppercase tracking-wider">No Security Flags</span>`;
    }

    // Populate Bugs
    const bugsList = document.getElementById("review-bugs-list");
    if (review.bugs && review.bugs.length > 0) {
      bugsContainer.classList.remove("hidden");
      bugsList.innerHTML = review.bugs.map(bug => {
        let badgeColor = "bg-slate-100 dark:bg-slate-500/10 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-500/20";
        if (bug.severity === "High") badgeColor = "bg-rose-50 dark:bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-100 dark:border-rose-500/20";
        if (bug.severity === "Medium") badgeColor = "bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-400 border border-amber-100 dark:border-amber-500/20";
        if (bug.severity === "Low") badgeColor = "bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border border-indigo-100 dark:border-indigo-500/20";
        
        return `
          <div class="bg-slate-50 dark:bg-slate-950/60 rounded-xl p-3 border border-slate-200 dark:border-white/5 space-y-1.5">
            <div class="flex items-center gap-2">
              <span class="text-[9px] font-bold px-1.5 py-0.5 rounded uppercase ${badgeColor}">${bug.severity}</span>
              <span class="text-xs font-semibold text-slate-900 dark:text-white">Line ${bug.line_number}</span>
            </div>
            <p class="text-xs text-slate-750 dark:text-slate-300 leading-relaxed">${escapeHtml(bug.description)}</p>
            <div class="text-[10px] text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-400/5 px-2.5 py-1 rounded border border-indigo-200/50 dark:border-indigo-400/10">
              <span class="font-bold">Fix Suggestion:</span> ${escapeHtml(bug.suggestion)}
            </div>
          </div>
        `;
      }).join("");
    } else {
      bugsContainer.classList.add("hidden");
    }

    // Populate Diffs
    document.getElementById("diff-original-code").textContent = document.getElementById("textarea-review-code").value;
    document.getElementById("diff-optimized-code").textContent = review.optimized_code || "";
  }
}

function copyOptimizedCode() {
  const code = document.getElementById("diff-optimized-code").textContent;
  navigator.clipboard.writeText(code);
  alert("Optimized code copied to clipboard!");
}

// ================= COMPLEXITY HANDLERS =================
async function runComplexityAnalysis() {
  const code = document.getElementById("textarea-complexity-code").value;
  const eli5 = document.getElementById("eli5-complexity").checked;

  if (!code.trim()) {
    alert("Please enter code to analyze complexity bounds.");
    return;
  }

  if (!isValidSourceCode(code)) {
    alert("This is not code. Please enter valid source code.");
    return;
  }

  document.getElementById("complexity-empty-state").classList.add("hidden");
  document.getElementById("complexity-result-container").classList.add("hidden");
  document.getElementById("complexity-loading").classList.remove("hidden");

  try {
    const response = await fetch("/api/complexity", {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({ code: code, language: "general", eli5: eli5 })
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({ detail: "Verify API Key settings." }));
      alert(errData.detail);
      resetComplexityUI();
      return;
    }

    const data = await response.json();
    document.getElementById("complexity-loading").classList.add("hidden");
    document.getElementById("complexity-result-container").classList.remove("hidden");

    // Populate caps
    document.getElementById("complexity-best").textContent = data.best_case || "O(1)";
    document.getElementById("complexity-average").textContent = data.average_case || "O(N)";
    document.getElementById("complexity-worst").textContent = data.worst_case || "O(N)";
    
    // Explanation
    document.getElementById("complexity-explanation").textContent = data.explanation || "";
    
    // Traceout
    document.getElementById("complexity-traceout").textContent = data.traceout || "";

  } catch (err) {
    alert("Network error. Please try again.");
    resetComplexityUI();
  }
}

function resetComplexityUI() {
  document.getElementById("complexity-loading").classList.add("hidden");
  document.getElementById("complexity-empty-state").classList.remove("hidden");
}

// ================= ERROR DIAGNOSTIC HANDLERS =================
async function runErrorExplain() {
  const code = document.getElementById("textarea-error-code").value;
  const logs = document.getElementById("textarea-error-logs").value;
  const eli5 = document.getElementById("eli5-error").checked;

  if (!code.trim() && !logs.trim()) {
    alert("Please provide either source code or error logs.");
    return;
  }

  if (code.trim() && !isValidSourceCode(code)) {
    alert("This is not code. Please enter valid source code.");
    return;
  }

  document.getElementById("error-empty-state").classList.add("hidden");
  document.getElementById("error-result-container").classList.add("hidden");
  document.getElementById("error-loading").classList.remove("hidden");

  try {
    const response = await fetch("/api/explain-error", {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({ code: code, error_logs: logs, eli5: eli5 })
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({ detail: "Check console error outputs." }));
      alert(errData.detail);
      resetErrorUI();
      return;
    }

    const data = await response.json();
    document.getElementById("error-loading").classList.add("hidden");
    document.getElementById("error-result-container").classList.remove("hidden");

    // Populate outputs
    document.getElementById("error-summary-txt").textContent = data.error_summary || "Diagnosed Exception";
    document.getElementById("error-explanation-txt").textContent = data.explanation || "";
    document.getElementById("error-fixed-code").textContent = data.fixed_code || "";

    // Resources list
    const resourcesList = document.getElementById("error-resources-list");
    if (data.resources && data.resources.length > 0) {
      resourcesList.innerHTML = data.resources.map(res => `
        <div class="rounded-xl p-4 glass-panel space-y-3">
          <div class="text-xs font-semibold text-slate-900 dark:text-white flex items-center gap-1.5">
            <i class="fa-solid fa-graduation-cap text-indigo-600 dark:text-indigo-400"></i>
            <span>${escapeHtml(res.topic)}</span>
          </div>
          <div class="flex items-center gap-2">
            <a href="${res.youtube}" target="_blank" class="flex-1 text-center bg-rose-600/10 hover:bg-rose-600/20 text-rose-600 dark:text-rose-400 border border-rose-200 dark:border-rose-500/20 text-[10px] font-semibold py-2 rounded-lg transition-all flex items-center justify-center gap-1.5">
              <i class="fa-brands fa-youtube"></i>
              YouTube Tutorials
            </a>
            <a href="${res.geeksforgeeks}" target="_blank" class="flex-1 text-center bg-emerald-600/10 hover:bg-emerald-600/20 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-500/20 text-[10px] font-semibold py-2 rounded-lg transition-all flex items-center justify-center gap-1.5">
              <i class="fa-solid fa-book-open"></i>
              GeeksforGeeks
            </a>
          </div>
        </div>
      `).join("");
    } else {
      resourcesList.innerHTML = `<p class="text-xs text-slate-500 col-span-2">No educational topics identified.</p>`;
    }

  } catch (err) {
    alert("Diagnostic network exception.");
    resetErrorUI();
  }
}

function resetErrorUI() {
  document.getElementById("error-loading").classList.add("hidden");
  document.getElementById("error-empty-state").classList.remove("hidden");
}

function copyFixedErrorCode() {
  const code = document.getElementById("error-fixed-code").textContent;
  navigator.clipboard.writeText(code);
  alert("Proposed code copied to clipboard!");
}

// ================= MULTIMODAL SCREEN SHARING =================
async function toggleScreenShare() {
  if (screenStream) {
    stopScreenShare();
  } else {
    try {
      // Prompt user to select window/screen to share
      screenStream = await navigator.mediaDevices.getDisplayMedia({
        video: {
          cursor: "always"
        },
        audio: false
      });

      const video = document.getElementById("video-screenshare");
      video.srcObject = screenStream;
      video.classList.remove("hidden");
      
      document.getElementById("screenshare-video-placeholder").classList.add("hidden");
      document.getElementById("screenshare-pulse-dot").classList.remove("hidden");

      // Update button state
      document.getElementById("btn-toggle-share-txt").textContent = "Stop Sharing";
      const captureBtn = document.getElementById("btn-capture-frame");
      captureBtn.removeAttribute("disabled");
      captureBtn.classList.remove("opacity-50", "cursor-not-allowed");

      // Handle stream stop by user directly clicking browser "Stop sharing" ribbon
      screenStream.getVideoTracks()[0].addEventListener("ended", () => {
        stopScreenShare();
      });

    } catch (err) {
      console.warn("Screen sharing permission denied or failed:", err);
    }
  }
}

function stopScreenShare() {
  if (screenStream) {
    screenStream.getTracks().forEach(track => track.stop());
    screenStream = null;
  }

  const video = document.getElementById("video-screenshare");
  video.srcObject = null;
  video.classList.add("hidden");

  document.getElementById("screenshare-video-placeholder").classList.remove("hidden");
  document.getElementById("screenshare-pulse-dot").classList.add("hidden");

  document.getElementById("btn-toggle-share-txt").textContent = "Share Screen";
  
  const captureBtn = document.getElementById("btn-capture-frame");
  captureBtn.setAttribute("disabled", "true");
  captureBtn.classList.add("opacity-50", "cursor-not-allowed");
}

async function captureAndAnalyzeFrame() {
  if (!screenStream) return;

  const video = document.getElementById("video-screenshare");
  const canvas = document.getElementById("hidden-canvas");
  const ctx = canvas.getContext("2d");

  // Match canvas size to current active screen share stream dimensions
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;

  // Draw current video element frames on canvas
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

  // Convert canvas contents to Base64 dataURL
  const dataURL = canvas.toDataURL("image/png");

  // Shutdown the stream instantly to conserve resources
  stopScreenShare();

  // Loaders
  document.getElementById("screenshare-empty-state").classList.add("hidden");
  document.getElementById("screenshare-result-container").classList.add("hidden");
  document.getElementById("screenshare-loading").classList.remove("hidden");

  try {
    const response = await fetch("/api/screen-capture", {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({ image: dataURL })
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({ detail: "Ensure key parameters are set." }));
      alert(errData.detail);
      resetScreenshareUI();
      return;
    }

    const data = await response.json();
    document.getElementById("screenshare-loading").classList.add("hidden");
    document.getElementById("screenshare-result-container").classList.remove("hidden");

    // Populate visual diagnostics
    document.getElementById("screenshare-badge-lang").textContent = data.language || "code";
    document.getElementById("screenshare-detected-error").textContent = data.detected_error || "Exception Spotted";
    document.getElementById("screenshare-explanation").textContent = data.explanation || "";
    document.getElementById("screenshare-original-code").textContent = data.original_code_snippet || "";
    document.getElementById("screenshare-fixed-code").textContent = data.fixed_code_snippet || "";

    // Set baseline and reset screenshare chatbot
    originalScreenshareBaseCode = data.fixed_code_snippet || "";
    resetScreenshareChatbot();

  } catch (err) {
    alert("Network vision exception.");
    resetScreenshareUI();
  }
}

function resetScreenshareUI() {
  document.getElementById("screenshare-loading").classList.add("hidden");
  document.getElementById("screenshare-empty-state").classList.remove("hidden");
}

function copyScreenshareCode() {
  const code = document.getElementById("screenshare-fixed-code").textContent;
  navigator.clipboard.writeText(code);
  alert("Corrected snippet copied!");
}

// ================= GENERAL HELPERS =================
function escapeHtml(text) {
  if (!text) return "";
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// ================= SOURCE CODE VALIDATION =================
function isValidSourceCode(text) {
  const textStripped = text.trim();
  if (!textStripped) return false;
  
  const keywords = new Set([
    "def", "function", "fn", "import", "from", "include", "public", "class", 
    "struct", "void", "return", "if", "for", "while", "else", "elif", "except", 
    "try", "catch", "throw", "let", "const", "var", "int", "float", "char", "double",
    "println", "printf", "cout", "print", "console", "using", "namespace", "std",
    "System", "out"
  ]);
  
  // Find words
  const words = textStripped.match(/\b\w+\b/g) || [];
  const hasKeyword = words.some(w => keywords.has(w));
  
  // Check common syntax symbols
  const syntaxTokens = ['{', '}', ';', '(', ')', '[', ']', '=', '+', '-', '*', '/', '<', '>', ':', '"', "'"];
  let syntaxCount = 0;
  for (const char of textStripped) {
    if (syntaxTokens.includes(char)) {
      syntaxCount++;
    }
  }
  
  return hasKeyword || syntaxCount >= 1;
}

// ================= CODE REVIEW CHATBOT AND UNDO/REDO/RESTORE =================

function resetChatbot() {
  chatHistory = [];
  codeUndoStack = [];
  codeRedoStack = [];
  
  const chatbotBox = document.getElementById("chatbot-box");
  if (chatbotBox) {
    chatbotBox.innerHTML = `
      <div class="bg-indigo-500/10 border border-indigo-500/20 text-indigo-950 dark:text-indigo-200 text-xs p-3 rounded-xl max-w-[85%] self-start">
        Hello! I am your Code Review assistant. Ask me to modify, update, improve, or explain the uploaded code above.
      </div>
    `;
  }
  updateUndoRedoRestoreButtons();
}

async function startNewChat() {
  await saveCurrentSessionCode();
  
  try {
    const response = await fetch("/api/review/new", {
      method: "POST",
      headers: getAuthHeaders()
    });
    
    if (!response.ok) {
      const errData = await response.json().catch(() => ({ detail: "Failed to start a new chat." }));
      alert(errData.detail);
      return;
    }
    
    const newReview = await response.json();
    
    // Set the new review ID as active
    activeReviewId = newReview.id;
    
    // Reset inputs and workspace code views
    document.getElementById("textarea-review-code").value = "";
    document.getElementById("diff-original-code").textContent = "";
    document.getElementById("diff-optimized-code").textContent = "";
    originalBaseCode = "";
    
    // Clear chat history and set interface to chatbot focus
    resetChatbot();
    displayCodeReviewResults(newReview);
    
    // Reload history panel so the new copy is displayed in the sidebar
    await loadHistory();
    
  } catch (err) {
    alert("Network error starting new chat.");
  }
}

function updateUndoRedoRestoreButtons() {
  const btnUndo = document.getElementById("btn-chatbot-undo");
  const btnRedo = document.getElementById("btn-chatbot-redo");
  const btnRestore = document.getElementById("btn-chatbot-restore");
  const textarea = document.getElementById("textarea-review-code");
  
  if (btnUndo) {
    if (codeUndoStack.length > 0) {
      btnUndo.classList.remove("hidden");
    } else {
      btnUndo.classList.add("hidden");
    }
  }
  
  if (btnRedo) {
    if (codeRedoStack.length > 0) {
      btnRedo.classList.remove("hidden");
    } else {
      btnRedo.classList.add("hidden");
    }
  }
  
  if (btnRestore && textarea) {
    const currentCode = textarea.value;
    if (originalBaseCode && currentCode !== originalBaseCode) {
      btnRestore.classList.remove("hidden");
    } else {
      btnRestore.classList.add("hidden");
    }
  }
}

async function sendChatbotMessage(event) {
  event.preventDefault();
  
  const msgInput = document.getElementById("input-chatbot-msg");
  if (!msgInput) return;
  
  const message = msgInput.value.trim();
  if (!message) return;
  
  // Clear input
  msgInput.value = "";
  
  // Render user bubble
  renderChatbotBubble("user", message);
  
  // Push to history
  chatHistory.push({ role: "user", text: message });
  
  const code = document.getElementById("textarea-review-code").value;
  const lang = document.getElementById("select-review-lang").value;
  
  // Show loading indicator
  const chatbotBox = document.getElementById("chatbot-box");
  const loaderId = "chatbot-loader-" + Date.now();
  const loaderHtml = `
    <div id="${loaderId}" class="bg-indigo-500/5 border border-indigo-500/10 text-slate-400 text-xs p-3 rounded-xl max-w-[85%] self-start flex items-center gap-2">
      <div class="w-3 h-3 border-2 border-indigo-500/20 border-t-indigo-500 rounded-full animate-spin"></div>
      <span>Assistant is typing...</span>
    </div>
  `;
  chatbotBox.insertAdjacentHTML("beforeend", loaderHtml);
  chatbotBox.scrollTop = chatbotBox.scrollHeight;
  
  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({
        code: code,
        language: lang,
        message: message,
        history: chatHistory,
        review_id: activeReviewId
      })
    });
    
    // Remove loader
    const loaderEl = document.getElementById(loaderId);
    if (loaderEl) loaderEl.remove();
    
    if (!response.ok) {
      const errData = await response.json().catch(() => ({ detail: "Chat failed. Verify your API Key." }));
      renderChatbotBubble("model", `Error: ${errData.detail || "Unable to retrieve response."}`);
      return;
    }
    
    const data = await response.json();
    const botText = data.text || "";
    
    // Render assistant response
    renderChatbotBubble("model", botText);
    
    // Push to history
    chatHistory.push({ role: "model", text: botText });
    
    // Reload history list if it was a new untitled chat to update the title in the sidebar
    if (chatHistory.length <= 2) {
      loadHistory();
    }
    
  } catch (err) {
    const loaderEl = document.getElementById(loaderId);
    if (loaderEl) loaderEl.remove();
    renderChatbotBubble("model", "Network error. Please try again.");
  }
}

// Global container to store code suggestions for Accept/Reject
let suggestedCodeSuggestions = {};

function renderChatbotBubble(sender, text) {
  const chatbotBox = document.getElementById("chatbot-box");
  if (!chatbotBox) return;
  
  const isUser = sender === "user";
  const alignClass = isUser ? "self-end bg-indigo-600 text-white" : "self-start bg-slate-100 dark:bg-slate-900 border border-slate-200 dark:border-white/5 text-slate-800 dark:text-slate-200";
  
  // Parse markdown code blocks in bot response
  let bubbleContent = "";
  if (isUser) {
    bubbleContent = escapeHtml(text).replace(/\n/g, "<br>");
  } else {
    // Process markdown code blocks: ```[lang]\n[code]\n```
    const regex = /```(\w*)\n([\s\S]*?)\n```/g;
    let lastIndex = 0;
    let match;
    
    while ((match = regex.exec(text)) !== null) {
      const precedingText = text.substring(lastIndex, match.index);
      if (precedingText) {
        bubbleContent += formatBotText(precedingText);
      }
      
      const lang = match[1] || "code";
      const code = match[2];
      const codeId = "code-suggestion-" + Date.now() + "-" + Math.floor(Math.random() * 1000);
      
      // Store code globally for application
      suggestedCodeSuggestions[codeId] = code;
      
      bubbleContent += `
        <div class="my-3 border border-indigo-200 dark:border-indigo-500/20 rounded-xl overflow-hidden bg-slate-50 dark:bg-slate-950">
          <div class="flex items-center justify-between px-3 py-1.5 bg-slate-100 dark:bg-slate-900 border-b border-indigo-200 dark:border-indigo-500/10 text-[10px] text-slate-600 dark:text-slate-400">
            <span class="font-mono uppercase">${lang}</span>
            <span class="font-semibold text-indigo-600 dark:text-indigo-400">Suggested Code</span>
          </div>
          <pre class="p-3 text-[11px] font-mono overflow-x-auto text-indigo-950 dark:text-indigo-200">${escapeHtml(code)}</pre>
          <div id="actions-${codeId}" class="flex border-t border-indigo-200 dark:border-indigo-500/10 text-xs">
            <button type="button" onclick="applyChatbotCode('${codeId}')" class="flex-1 py-2 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 font-semibold border-r border-indigo-200 dark:border-indigo-500/10 transition-all flex items-center justify-center gap-1">
              <i class="fa-solid fa-check"></i> Accept Changes
            </button>
            <button type="button" onclick="rejectChatbotCode('${codeId}')" class="flex-1 py-2 bg-rose-500/10 hover:bg-rose-500/20 text-rose-600 dark:text-rose-400 font-semibold transition-all flex items-center justify-center gap-1">
              <i class="fa-solid fa-xmark"></i> Reject
            </button>
          </div>
        </div>
      `;
      
      lastIndex = regex.lastIndex;
    }
    
    const remainingText = text.substring(lastIndex);
    if (remainingText) {
      bubbleContent += formatBotText(remainingText);
    }
  }
  
  const bubbleHtml = `
    <div class="${alignClass} text-xs p-3 rounded-xl max-w-[85%] leading-relaxed">
      ${bubbleContent}
    </div>
  `;
  
  chatbotBox.insertAdjacentHTML("beforeend", bubbleHtml);
  chatbotBox.scrollTop = chatbotBox.scrollHeight;
}

function formatBotText(text) {
  // Simple markdown-to-html helper for inline code and linebreaks
  return escapeHtml(text)
    .replace(/\n/g, "<br>")
    .replace(/`([^`]+)`/g, '<code class="bg-slate-200 dark:bg-slate-950 px-1 py-0.5 rounded text-indigo-700 dark:text-indigo-300 font-mono text-[10px]">$1</code>');
}

function applyChatbotCode(codeId) {
  const code = suggestedCodeSuggestions[codeId];
  if (!code) return;
  
  const textarea = document.getElementById("textarea-review-code");
  if (!textarea) return;
  
  // Push to undo stack
  codeUndoStack.push(textarea.value);
  
  // Clear redo stack on new action
  codeRedoStack = [];
  
  // Update editor value
  textarea.value = code;
  
  // Hide actions panel for this suggestion
  const actionsEl = document.getElementById(`actions-${codeId}`);
  if (actionsEl) {
    actionsEl.innerHTML = `
      <div class="w-full py-1.5 text-center text-emerald-400 bg-emerald-500/5 font-semibold text-[10px] flex items-center justify-center gap-1">
        <i class="fa-solid fa-circle-check"></i> Changes Applied to Editor
      </div>
    `;
  }
  
  updateUndoRedoRestoreButtons();
}

function rejectChatbotCode(codeId) {
  // Hide actions panel for this suggestion
  const actionsEl = document.getElementById(`actions-${codeId}`);
  if (actionsEl) {
    actionsEl.innerHTML = `
      <div class="w-full py-1.5 text-center text-slate-500 bg-white/5 font-medium text-[10px]">
        Suggestion Declined
      </div>
    `;
  }
}

function undoLastAppliedCode() {
  if (codeUndoStack.length === 0) return;
  
  const textarea = document.getElementById("textarea-review-code");
  if (!textarea) return;
  
  // Push current state to redo stack
  codeRedoStack.push(textarea.value);
  
  // Revert code
  textarea.value = codeUndoStack.pop();
  
  updateUndoRedoRestoreButtons();
}

function redoLastUndoneCode() {
  if (codeRedoStack.length === 0) return;
  
  const textarea = document.getElementById("textarea-review-code");
  if (!textarea) return;
  
  // Push current state to undo stack
  codeUndoStack.push(textarea.value);
  
  // Re-apply code
  textarea.value = codeRedoStack.pop();
  
  updateUndoRedoRestoreButtons();
}

function restoreOriginalReviewCode() {
  if (!originalBaseCode) return;
  
  const textarea = document.getElementById("textarea-review-code");
  if (!textarea) return;
  
  if (textarea.value === originalBaseCode) return;
  
  // Push current to undo stack so restore itself can be undone!
  codeUndoStack.push(textarea.value);
  codeRedoStack = [];
  
  textarea.value = originalBaseCode;
  
  updateUndoRedoRestoreButtons();
}

// ================= SCREEN SHARE CHATBOT AND UNDO/REDO/RESTORE =================

function resetScreenshareChatbot() {
  screenshareChatHistory = [];
  screenshareUndoStack = [];
  screenshareRedoStack = [];
  
  const chatbotBox = document.getElementById("screenshare-chatbot-box");
  if (chatbotBox) {
    chatbotBox.innerHTML = `
      <div class="bg-emerald-500/10 border border-emerald-500/20 text-emerald-950 dark:text-emerald-200 text-xs p-3 rounded-xl max-w-[85%] self-start">
        Hello! I am your Screen Share code assistant. Ask me to modify, update, improve, or explain the captured code above.
      </div>
    `;
  }
  updateScreenshareUndoRedoRestoreButtons();
}

function updateScreenshareUndoRedoRestoreButtons() {
  const btnUndo = document.getElementById("btn-screenshare-undo");
  const btnRedo = document.getElementById("btn-screenshare-redo");
  const btnRestore = document.getElementById("btn-screenshare-restore");
  const fixedCodeContainer = document.getElementById("screenshare-fixed-code");
  
  if (btnUndo) {
    if (screenshareUndoStack.length > 0) {
      btnUndo.classList.remove("hidden");
    } else {
      btnUndo.classList.add("hidden");
    }
  }
  
  if (btnRedo) {
    if (screenshareRedoStack.length > 0) {
      btnRedo.classList.remove("hidden");
    } else {
      btnRedo.classList.add("hidden");
    }
  }
  
  if (btnRestore && fixedCodeContainer) {
    const currentCode = fixedCodeContainer.textContent;
    if (originalScreenshareBaseCode && currentCode !== originalScreenshareBaseCode) {
      btnRestore.classList.remove("hidden");
    } else {
      btnRestore.classList.add("hidden");
    }
  }
}

async function sendScreenshareChatbotMessage(event) {
  event.preventDefault();
  
  const msgInput = document.getElementById("input-screenshare-chatbot-msg");
  if (!msgInput) return;
  
  const message = msgInput.value.trim();
  if (!message) return;
  
  // Clear input
  msgInput.value = "";
  
  // Render user bubble
  renderScreenshareChatbotBubble("user", message);
  
  // Push to history
  screenshareChatHistory.push({ role: "user", text: message });
  
  const codeContainer = document.getElementById("screenshare-fixed-code");
  const code = codeContainer ? codeContainer.textContent : "";
  
  // Show loading indicator
  const chatbotBox = document.getElementById("screenshare-chatbot-box");
  const loaderId = "screenshare-chatbot-loader-" + Date.now();
  const loaderHtml = `
    <div id="${loaderId}" class="bg-emerald-500/5 border border-emerald-500/10 text-slate-400 text-xs p-3 rounded-xl max-w-[85%] self-start flex items-center gap-2">
      <div class="w-3 h-3 border-2 border-emerald-500/20 border-t-emerald-500 rounded-full animate-spin"></div>
      <span>Assistant is typing...</span>
    </div>
  `;
  chatbotBox.insertAdjacentHTML("beforeend", loaderHtml);
  chatbotBox.scrollTop = chatbotBox.scrollHeight;
  
  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({
        code: code,
        message: message,
        history: screenshareChatHistory
      })
    });
    
    // Remove loader
    const loaderEl = document.getElementById(loaderId);
    if (loaderEl) loaderEl.remove();
    
    if (!response.ok) {
      const errData = await response.json().catch(() => ({ detail: "Chat failed. Verify your API Key." }));
      renderScreenshareChatbotBubble("model", `Error: ${errData.detail || "Unable to retrieve response."}`);
      return;
    }
    
    const data = await response.json();
    const botText = data.text || "";
    
    // Render assistant response
    renderScreenshareChatbotBubble("model", botText);
    
    // Push to history
    screenshareChatHistory.push({ role: "model", text: botText });
    
  } catch (err) {
    const loaderEl = document.getElementById(loaderId);
    if (loaderEl) loaderEl.remove();
    renderScreenshareChatbotBubble("model", "Network error. Please try again.");
  }
}

// Global container to store code suggestions for Accept/Reject (Screen Share)
let suggestedScreenshareCodeSuggestions = {};

function renderScreenshareChatbotBubble(sender, text) {
  const chatbotBox = document.getElementById("screenshare-chatbot-box");
  if (!chatbotBox) return;
  
  const isUser = sender === "user";
  const alignClass = isUser ? "self-end bg-emerald-600 text-white" : "self-start bg-slate-100 dark:bg-slate-900 border border-slate-200 dark:border-white/5 text-slate-800 dark:text-slate-200";
  
  // Parse markdown code blocks in bot response
  let bubbleContent = "";
  if (isUser) {
    bubbleContent = escapeHtml(text).replace(/\n/g, "<br>");
  } else {
    // Process markdown code blocks: ```[lang]\n[code]\n```
    const regex = /```(\w*)\n([\s\S]*?)\n```/g;
    let lastIndex = 0;
    let match;
    
    while ((match = regex.exec(text)) !== null) {
      const precedingText = text.substring(lastIndex, match.index);
      if (precedingText) {
        bubbleContent += formatBotText(precedingText);
      }
      
      const lang = match[1] || "code";
      const code = match[2];
      const codeId = "screenshare-code-suggestion-" + Date.now() + "-" + Math.floor(Math.random() * 1000);
      
      // Store code globally for application
      suggestedScreenshareCodeSuggestions[codeId] = code;
      
      bubbleContent += `
        <div class="my-3 border border-emerald-200 dark:border-emerald-500/20 rounded-xl overflow-hidden bg-slate-50 dark:bg-slate-950">
          <div class="flex items-center justify-between px-3 py-1.5 bg-slate-100 dark:bg-slate-900 border-b border-emerald-200 dark:border-emerald-500/10 text-[10px] text-slate-600 dark:text-slate-400">
            <span class="font-mono uppercase">${lang}</span>
            <span class="font-semibold text-emerald-600 dark:text-emerald-400">Suggested Code</span>
          </div>
          <pre class="p-3 text-[11px] font-mono overflow-x-auto text-emerald-950 dark:text-indigo-200">${escapeHtml(code)}</pre>
          <div id="actions-${codeId}" class="flex border-t border-emerald-200 dark:border-emerald-500/10 text-xs">
            <button type="button" onclick="applyScreenshareChatbotCode('${codeId}')" class="flex-1 py-2 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 font-semibold border-r border-emerald-200 dark:border-emerald-500/10 transition-all flex items-center justify-center gap-1">
              <i class="fa-solid fa-check"></i> Accept Changes
            </button>
            <button type="button" onclick="rejectScreenshareChatbotCode('${codeId}')" class="flex-1 py-2 bg-rose-500/10 hover:bg-rose-500/20 text-rose-600 dark:text-rose-400 font-semibold transition-all flex items-center justify-center gap-1">
              <i class="fa-solid fa-xmark"></i> Reject
            </button>
          </div>
        </div>
      `;
      
      lastIndex = regex.lastIndex;
    }
    
    const remainingText = text.substring(lastIndex);
    if (remainingText) {
      bubbleContent += formatBotText(remainingText);
    }
  }
  
  const bubbleHtml = `
    <div class="${alignClass} text-xs p-3 rounded-xl max-w-[85%] leading-relaxed">
      ${bubbleContent}
    </div>
  `;
  
  chatbotBox.insertAdjacentHTML("beforeend", bubbleHtml);
  chatbotBox.scrollTop = chatbotBox.scrollHeight;
}

function applyScreenshareChatbotCode(codeId) {
  const code = suggestedScreenshareCodeSuggestions[codeId];
  if (!code) return;
  
  const codeContainer = document.getElementById("screenshare-fixed-code");
  if (!codeContainer) return;
  
  // Push to undo stack
  screenshareUndoStack.push(codeContainer.textContent);
  
  // Clear redo stack on new action
  screenshareRedoStack = [];
  
  // Update editor value
  codeContainer.textContent = code;
  
  // Hide actions panel for this suggestion
  const actionsEl = document.getElementById(`actions-${codeId}`);
  if (actionsEl) {
    actionsEl.innerHTML = `
      <div class="w-full py-1.5 text-center text-emerald-400 bg-emerald-500/5 font-semibold text-[10px] flex items-center justify-center gap-1">
        <i class="fa-solid fa-circle-check"></i> Changes Applied to Screen Share Code
      </div>
    `;
  }
  
  updateScreenshareUndoRedoRestoreButtons();
}

function rejectScreenshareChatbotCode(codeId) {
  // Hide actions panel for this suggestion
  const actionsEl = document.getElementById(`actions-${codeId}`);
  if (actionsEl) {
    actionsEl.innerHTML = `
      <div class="w-full py-1.5 text-center text-slate-500 bg-white/5 font-medium text-[10px]">
        Suggestion Declined
      </div>
    `;
  }
}

function undoLastAppliedScreenshareCode() {
  if (screenshareUndoStack.length === 0) return;
  
  const codeContainer = document.getElementById("screenshare-fixed-code");
  if (!codeContainer) return;
  
  // Push current state to redo stack
  screenshareRedoStack.push(codeContainer.textContent);
  
  // Revert code
  codeContainer.textContent = screenshareUndoStack.pop();
  
  updateScreenshareUndoRedoRestoreButtons();
}

function redoLastUndoneScreenshareCode() {
  if (screenshareRedoStack.length === 0) return;
  
  const codeContainer = document.getElementById("screenshare-fixed-code");
  if (!codeContainer) return;
  
  // Push current state to undo stack
  screenshareUndoStack.push(codeContainer.textContent);
  
  // Re-apply code
  codeContainer.textContent = screenshareRedoStack.pop();
  
  updateScreenshareUndoRedoRestoreButtons();
}

function restoreOriginalScreenshareCode() {
  if (!originalScreenshareBaseCode) return;
  
  const codeContainer = document.getElementById("screenshare-fixed-code");
  if (!codeContainer) return;
  
  if (codeContainer.textContent === originalScreenshareBaseCode) return;
  
  // Push current to undo stack so restore itself can be undone!
  screenshareUndoStack.push(codeContainer.textContent);
  screenshareRedoStack = [];
  
  codeContainer.textContent = originalScreenshareBaseCode;
  
  updateScreenshareUndoRedoRestoreButtons();
}

function toggleTheme() {
  const isDark = document.documentElement.classList.contains("dark");
  if (isDark) {
    document.documentElement.classList.remove("dark");
    localStorage.setItem("theme", "light");
  } else {
    document.documentElement.classList.add("dark");
    localStorage.setItem("theme", "dark");
  }
}
 
async function saveCurrentSessionCode() {
  if (!activeReviewId) return;
  const code = document.getElementById("textarea-review-code").value;
  const lang = document.getElementById("select-review-lang").value;
  try {
    await fetch("/api/review/update", {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({ id: activeReviewId, code: code, language: lang })
    });
  } catch (err) {
    console.error("Failed to auto-save current session:", err);
  }
}
