let currentLogFile = "";
let currentEntries = [];
let totalEntries = 0;
let currentPage = 1;
const logsPerPage = 100;
let eventSource = null;

document.addEventListener("DOMContentLoaded", () => {
    setActiveNav("logs");
    collapseFiltersOnMobile();
    bindSearchShortcut();
    loadLogFiles();
});

function collapseFiltersOnMobile() {
    const filterContent = document.getElementById("logFilterContent");
    if (!filterContent) {
        return;
    }

    if (window.innerWidth <= 768 && filterContent.classList.contains("show")) {
        const collapse = new bootstrap.Collapse(filterContent, { toggle: false });
        collapse.hide();
    }
}

function bindSearchShortcut() {
    const searchInput = document.getElementById("searchInput");
    if (!searchInput) {
        return;
    }
    searchInput.addEventListener("keypress", (event) => {
        if (event.key === "Enter") {
            filterLogs();
        }
    });
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
            return;
        }

        select.innerHTML = "";
        files.forEach((file) => {
            const option = document.createElement("option");
            option.value = file.name;
            option.textContent = `${file.name} (${formatFileSize(file.size)})`;
            select.appendChild(option);
        });

        if (!currentLogFile || !files.some((f) => f.name === currentLogFile)) {
            currentLogFile = files[0].name;
        }
        select.value = currentLogFile;

        await loadLogPage(true);
    } catch (error) {
        select.innerHTML = '<option value="">加载失败</option>';
        renderError("logContainer", `加载日志文件列表失败: ${error.message}`);
        showNotification("加载日志文件列表失败", "danger");
    }
}

async function loadLogPage(resetPage = false) {
    if (!currentLogFile) {
        return;
    }

    if (resetPage) {
        currentPage = 1;
    }

    const level = getSelectedLevel();
    const searchTerm = getSearchTerm();
    const offset = (currentPage - 1) * logsPerPage;

    const params = new URLSearchParams({
        file: currentLogFile,
        limit: logsPerPage,
        offset,
    });
    if (level) {
        params.append("level", level);
    }
    if (searchTerm) {
        params.append("search", searchTerm);
    }

    try {
        const data = await apiCall(`/api/public/logs/content?${params.toString()}`);
        currentEntries = data.entries || [];
        totalEntries = data.total || 0;

        renderLogEntries();
        updateStatistics();
        updatePagination();
    } catch (error) {
        renderError("logContainer", `加载日志失败: ${error.message}`);
        showNotification(`加载日志失败: ${error.message}`, "danger");
    }
}

function renderLogEntries() {
    const container = document.getElementById("logContainer");
    if (!container) {
        return;
    }

    if (!currentEntries.length) {
        renderEmptyState("logContainer", "暂无日志内容");
        updatePagination();
        updateStatistics();
        return;
    }

    container.innerHTML = currentEntries
        .map((log) => {
            const message = escapeHtml(log.message || "");
            return `
                <div class="log-entry log-level-${log.level}" onclick="showLogDetail('${log.timestamp}', '${log.level}', '${message.replace(/'/g, "\\'")}')">
                    <div class="d-flex justify-content-between">
                        <span class="text-muted">[${formatTime(log.timestamp)}]</span>
                        <span class="badge bg-${getLevelColor(log.level)}">${log.level}</span>
                    </div>
                    <div class="mt-1">${message}</div>
                </div>
            `;
        })
        .join("");

    if (document.getElementById("autoScroll")?.checked) {
        setTimeout(() => scrollToBottom(), 100);
    }
}

