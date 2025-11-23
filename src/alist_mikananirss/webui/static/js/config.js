let currentConfig = {};
let configSchema = {};
let importModal;

const LEVEL_BADGE = {
    ok: 'bg-success',
    connected: 'bg-success',
    warning: 'bg-warning text-dark',
    error: 'bg-danger'
};

document.addEventListener('DOMContentLoaded', () => {
    setActiveNav('config');
    importModal = new bootstrap.Modal(document.getElementById('importModal'));
    bindEvents();
    loadConfig();
});

function bindEvents() {
    const actionBar = document.getElementById('configActionBar');
    if (actionBar) {
        actionBar.addEventListener('click', (event) => {
            const actionBtn = event.target.closest('.config-action');
            if (!actionBtn) return;
            const action = actionBtn.dataset.action;
            switch (action) {
                case 'reload':
                    loadConfig();
                    break;
                case 'export':
                    exportConfig();
                    break;
                case 'import':
                    openImportModal();
                    break;
                default:
                    break;
            }
        });
    }

    const testBtn = document.getElementById('btnTestConfig');
    if (testBtn) testBtn.addEventListener('click', testConfig);

    const resetBtn = document.getElementById('btnResetConfig');
    if (resetBtn) resetBtn.addEventListener('click', resetConfigToDefault);

    const saveBtn = document.getElementById('btnSaveConfig');
    if (saveBtn) saveBtn.addEventListener('click', saveConfig);

    const doImportBtn = document.getElementById('btnDoImport');
    if (doImportBtn) doImportBtn.addEventListener('click', doImportConfig);

    const mikanForm = document.getElementById('mikanForm');
    if (mikanForm) {
        mikanForm.addEventListener('click', (event) => {
            const actionBtn = event.target.closest('[data-action]');
            if (!actionBtn) return;
            switch (actionBtn.dataset.action) {
                case 'add-subscribe':
                    addSubscribeUrl();
                    break;
                case 'add-regex':
                    addRegexPattern();
                    break;
                case 'add-filter':
                    addFilter();
                    break;
                case 'remove-subscribe':
                    removeSubscribeUrl(actionBtn);
                    break;
                case 'remove-regex':
                    removeRegexPattern(actionBtn);
                    break;
                case 'remove-filter':
                    removeFilter(actionBtn);
                    break;
                default:
                    break;
            }
        });
    }

    const renameEnable = document.getElementById('rename_enable');
    if (renameEnable) renameEnable.addEventListener('change', toggleRenameConfig);

    const renameType = document.getElementById('rename_extractor_type');
    if (renameType) renameType.addEventListener('change', toggleRenameProviderFields);

    const renameRemapEnable = document.getElementById('rename_remap_enable');
    if (renameRemapEnable) renameRemapEnable.addEventListener('change', toggleRemapPath);

    const notificationEnable = document.getElementById('notification_enable');
    if (notificationEnable) notificationEnable.addEventListener('change', toggleNotificationConfig);

    const addBotBtn = document.getElementById('addNotificationBot');
    if (addBotBtn) addBotBtn.addEventListener('click', () => addNotificationBot());

    const botContainer = document.getElementById('notificationBots');
    if (botContainer) {
        botContainer.addEventListener('click', (event) => {
            const actionBtn = event.target.closest('[data-action]');
            if (!actionBtn) return;
            if (actionBtn.dataset.action === 'remove-bot') {
                actionBtn.closest('.notification-bot')?.remove();
            }
        });
        botContainer.addEventListener('change', (event) => {
            const row = event.target.closest('.notification-bot');
            if (!row) return;
            if (event.target.classList.contains('bot-type')) {
                updateBotFields(row);
            }
        });
    }
}

async function loadConfig(showToast = true) {
    try {
        resetTestPanel();
        const [config, schema] = await Promise.all([
            apiCall('/api/admin/config/current'),
            apiCall('/api/admin/config/schema')
        ]);
        currentConfig = config || {};
        configSchema = schema || {};
        populateForms();
        toggleSetupNotice();
        if (showToast) showNotification('配置加载成功', 'success');
    } catch (error) {
        console.error('加载配置失败', error);
        showNotification('加载配置失败: ' + error.message, 'danger');
    }
}

