// CodeRefine Client-Side Logic

let currentTab = "review";
let currentAuthTab = "login";
let screenStream = null;
let currentProfile = null;

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
});

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
    loginTabBtn.className = "flex-1 pb-3 text-center font-medium border-b-2 border-indigo-500 text-white transition-all";
    registerTabBtn.className = "flex-1 pb-3 text-center font-medium border-b-2 border-transparent text-slate-400 hover:text-slate-200 transition-all";
    authSubmitBtn.querySelector("span").textContent = "Sign In";
    clearAuthBanners();
  });

  registerTabBtn.addEventListener("click", () => {
    currentAuthTab = "register";
    registerTabBtn.className = "flex-1 pb-3 text-center font-medium border-b-2 border-indigo-500 text-white transition-all";
    loginTabBtn.className = "flex-1 pb-3 text-center font-medium border-b-2 border-transparent text-slate-400 hover:text-slate-200 transition-all";
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

    if (currentAuthTab === "login") {
      localStorage.setItem("token", data.access_token);
      document.getElementById("input-username").value = "";
      document.getElementById("input-password").value = "";
      showDashboardState();
      fetchProfile();
      loadHistory();
    } else {
      // Registration successful: switch to login
      showAuthSuccess();
      document.getElementById("auth-tab-login").click();
      document.getElementById("input-password").value = "";
    }
  } catch (err) {
    showAuthError("Server unavailable. Please verify uvicorn is running.");
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
    if (data.has_gemini_key) {
      keyStatusEl.textContent = `Configured (${data.gemini_key_masked})`;
      keyStatusEl.className = "font-mono text-emerald-400 font-semibold";
      document.getElementById("input-gemini-key").placeholder = "••••••••••••••••";
    } else {
      keyStatusEl.textContent = "Not Configured (Using System Default)";
      keyStatusEl.className = "font-mono text-slate-500 font-semibold";
      document.getElementById("input-gemini-key").placeholder = "AIzaSy...";
    }
  } catch (err) {
    console.error("Failed to fetch user profile:", err);
  }
}

function logout() {
  localStorage.removeItem("token");
  currentProfile = null;
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
        <div onclick='selectHistoryItem(${JSON.stringify(item).replace(/'/g, "&apos;")})' class="glass-panel hover:bg-white/5 border border-white/5 hover:border-white/10 rounded-xl p-3 flex flex-col gap-1 cursor-pointer transition-all relative group">
          <div class="flex items-center justify-between">
            <span class="text-xs font-semibold text-white truncate pr-6">${item.title}</span>
            <span class="text-[10px] text-slate-500 font-mono">${item.language}</span>
          </div>
          <div class="flex items-center justify-between mt-1 text-[10px] text-slate-500">
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

function selectHistoryItem(item) {
  switchTab("review");
  
  // Pre-fill input
  document.getElementById("textarea-review-code").value = item.original_code;
  document.getElementById("select-review-lang").value = item.language;
  
  // Populate result view directly
  displayCodeReviewResults(item.review_json);
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
  const keyInput = document.getElementById("input-gemini-key").value.trim();
  const banner = document.getElementById("settings-message-banner");
  const icon = document.getElementById("settings-message-icon");
  const text = document.getElementById("settings-message-text");

  if (!keyInput) {
    banner.className = "mb-4 p-3 rounded-lg text-xs flex items-center gap-2 bg-rose-500/10 border border-rose-500/20 text-rose-400";
    text.textContent = "Please enter a valid key.";
    banner.classList.remove("hidden");
    return;
  }

  try {
    const response = await fetch("/api/auth/settings", {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({ gemini_key: keyInput })
    });

    if (response.ok) {
      banner.className = "mb-4 p-3 rounded-lg text-xs flex items-center gap-2 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400";
      text.textContent = "Gemini API Key updated successfully!";
      banner.classList.remove("hidden");
      document.getElementById("input-gemini-key").value = "";
      
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

  // Set UI States
  document.getElementById("review-empty-state").classList.add("hidden");
  document.getElementById("review-result-container").classList.add("hidden");
  document.getElementById("review-loading").classList.remove("hidden");

  try {
    const response = await fetch("/api/review", {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({ code: code, language: lang })
    });

    const data = await response.ok ? await response.json() : null;

    if (!response.ok) {
      const errData = await response.json().catch(() => ({ detail: "Analysis failed. Verify your API Key." }));
      alert(`Error: ${errData.detail}`);
      resetReviewUI();
      return;
    }

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
      let colorClass = "bg-indigo-500/10 border-indigo-500/25 text-indigo-400";
      if (badge.status === "danger") {
        colorClass = "bg-rose-500/10 border-rose-500/25 text-rose-400";
      } else if (badge.status === "warning") {
        colorClass = "bg-amber-500/10 border-amber-500/25 text-amber-400";
      } else if (badge.status === "success") {
        colorClass = "bg-emerald-500/10 border-emerald-500/25 text-emerald-400";
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
  const bugsContainer = document.getElementById("review-bugs-container");
  const bugsList = document.getElementById("review-bugs-list");
  if (review.bugs && review.bugs.length > 0) {
    bugsContainer.classList.remove("hidden");
    bugsList.innerHTML = review.bugs.map(bug => {
      let badgeColor = "bg-slate-500/10 text-slate-400";
      if (bug.severity === "High") badgeColor = "bg-rose-500/10 text-rose-400 border border-rose-500/20";
      if (bug.severity === "Medium") badgeColor = "bg-amber-500/10 text-amber-400 border border-amber-500/20";
      if (bug.severity === "Low") badgeColor = "bg-indigo-500/10 text-indigo-400 border border-indigo-500/20";
      
      return `
        <div class="bg-slate-950/60 rounded-xl p-3 border border-white/5 space-y-1.5">
          <div class="flex items-center gap-2">
            <span class="text-[9px] font-bold px-1.5 py-0.5 rounded uppercase ${badgeColor}">${bug.severity}</span>
            <span class="text-xs font-semibold text-white">Line ${bug.line_number}</span>
          </div>
          <p class="text-xs text-slate-300 leading-relaxed">${escapeHtml(bug.description)}</p>
          <div class="text-[10px] text-indigo-400 bg-indigo-400/5 px-2.5 py-1 rounded border border-indigo-400/10">
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
      alert(`Complexity analysis failed: ${errData.detail}`);
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
      alert(`Debugging diagnosis failed: ${errData.detail}`);
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
        <div class="bg-slate-950/80 rounded-xl p-4 border border-white/5 space-y-3 glass-panel">
          <div class="text-xs font-semibold text-white flex items-center gap-1.5">
            <i class="fa-solid fa-graduation-cap text-indigo-400"></i>
            <span>${escapeHtml(res.topic)}</span>
          </div>
          <div class="flex items-center gap-2">
            <a href="${res.youtube}" target="_blank" class="flex-1 text-center bg-rose-600/10 hover:bg-rose-600/20 text-rose-400 border border-rose-500/20 text-[10px] font-semibold py-2 rounded-lg transition-all flex items-center justify-center gap-1.5">
              <i class="fa-brands fa-youtube"></i>
              YouTube Tutorials
            </a>
            <a href="${res.geeksforgeeks}" target="_blank" class="flex-1 text-center bg-emerald-600/10 hover:bg-emerald-600/20 text-emerald-400 border border-emerald-500/20 text-[10px] font-semibold py-2 rounded-lg transition-all flex items-center justify-center gap-1.5">
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
      alert(`Screen vision check failed: ${errData.detail}`);
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
