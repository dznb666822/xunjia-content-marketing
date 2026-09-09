// ==================== Helpers ====================
var cachedBrands = [];

function fmtCount(n) {
    n = parseInt(n) || 0;
    if (n >= 100000000) return (n / 100000000).toFixed(1) + '亿';
    if (n >= 10000) return (n / 10000).toFixed(1) + '万';
    return n.toString();
}

function fmtDuration(ms) {
    ms = parseInt(ms) || 0;
    var totalSec = Math.floor(ms / 1000);
    var m = Math.floor(totalSec / 60);
    var s = totalSec % 60;
    return m + ':' + (s < 10 ? '0' : '') + s;
}

function getVal(id) {
    var el = document.getElementById(id);
    return el ? el.value.trim() : '';
}

function getCheckedIds(className) {
    var ids = [];
    var cbs = document.querySelectorAll('.' + className + ':checked');
    for (var i = 0; i < cbs.length; i++) {
        if (cbs[i].value) ids.push(cbs[i].value);
    }
    return ids;
}

function spinner(id, show) {
    var el = document.getElementById(id);
    if (el) el.classList.toggle('show', !!show);
}

function showResult(id, json) {
    var el = document.getElementById(id);
    if (!el) return;
    el.classList.add('show');
    el.textContent = typeof json === 'string' ? json : JSON.stringify(json, null, 2);
}

function showToast(msg, type) {
    var t = document.createElement('div');
    t.className = 'toast ' + (type || 'success');
    t.textContent = msg;
    var container = document.getElementById('toast-container');
    if (container) container.appendChild(t);
    setTimeout(function () { t.remove(); }, 3000);
}

function toggleCheckAll(className, masterCheckbox) {
    var checked = masterCheckbox.checked;
    var cbs = document.querySelectorAll('.' + className);
    for (var i = 0; i < cbs.length; i++) {
        cbs[i].checked = checked;
    }
}