function populateForms() {
    fillCommonSection();
    fillAlistSection();
    fillMikanSection();
    fillRenameSection();
    fillNotificationSection();
    fillWebdavSection();
}

function fillCommonSection() {
    const common = currentConfig.common || {};
    const schemaCommon = configSchema.common || {};

    setInputValue('interval_time', common.interval_time ?? schemaCommon.interval_time?.value ?? 300);
    setSelectValue('log_level', (common.log_level || 'INFO').toUpperCase());

    const proxies = common.proxies || {};
    setInputValue('proxy_http', proxies.http || proxies.http_proxy || '');
    setInputValue('proxy_https', proxies.https || proxies.https_proxy || '');
}

function fillAlistSection() {
    const alist = currentConfig.alist || {};
    setInputValue('alist_base_url', alist.base_url || '');
    setInputValue('alist_token', alist.token || '');
    setSelectValue('alist_downloader', alist.downloader || 'qBittorrent');
    setInputValue('alist_download_path', alist.download_path || '/downloads');
    setCheckboxValue('alist_convert_torrent', Boolean(alist.convert_torrent_to_magnet));
}

function fillMikanSection() {
    const mikan = currentConfig.mikan || {};

    renderSubscribeUrls(mikan.subscribe_url);
    renderRegexPatterns(mikan.regex_pattern);
    renderFilters(mikan.filters);
}

function fillRenameSection() {
    const rename = currentConfig.rename || {};
    setCheckboxValue('rename_enable', Boolean(rename.enable));
    setInputValue('rename_format', rename.rename_format || '{name} S{season:02d}E{episode:02d}');

    const extractor = rename.extractor || {};
    setSelectValue('rename_extractor_type', extractor.extractor_type || '');
    setInputValue('rename_model', extractor.model || '');
    setInputValue('rename_api_key', extractor.api_key || '');
    setInputValue('rename_base_url', extractor.base_url || '');
    setSelectValue('rename_output_type', extractor.output_type || 'json_object');

    const remap = rename.remap || {};
    setCheckboxValue('rename_remap_enable', Boolean(remap.enable));
    setInputValue('rename_remap_path', remap.cfg_path || './remap.yaml');

    toggleRenameConfig();
    toggleRenameProviderFields();
    toggleRemapPath();
}

function fillNotificationSection() {
    const notification = currentConfig.notification || {};
    setCheckboxValue('notification_enable', Boolean(notification.enable));
    setInputValue('notification_interval', notification.interval_time ?? 300);

    renderNotificationBots(notification.bots);
    toggleNotificationConfig();
}

function fillWebdavSection() {
    const webdav = currentConfig.webdav || {};
    setInputValue('webdav_username', webdav.username || 'admin');
    setInputValue('webdav_password', webdav.password || '');
    setInputValue('webdav_timeout', webdav.timeout ?? 60);

    const fixer = webdav.fixer || {};
    setCheckboxValue('webdav_fixer_enable', Boolean(fixer.enable));
    setCheckboxValue('webdav_execute_mode', Boolean(fixer.execute_mode));
    setCheckboxValue('webdav_recursive_scan', fixer.recursive_scan !== false);
    setSelectValue('webdav_conflict_strategy', fixer.conflict_strategy || 'skip');

    const manual = webdav.manual || {};
    setCheckboxValue('webdav_manual_enable', manual.enable !== false);
    setInputValue('webdav_manual_path', manual.default_path || '');
    setCheckboxValue('webdav_manual_execute', Boolean(manual.execute_mode));
    setCheckboxValue('webdav_manual_recursive', manual.recursive_scan !== false);
    setSelectValue('webdav_manual_strategy', manual.conflict_strategy || 'skip');
}

function renderSubscribeUrls(urls) {
    const container = document.getElementById('subscribeUrls');
    if (!container) return;
    container.innerHTML = '';
    const list = Array.isArray(urls) && urls.length > 0 ? urls : [''];
    list.forEach((value) => container.appendChild(createSubscribeRow(value)));
}