function updateStatistics() {
    const stats = {
        total: totalEntries,
        debug: 0,
        info: 0,
        warning: 0,
        error: 0,
        critical: 0,
    };

    currentEntries.forEach((log) => {
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

function updatePagination() {
    const pagination = document.getElementById("pagination");
    if (!pagination) {
        return;
    }

    const totalPages = totalEntries > 0 ? Math.ceil(totalEntries / logsPerPage) : 1;
    const safePage = Math.min(Math.max(currentPage, 1), totalPages);
    if (safePage !== currentPage) {
        currentPage = safePage;
    }

    const start = totalEntries === 0 ? 0 : (currentPage - 1) * logsPerPage + 1;
    const end = Math.min(currentPage * logsPerPage, totalEntries);

    document.getElementById("showingFrom").textContent = start;
    document.getElementById("showingTo").textContent = end;
    document.getElementById("totalCount").textContent = totalEntries;

    let paginationHTML = "";
    paginationHTML += `
        <li class="page-item ${currentPage === 1 ? "disabled" : ""}">
            <a class="page-link" href="#" onclick="changePage(${currentPage - 1}); return false;">上一页</a>
        </li>
    `;

    const pagesToShow = Math.min(totalPages, 10);
    for (let i = 1; i <= pagesToShow; i += 1) {
        paginationHTML += `
            <li class="page-item ${i === currentPage ? "active" : ""}">
                <a class="page-link" href="#" onclick="changePage(${i}); return false;">${i}</a>
            </li>
        `;
    }

    paginationHTML += `
        <li class="page-item ${currentPage === totalPages || totalPages === 0 ? "disabled" : ""}">
            <a class="page-link" href="#" onclick="changePage(${currentPage + 1}); return false;">下一页</a>
        </li>
    `;

    pagination.innerHTML = paginationHTML;
}

function changePage(page) {
    const totalPages = totalEntries > 0 ? Math.ceil(totalEntries / logsPerPage) : 1;
    if (page < 1 || page > totalPages) {
        return;
    }
    currentPage = page;
    loadLogPage(false);
}

function filterLogs() {
    currentPage = 1;
    loadLogPage(true);
}

function searchLogs() {
    filterLogs();
}

function clearLogs() {
    confirmAction("确定要清空当前显示的日志吗？", () => {
        currentEntries = [];
        totalEntries = 0;
        renderLogEntries();
        updateStatistics();
        updatePagination();
        showNotification("日志已清空", "success");
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

function refreshLogs() {
    loadLogPage(true);
    showNotification("日志已刷新", "info");
}

function toggleRealtime() {
    const enabled = document.getElementById("realtimeMode")?.checked;
    if (enabled) {
        startRealtimeMode();
    } else {
        stopRealtimeMode();
    }
}

function startRealtimeMode() {
    if (!currentLogFile) {
        showNotification("请先选择日志文件", "warning");
        document.getElementById("realtimeMode").checked = false;
        return;
    }

    stopRealtimeMode();

    try {
        eventSource = new EventSource(`/api/public/logs/stream?file=${encodeURIComponent(currentLogFile)}`);
        eventSource.onmessage = (event) => {
            const newLog = JSON.parse(event.data);
            currentEntries.push(newLog);
            totalEntries += 1;

            if (currentEntries.length > logsPerPage) {
                currentEntries.shift();
            }

            renderLogEntries();
            updateStatistics();
            updatePagination();
        };

        eventSource.onerror = () => {
            showNotification("实时连接断开", "warning");
            stopRealtimeMode();
        };

        showNotification("实时监控已开启", "success");
    } catch (error) {
        showNotification(`开启实时监控失败: ${error.message}`, "danger");
        document.getElementById("realtimeMode").checked = false;
    }
}

function stopRealtimeMode() {
    if (eventSource) {
        eventSource.close();
        eventSource = null;
    }
}

function renderEmptyState(containerId, message) {
    const container = document.getElementById(containerId);
    if (!container) {
        return;
    }
    container.innerHTML = `
        <div class="text-center p-4">
            <i class="bi bi-inbox fs-1 text-muted"></i>
            <p class="text-muted mt-2 mb-0">${message}</p>
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

function scrollToTop() {
    const container = document.getElementById("logContainer");
    if (container) {
        container.scrollTop = 0;
    }
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

window.addEventListener("beforeunload", () => {
    stopRealtimeMode();
});
