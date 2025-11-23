let currentLogFile = "";
let liveEntries = [];
let totalEntries = 0;
let eventSource = null;
let streamState = "idle";

const maxLiveEntries = 400;
const snapshotLimit = 200;

document.addEventListener("DOMContentLoaded", () => {
    setActiveNav("logs");
    bindControls();
    loadLogFiles();
});

function bindControls() {
    document.getElementById("logLevel")?.addEventListener("change", applyFilters);
    document.getElementById("searchInput")?.addEventListener("keypress", (event) => {
        if (event.key === "Enter") {
            applyFilters();
        }
    });
    document.getElementById("streamToggle")?.addEventListener("click", toggleStream);
    document.getElementById("reconnectStream")?.addEventListener("click", () => startStream(true));
    document.getElementById("clearLogsBtn")?.addEventListener("click", clearLogs);
    document.getElementById("downloadLogsBtn")?.addEventListener("click", downloadLogs);
    document.getElementById("logFile")?.addEventListener("change", () => startStream(true));
}

async function loadLogFiles() {
    const select = document.getElementById("logFile");
    if (!select) {
        return;
    }

    select.innerHTML = '<option value="">加载中...</option>';

    try {
        const files = await apiCall("/api/public/logs/files");
        if (!Array.isArray(files) || files.length === 0) {
            select.innerHTML = '<option value="">暂无日志文件</option>';
            renderEmptyState("logContainer", "暂无可用日志文件");
            updateStreamStatus("idle", "等待文件");
            return;
        }

        select.innerHTML = "";
        files.forEach((file) => {
            const option = document.createElement("option");
            option.value = file.name;
            const modified = file.modified_time ? ` · ${formatTime(file.modified_time)}` : "";
            option.textContent = `${file.name} (${formatFileSize(file.size)})${modified}`;
            select.appendChild(option);
        });

        if (!currentLogFile || !files.some((f) => f.name === currentLogFile)) {
            currentLogFile = files[0].name;
        }
        select.value = currentLogFile;

        startStream(true);
    } catch (error) {
        select.innerHTML = '<option value="">加载失败</option>';
        renderError("logContainer", `加载日志文件列表失败: ${error.message}`);
        updateStreamStatus("error", "加载失败");
        showNotification("加载日志文件列表失败", "danger");
    }
}

function applyFilters() {
    startStream(true);
}

function toggleStream() {
    if (streamState === "live" || streamState === "connecting") {
        stopStream(false);
        updateStreamStatus("paused", "已暂停");
    } else {
        startStream(false);
    }
}

function startStream(resetBuffer = true) {
    if (!currentLogFile) {
        return;
    }

    stopStream(false);
    updateStreamStatus("connecting", "正在连接...");

    if (resetBuffer) {
        liveEntries = [];
        totalEntries = 0;
        renderLiveEntries();
        updateStatistics();
    }

    const params = new URLSearchParams({
        file: currentLogFile,
        poll_interval: 1,
        initial_limit: snapshotLimit,
    });
    const level = getSelectedLevel();
    const searchTerm = getSearchTerm();
    if (level) {
        params.append("level", level);
    }
    if (searchTerm) {
        params.append("search", searchTerm);
    }

    eventSource = new EventSource(`/api/public/logs/stream?${params.toString()}`);

    eventSource.addEventListener("snapshot", (event) => {
        const payload = safeParse(event.data) || {};
        liveEntries = Array.isArray(payload.entries) ? payload.entries : [];
        totalEntries = payload.total ?? liveEntries.length;
        renderLiveEntries(true);
        updateStatistics();
        updateStreamStatus("live", "实时跟随");
    });

    eventSource.onmessage = (event) => {
        const entry = safeParse(event.data);
        if (!entry) {
            return;
        }
        appendEntry(entry);
    };

    eventSource.onerror = () => {
        updateStreamStatus("error", "连接断开");
        stopStream(false);
        showNotification("实时连接已断开，请点击重连。", "warning");
    };
}

function stopStream(clearState = true) {
    if (eventSource) {
        eventSource.close();
        eventSource = null;
    }
    if (clearState) {
        updateStreamStatus("idle", "等待连接");
    }
}

function appendEntry(entry) {
    liveEntries.push(entry);
    totalEntries += 1;

    if (liveEntries.length > maxLiveEntries) {
        liveEntries.shift();
    }

    renderLiveEntries();
    updateStatistics();
}

function renderLiveEntries(forceScroll = false) {
    const container = document.getElementById("logContainer");
    if (!container) {
        return;
    }

    if (!liveEntries.length) {
        renderEmptyState("logContainer", "等待实时日志...");
        return;
    }

    container.innerHTML = liveEntries
        .map((log) => {
            const message = escapeHtml(log.message || "");
            return `
                <div class="log-line log-level-${log.level || "INFO"}" onclick="showLogDetail('${log.timestamp}', '${log.level}', '${message.replace(/'/g, "\\'")}')">
                    <span class="log-time">[${formatTime(log.timestamp)}]</span>
                    <span class="log-level badge bg-${getLevelColor(log.level)}">${log.level}</span>
                    <span class="log-message">${message}</span>
                </div>
            `;
        })
        .join("");

    const shouldScroll = forceScroll || document.getElementById("autoScroll")?.checked;
    if (shouldScroll) {
        scrollToBottom();
    }
}