function createSubscribeRow(value = '') {
    const div = document.createElement('div');
    div.className = 'input-group';

    const input = document.createElement('input');
    input.type = 'url';
    input.className = 'form-control';
    input.name = 'subscribe_url';
    input.placeholder = 'https://mikanani.me/RSS/MyBangumi?token=xxx';
    input.value = value || '';

    const removeBtn = document.createElement('button');
    removeBtn.type = 'button';
    removeBtn.className = 'btn btn-outline-danger';
    removeBtn.dataset.action = 'remove-subscribe';
    removeBtn.innerHTML = '<i class="bi bi-trash"></i>';

    div.appendChild(input);
    div.appendChild(removeBtn);
    return div;
}

function addSubscribeUrl(value = '') {
    const container = document.getElementById('subscribeUrls');
    if (!container) return;
    container.appendChild(createSubscribeRow(value));
}

function removeSubscribeUrl(button) {
    const row = button.closest('.input-group');
    if (!row) return;
    const container = row.parentElement;
    row.remove();
    if (container && container.children.length === 0) {
        addSubscribeUrl();
    }
}

function renderRegexPatterns(patterns) {
    const container = document.getElementById('regexPatterns');
    if (!container) return;
    container.innerHTML = '';
    const entries = patterns && typeof patterns === 'object' && Object.keys(patterns).length > 0
        ? Object.entries(patterns)
        : [['', '']];
    entries.forEach(([name, value]) => container.appendChild(createRegexRow(name, value)));
}

function createRegexRow(name = '', value = '') {
    const wrapper = document.createElement('div');
    wrapper.className = 'regex-pattern-item row g-2 align-items-center';

    const nameCol = document.createElement('div');
    nameCol.className = 'col-md-4';
    const nameInput = document.createElement('input');
    nameInput.type = 'text';
    nameInput.className = 'form-control';
    nameInput.name = 'regex_name';
    nameInput.placeholder = '规则名称';
    nameInput.value = name || '';
    nameCol.appendChild(nameInput);

    const valueCol = document.createElement('div');
    valueCol.className = 'col-md-6';
    const valueInput = document.createElement('input');
    valueInput.type = 'text';
    valueInput.className = 'form-control';
    valueInput.name = 'regex_value';
    valueInput.placeholder = '正则表达式';
    valueInput.value = value || '';
    valueCol.appendChild(valueInput);

    const actionsCol = document.createElement('div');
    actionsCol.className = 'col-md-2 d-flex gap-2 justify-content-end';
    const removeBtn = document.createElement('button');
    removeBtn.type = 'button';
    removeBtn.className = 'btn btn-outline-danger';
    removeBtn.dataset.action = 'remove-regex';
    removeBtn.innerHTML = '<i class="bi bi-trash"></i>';
    actionsCol.appendChild(removeBtn);

    wrapper.appendChild(nameCol);
    wrapper.appendChild(valueCol);
    wrapper.appendChild(actionsCol);
    return wrapper;
}

function addRegexPattern(name = '', value = '') {
    const container = document.getElementById('regexPatterns');
    if (!container) return;
    container.appendChild(createRegexRow(name, value));
}

function removeRegexPattern(button) {
    const row = button.closest('.regex-pattern-item');
    if (!row) return;
    const container = row.parentElement;
    row.remove();
    if (container && container.children.length === 0) {
        addRegexPattern();
    }
}

function renderFilters(filters) {
    const container = document.getElementById('filters');
    if (!container) return;
    container.innerHTML = '';
    const list = Array.isArray(filters) && filters.length > 0 ? filters : [''];
    list.forEach((value) => container.appendChild(createFilterRow(value)));
}

function createFilterRow(value = '') {
    const div = document.createElement('div');
    div.className = 'input-group';

    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'form-control';
    input.name = 'filter';
    input.placeholder = '例如: 非合集, 1080p';
    input.value = value || '';

    const removeBtn = document.createElement('button');
    removeBtn.type = 'button';
    removeBtn.className = 'btn btn-outline-danger';
    removeBtn.dataset.action = 'remove-filter';
    removeBtn.innerHTML = '<i class="bi bi-trash"></i>';

    div.appendChild(input);
    div.appendChild(removeBtn);
    return div;
}

function addFilter(value = '') {
    const container = document.getElementById('filters');
    if (!container) return;
    container.appendChild(createFilterRow(value));
}

function removeFilter(button) {
    const row = button.closest('.input-group');
    if (!row) return;
    const container = row.parentElement;
    row.remove();
    if (container && container.children.length === 0) {
        addFilter();
    }
}

function toggleRenameConfig() {
    const enable = document.getElementById('rename_enable')?.checked;
    const config = document.getElementById('renameConfig');
    if (config) {
        config.style.display = enable ? 'flex' : 'none';
        config.style.flexDirection = 'column';
    }
}

function toggleRenameProviderFields() {
    const provider = document.getElementById('rename_extractor_type')?.value || '';
    const baseUrlGroup = document.getElementById('rename_base_url_group');
    if (baseUrlGroup) {
        baseUrlGroup.style.display = provider && provider !== 'google' ? 'block' : 'none';
    }
}

function toggleRemapPath() {
    const enabled = document.getElementById('rename_remap_enable')?.checked;
    const pathInput = document.getElementById('rename_remap_path');
    if (pathInput) {
        pathInput.disabled = !enabled;
    }
}

function toggleNotificationConfig() {
    const enabled = document.getElementById('notification_enable')?.checked;
    const container = document.getElementById('notificationBots');
    const addBtn = document.getElementById('addNotificationBot');
    if (container) container.classList.toggle('opacity-50', !enabled);
    if (addBtn) addBtn.disabled = !enabled;
}

function renderNotificationBots(bots) {
    const container = document.getElementById('notificationBots');
    if (!container) return;
    container.innerHTML = '';
    const list = Array.isArray(bots) && bots.length > 0 ? bots : [{}];
    list.forEach((bot) => container.appendChild(createBotRow(bot)));
}

function createBotRow(bot = {}) {
    const wrapper = document.createElement('div');
    wrapper.className = 'notification-bot card card-body p-3';

    const row = document.createElement('div');
    row.className = 'row g-3 align-items-center';

    const typeCol = document.createElement('div');
    typeCol.className = 'col-md-3';
    const typeLabel = document.createElement('label');
    typeLabel.className = 'form-label';
    typeLabel.textContent = '类型';
    const typeSelect = document.createElement('select');
    typeSelect.className = 'form-select bot-type';
    ['','telegram','pushplus'].forEach((option) => {
        const opt = document.createElement('option');
        opt.value = option;
        opt.textContent = option ? option : '选择类型';
        typeSelect.appendChild(opt);
    });
    typeSelect.value = bot.bot_type || '';
    typeCol.appendChild(typeLabel);
    typeCol.appendChild(typeSelect);

    const tokenCol = document.createElement('div');
    tokenCol.className = 'col-md-3';
    const tokenLabel = document.createElement('label');
    tokenLabel.className = 'form-label';
    tokenLabel.textContent = 'Token';
    const tokenInput = document.createElement('input');
    tokenInput.type = 'password';
    tokenInput.className = 'form-control bot-token';
    tokenInput.value = bot.token || '';
    tokenCol.appendChild(tokenLabel);
    tokenCol.appendChild(tokenInput);

    const detailCol = document.createElement('div');
    detailCol.className = 'col-md-4';
    detailCol.dataset.role = 'bot-detail';

    const removeCol = document.createElement('div');
    removeCol.className = 'col-md-2 d-flex justify-content-end';
    const removeBtn = document.createElement('button');
    removeBtn.type = 'button';
    removeBtn.className = 'btn btn-outline-danger';
    removeBtn.dataset.action = 'remove-bot';
    removeBtn.innerHTML = '<i class="bi bi-trash"></i>';
    removeCol.appendChild(removeBtn);

    row.appendChild(typeCol);
    row.appendChild(tokenCol);
    row.appendChild(detailCol);
    row.appendChild(removeCol);
    wrapper.appendChild(row);

    updateBotFields(wrapper, bot);
    return wrapper;
}