function updateStatistics() {
    const stats = {
        total: totalEntries || liveEntries.length,
        debug: 0,
        info: 0,
        warning: 0,
        error: 0,
        critical: 0,
    };

    liveEntries.forEach((log) => {
        const level = (log.level || "").toLowerCase();
        if (stats[level] !== undefined) {
            stats[level] += 1;
        }
    });

    document.getElementById("totalLogs").textContent = stats.total;
    document.getElementById("debugLogs").textContent = stats.debug;
    document.getElementById("infoLogs").textContent = stats.info;
    document.getElementById("warningLogs").textContent = stats.warning;
    document.getElementById("errorLogs").textContent = stats.error;
    document.getElementById("criticalLogs").textContent = stats.critical;
}

function clearLogs() {
    confirmAction("确定要清空当前实时窗口吗？", () => {
        liveEntries = [];
        totalEntries = 0;
        renderLiveEntries();
        updateStatistics();
    });
}

async function downloadLogs() {
    if (!currentLogFile) {
        showNotification("请先选择要下载的日志文件", "warning");
        return;
    }

    try {
        window.open(`/api/public/logs/download?file=${encodeURIComponent(currentLogFile)}`, "_blank");
        showNotification("日志下载已开始", "success");
    } catch (error) {
        showNotification(`下载失败: ${error.message}`, "danger");
    }
}

function updateStreamStatus(state, label) {
    streamState = state;

    const statusText = document.getElementById("liveStatusText");
    const statusDot = document.getElementById("liveStatusDot");
    const toggle = document.getElementById("streamToggle");

    const config = {
        idle: { text: label || "等待连接", dot: "idle", btnText: "开启实时" },
        connecting: { text: label || "正在连接...", dot: "connecting", btnText: "暂停实时" },
        live: { text: label || "实时跟随", dot: "live", btnText: "暂停实时" },
        paused: { text: label || "已暂停", dot: "paused", btnText: "恢复实时" },
        error: { text: label || "连接异常", dot: "error", btnText: "重试连接" },
    };

    const stateConfig = config[state] || config.idle;

    if (statusText) {
        statusText.textContent = stateConfig.text;
    }

    if (statusDot) {
        statusDot.className = `status-dot ${stateConfig.dot}`;
    }

    if (toggle) {
        toggle.textContent = stateConfig.btnText;
        toggle.classList.toggle("btn-danger", state === "error");
        toggle.classList.toggle("btn-primary", state !== "error");
    }
}

function renderEmptyState(containerId, message) {
    const container = document.getElementById(containerId);
    if (!container) {
        return;
    }
    container.innerHTML = `
        <div class="empty-state">
            <i class="bi bi-broadcast-pin fs-3 text-muted me-2"></i>
            <span class="text-muted">${message}</span>
        </div>
    `;
}

function renderError(containerId, message) {
    const container = document.getElementById(containerId);
    if (!container) {
        return;
    }
    container.innerHTML = `
        <div class="alert alert-danger m-3">
            <i class="bi bi-exclamation-triangle me-2"></i>
            ${message}
        </div>
    `;
}

function showLogDetail(timestamp, level, message) {
    const modalElement = document.getElementById("logDetailModal");
    const content = document.getElementById("logDetailContent");
    if (!modalElement || !content) {
        return;
    }

    content.innerHTML = `
        <div class="row">
            <div class="col-md-3"><strong>时间:</strong></div>
            <div class="col-md-9">${formatTime(timestamp)}</div>
        </div>
        <div class="row mt-2">
            <div class="col-md-3"><strong>级别:</strong></div>
            <div class="col-md-9">
                <span class="badge bg-${getLevelColor(level)}">${level}</span>
            </div>
        </div>
        <div class="row mt-2">
            <div class="col-md-3"><strong>消息:</strong></div>
            <div class="col-md-9">
                <pre class="bg-light p-2 rounded">${escapeHtml(message)}</pre>
            </div>
        </div>
    `;

    new bootstrap.Modal(modalElement).show();
}

function scrollToBottom() {
    const container = document.getElementById("logContainer");
    if (container) {
        container.scrollTop = container.scrollHeight;
    }
}

function getLevelColor(level) {
    const colors = {
        DEBUG: "secondary",
        INFO: "info",
        WARNING: "warning",
        ERROR: "danger",
        CRITICAL: "danger",
    };
    return colors[level] || "secondary";
}

function escapeHtml(text) {
    if (text === undefined || text === null) {
        return "";
    }
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

function getSelectedLevel() {
    const select = document.getElementById("logLevel");
    if (!select) {
        return null;
    }
    const value = (select.value || "").trim();
    if (!value || value.toLowerCase() === "all") {
        return null;
    }
    return value.toUpperCase();
}

function getSearchTerm() {
    const input = document.getElementById("searchInput");
    return (input?.value || "").trim();
}

function safeParse(text) {
    try {
        return JSON.parse(text);
    } catch (err) {
        return null;
    }
}

window.addEventListener("beforeunload", () => {
    stopStream();
});