function updateBotFields(row, bot = {}) {
    const type = row.querySelector('.bot-type')?.value || bot.bot_type || '';
    const detailCol = row.querySelector('[data-role="bot-detail"]');
    if (!detailCol) return;
    detailCol.innerHTML = '';

    if (type === 'telegram') {
        const label = document.createElement('label');
        label.className = 'form-label';
        label.textContent = 'User ID';
        const input = document.createElement('input');
        input.type = 'text';
        input.className = 'form-control bot-user-id';
        input.value = bot.user_id || bot.chat_id || '';
        detailCol.appendChild(label);
        detailCol.appendChild(input);
    } else if (type === 'pushplus') {
        const label = document.createElement('label');
        label.className = 'form-label';
        label.textContent = 'Channel';
        const select = document.createElement('select');
        select.className = 'form-select bot-channel';
        [
            { value: 'wechat', label: '微信' },
            { value: 'webhook', label: 'Webhook' },
            { value: 'cp', label: '企业微信/钉钉' },
            { value: 'mail', label: '邮件' }
        ].forEach(({ value, label: text }) => {
            const opt = document.createElement('option');
            opt.value = value;
            opt.textContent = text;
            select.appendChild(opt);
        });
        select.value = bot.channel || 'wechat';
        detailCol.appendChild(label);
        detailCol.appendChild(select);
    } else {
        const muted = document.createElement('div');
        muted.className = 'text-muted small';
        muted.textContent = '选择类型后填写对应字段';
        detailCol.appendChild(muted);
    }
}

function addNotificationBot() {
    const container = document.getElementById('notificationBots');
    if (!container) return;
    container.appendChild(createBotRow());
}

function toggleSetupNotice() {
    const notice = document.getElementById('configSetupNotice');
    if (!notice) return;
    const needsSetup = currentConfig?._meta?.needs_setup;
    notice.classList.toggle('d-none', !needsSetup);
}

function collectFormData() {
    const config = {};

    config.common = {
        interval_time: parseNumberValue('interval_time', 300),
        log_level: (getInputValue('log_level') || 'INFO').toUpperCase(),
        proxies: {},
    };
    const httpProxy = getInputValue('proxy_http');
    const httpsProxy = getInputValue('proxy_https');
    if (httpProxy) config.common.proxies.http = httpProxy;
    if (httpsProxy) config.common.proxies.https = httpsProxy;

    config.alist = {
        base_url: getInputValue('alist_base_url'),
        token: getInputValue('alist_token'),
        downloader: getInputValue('alist_downloader') || 'qBittorrent',
        download_path: getInputValue('alist_download_path') || '/downloads',
        convert_torrent_to_magnet: document.getElementById('alist_convert_torrent')?.checked || false,
    };

    config.mikan = collectMikanFormData();
    config.rename = collectRenameFormData();
    config.notification = collectNotificationFormData();
    config.webdav = collectWebdavFormData();

    // 保留后端已有的其他字段
    ['webui', 'bot_assistant', 'dev'].forEach((key) => {
        if (currentConfig[key] !== undefined) {
            config[key] = deepClone(currentConfig[key]);
        }
    });

    return config;
}

function collectMikanFormData() {
    const data = {};
    const urls = [];
    document.querySelectorAll('#subscribeUrls input[name="subscribe_url"]').forEach((input) => {
        const value = input.value.trim();
        if (value) urls.push(value);
    });
    data.subscribe_url = urls;

    const regex = {};
    document.querySelectorAll('#regexPatterns .regex-pattern-item').forEach((row) => {
        const name = row.querySelector('input[name="regex_name"]')?.value.trim();
        const value = row.querySelector('input[name="regex_value"]')?.value.trim();
        if (name && value) {
            regex[name] = value;
        }
    });
    data.regex_pattern = regex;

    const filters = [];
    document.querySelectorAll('#filters input[name="filter"]').forEach((input) => {
        const value = input.value.trim();
        if (value) filters.push(value);
    });
    data.filters = filters;
    return data;
}

function collectRenameFormData() {
    const enable = document.getElementById('rename_enable')?.checked || false;
    const remapEnable = document.getElementById('rename_remap_enable')?.checked || false;

    const extractorType = getInputValue('rename_extractor_type');
    let extractor = null;
    if (extractorType) {
        extractor = {
            extractor_type: extractorType,
            api_key: getInputValue('rename_api_key') || undefined,
            model: getInputValue('rename_model') || undefined,
            output_type: getInputValue('rename_output_type') || 'json_object',
        };
        if (extractorType !== 'google') {
            extractor.base_url = getInputValue('rename_base_url') || undefined;
        }
    }

    return {
        enable,
        rename_format: getInputValue('rename_format') || '{name} S{season:02d}E{episode:02d}',
        extractor,
        remap: {
            enable: remapEnable,
            cfg_path: getInputValue('rename_remap_path') || './remap.yaml',
        },
    };
}

function collectNotificationFormData() {
    const enabled = document.getElementById('notification_enable')?.checked || false;
    const interval = parseNumberValue('notification_interval', 300);
    const bots = [];

    document.querySelectorAll('#notificationBots .notification-bot').forEach((row) => {
        const botType = row.querySelector('.bot-type')?.value;
        const token = row.querySelector('.bot-token')?.value;
        if (!botType || !token) return;

        const bot = { bot_type: botType, token };
        if (botType === 'telegram') {
            bot.user_id = row.querySelector('.bot-user-id')?.value || '';
        } else if (botType === 'pushplus') {
            bot.channel = row.querySelector('.bot-channel')?.value || 'wechat';
        }
        bots.push(bot);
    });

    return { enable: enabled, interval_time: interval, bots };
}

function collectWebdavFormData() {
    const fixerEnable = document.getElementById('webdav_fixer_enable')?.checked || false;
    const manualEnable = document.getElementById('webdav_manual_enable')?.checked;
    return {
        username: getInputValue('webdav_username') || 'admin',
        password: getInputValue('webdav_password') || '',
        timeout: parseNumberValue('webdav_timeout', 60),
        fixer: {
            enable: fixerEnable,
            execute_mode: document.getElementById('webdav_execute_mode')?.checked || false,
            recursive_scan: document.getElementById('webdav_recursive_scan')?.checked !== false,
            conflict_strategy: getInputValue('webdav_conflict_strategy') || 'skip',
        },
        manual: {
            enable: manualEnable !== false,
            default_path: getInputValue('webdav_manual_path') || null,
            execute_mode: document.getElementById('webdav_manual_execute')?.checked || false,
            recursive_scan: document.getElementById('webdav_manual_recursive')?.checked !== false,
            conflict_strategy: getInputValue('webdav_manual_strategy') || 'skip',
        },
    };
}

async function saveConfig() {
    const payload = collectFormData();
    try {
        const response = await apiCall('/api/admin/config/save', {
            method: 'POST',
            body: JSON.stringify(payload)
        });
        if (!response.success) {
            renderValidationResults(response.errors || [], true);
            showNotification('配置保存失败', 'danger');
            return;
        }
        currentConfig = { ...payload, _meta: { needs_setup: false, source: 'file' } };
        toggleSetupNotice();
        showNotification('配置保存成功', 'success');
    } catch (error) {
        const errors = error.payload?.errors || error.payload?.field_errors;
        if (errors) {
            renderValidationResults(errors, true);
        }
        showNotification('配置保存失败: ' + error.message, 'danger');
    }
}

async function testConfig() {
    const payload = collectFormData();
    setTestStatus('running');
    try {
        const result = await apiCall('/api/admin/config/test', {
            method: 'POST',
            body: JSON.stringify(payload)
        });

        if (result.results?.validation) {
            renderValidationResults(result.results.validation, true);
        } else {
            renderValidationResults([], false);
        }

        renderTestResults(result.results, result.success);
        showNotification(result.success ? '配置测试通过' : '配置存在问题，请查看详情', result.success ? 'success' : 'warning');
    } catch (error) {
        setTestStatus('error');
        showNotification('测试配置失败: ' + error.message, 'danger');
        const validationErrors = error.payload?.detail?.errors || error.payload?.errors;
        if (validationErrors) {
            renderValidationResults(validationErrors, true);
        }
    }
}

function resetConfigToDefault() {
    const defaults = deriveDefaultsFromSchema();
    currentConfig = { ...currentConfig, ...defaults };
    populateForms();
    resetTestPanel();
    showNotification('已重置为默认值，请检查后保存', 'info');
}

function deriveDefaultsFromSchema() {
    const defaults = {};
    const schemaCommon = configSchema.common || {};
    defaults.common = {
        interval_time: schemaCommon.interval_time?.value ?? 300,
        log_level: (schemaCommon.log_level?.value || 'INFO').toUpperCase(),
        proxies: {}
    };

    const schemaAlist = configSchema.alist || {};
    defaults.alist = {
        base_url: schemaAlist.base_url?.value || 'http://127.0.0.1:5244',
        token: schemaAlist.token?.value || '',
        downloader: schemaAlist.downloader?.value || 'qBittorrent',
        download_path: schemaAlist.download_path?.value || '/downloads',
        convert_torrent_to_magnet: schemaAlist.convert_torrent_to_magnet?.value || false,
    };

    const schemaMikan = configSchema.mikan || {};
    defaults.mikan = {
        subscribe_url: schemaMikan.subscribe_url?.value || ['https://mikanani.me/RSS/'],
        filters: schemaMikan.filters?.value || [],
        regex_pattern: schemaMikan.regex_pattern?.value || {},
    };

    ['notification', 'rename', 'webdav', 'webui', 'bot_assistant', 'dev'].forEach((key) => {
        if (configSchema[key] !== undefined) {
            defaults[key] = deepClone(configSchema[key]);
        }
    });
    return defaults;
}

function exportConfig() {
    const config = collectFormData();
    const blob = new Blob([JSON.stringify(config, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `alist-mikananirss-config-${new Date().toISOString().split('T')[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
    showNotification('配置导出成功', 'success');
}

function openImportModal() {
    importModal?.show();
}

async function doImportConfig() {
    const fileInput = document.getElementById('importFile');
    const file = fileInput?.files?.[0];
    if (!file) {
        showNotification('请选择配置文件', 'warning');
        return;
    }

    try {
        const text = await file.text();
        const parsed = await parseConfigText(text);

        const validation = await apiCall('/api/admin/config/validate', {
            method: 'POST',
            body: JSON.stringify(parsed)
        });

        if (!validation.valid) {
            renderValidationResults(validation.errors || validation.field_errors || [], true);
            showNotification('导入的配置存在问题，请查看验证结果', 'warning');
            return;
        }

        currentConfig = parsed;
        populateForms();
        toggleSetupNotice();
        importModal?.hide();
        showNotification('配置导入成功，请检查并保存', 'success');
    } catch (error) {
        console.error('导入配置失败', error);
        renderValidationResults(error.payload?.errors || error.payload?.detail?.errors || [], true);
        showNotification('导入配置失败: ' + error.message, 'danger');
    }
}

async function parseConfigText(text) {
    try {
        return JSON.parse(text);
    } catch (jsonError) {
        // ignore and try yaml
    }

    try {
        const parser = await ensureYamlParser();
        if (parser) {
            return parser(text);
        }
    } catch (yamlError) {
        console.warn('YAML 解析失败', yamlError);
    }
    throw new Error('无法解析配置文件，请提供有效的 JSON 或 YAML');
}

async function ensureYamlParser() {
    if (window.jsyaml?.load) {
        return window.jsyaml.load;
    }
    try {
        const module = await import('https://cdn.jsdelivr.net/npm/js-yaml@4.1.0/dist/js-yaml.mjs');
        if (module?.load) {
            window.jsyaml = module;
            return module.load;
        }
    } catch (error) {
        console.warn('无法加载 js-yaml 解析器', error);
    }
    return null;
}

function renderValidationResults(results, forceShow = false) {
    const modalContent = document.getElementById('validationResults');
    if (!modalContent) return;

    const hasErrors = Boolean(
        (Array.isArray(results) && results.length > 0) ||
        (results && !Array.isArray(results) && Object.keys(results).length > 0)
    );

    if (!hasErrors && !forceShow) {
        modalContent.innerHTML = '';
        return;
    }

    let html = '';
    if (!results || (Array.isArray(results) && results.length === 0)) {
        html = '<div class="alert alert-success mb-0">配置验证通过</div>';
    } else if (Array.isArray(results)) {
        html = results.map((err) => {
            const field = err.field || err.section || '配置';
            const message = err.message || JSON.stringify(err);
            return `<div class="alert alert-warning mb-2"><strong>${field}</strong>: ${message}</div>`;
        }).join('');
    } else if (typeof results === 'object') {
        html = Object.entries(results).map(([field, messages]) => {
            const joined = Array.isArray(messages) ? messages.join('<br>') : messages;
            return `<div class="alert alert-warning mb-2"><strong>${field}</strong>: ${joined}</div>`;
        }).join('');
    }

    modalContent.innerHTML = html;
    const modal = new bootstrap.Modal(document.getElementById('validationModal'));
    modal.show();
}

function renderTestResults(results = {}, success = false) {
    const panel = document.getElementById('configTestPanel');
    const container = document.getElementById('connectivityResults');
    const badge = document.getElementById('configTestStatusBadge');
    if (!panel || !container || !badge) return;

    const entries = Object.entries(results || {}).filter(([key]) => key !== 'validation');
    if (entries.length === 0) {
        resetTestPanel();
        return;
    }

    container.innerHTML = '';
    entries.forEach(([key, detail]) => {
        const status = detail?.status || 'unknown';
        const message = detail?.message || '';

        const col = document.createElement('div');
        col.className = 'col';

        const card = document.createElement('div');
        card.className = 'border rounded p-3 h-100';

        const header = document.createElement('div');
        header.className = 'd-flex justify-content-between align-items-center mb-2';
        const title = document.createElement('div');
        title.className = 'fw-semibold text-capitalize';
        title.textContent = key;
        const statusBadge = document.createElement('span');
        statusBadge.className = `badge ${LEVEL_BADGE[status] || 'bg-secondary'}`;
        statusBadge.textContent = status;
        header.appendChild(title);
        header.appendChild(statusBadge);

        const body = document.createElement('div');
        body.className = 'text-muted small';
        body.textContent = message;

        card.appendChild(header);
        card.appendChild(body);
        col.appendChild(card);
        container.appendChild(col);
    });

    badge.className = `badge rounded-pill ${success ? 'bg-success' : 'bg-warning text-dark'}`;
    badge.textContent = success ? '通过' : '存在警告';
    panel.classList.remove('d-none');
}

function resetTestPanel() {
    const panel = document.getElementById('configTestPanel');
    const container = document.getElementById('connectivityResults');
    const badge = document.getElementById('configTestStatusBadge');
    if (panel) panel.classList.add('d-none');
    if (container) container.innerHTML = '';
    if (badge) {
        badge.className = 'badge rounded-pill bg-secondary';
        badge.textContent = '未检测';
    }
}

function setTestStatus(status) {
    const badge = document.getElementById('configTestStatusBadge');
    const panel = document.getElementById('configTestPanel');
    if (!badge || !panel) return;
    panel.classList.remove('d-none');
    if (status === 'running') {
        badge.className = 'badge rounded-pill bg-info text-dark';
        badge.textContent = '测试中';
    } else if (status === 'error') {
        badge.className = 'badge rounded-pill bg-danger';
        badge.textContent = '失败';
    }
}

function setInputValue(id, value) {
    const input = document.getElementById(id);
    if (input !== null && input !== undefined) {
        input.value = value ?? '';
    }
}

function setSelectValue(id, value) {
    const select = document.getElementById(id);
    if (!select) return;
    const normalized = value ?? '';
    select.value = normalized;
    if (select.value !== normalized && select.options.length > 0) {
        select.selectedIndex = 0;
    }
}

function setCheckboxValue(id, checked) {
    const input = document.getElementById(id);
    if (input) {
        input.checked = Boolean(checked);
    }
}

function getInputValue(id) {
    const input = document.getElementById(id);
    if (!input) return '';
    return input.value?.trim?.() ?? '';
}

function parseNumberValue(id, fallback = 0) {
    const value = Number(getInputValue(id));
    return Number.isFinite(value) ? value : fallback;
}

function deepClone(obj) {
    try {
        return structuredClone(obj);
    } catch (error) {
        return JSON.parse(JSON.stringify(obj));
    }
}
