// ==================== Brand Management ====================
var cachedBrands = [];

function fetchAndPopulateBrands() {
    fetch('/api/brands')
        .then(function (resp) { return resp.json(); })
        .then(function (json) {
            if (json.success) {
                cachedBrands = json.data || [];
                populateBrandSelects(cachedBrands);
                renderBrandList(cachedBrands);
            } else {
                showToast('获取账号列表失败: ' + (json.error || '未知错误'), 'error');
            }
        })
        .catch(function (e) {
            showToast('请求账号列表失败: ' + e.message, 'error');
        });
}

function populateBrandSelects(brands) {
    var selects = ['disc-brand', 'script-brand', 'script-type-brand', 'dash-brand'];
    for (var s = 0; s < selects.length; s++) {
        var sel = document.getElementById(selects[s]);
        if (!sel) continue;
        var currentVal = sel.value;
        sel.innerHTML = '<option value="">-- 请选择账号 --</option>';
        for (var i = 0; i < brands.length; i++) {
            var b = brands[i];
            sel.innerHTML += '<option value="' + b.id + '">' + escapeHtml(b.name) + '</option>';
        }
        sel.value = currentVal;
    }
}

function renderBrandList(brands) {
    var container = document.getElementById('brand-list-container');
    if (!container) return;
    if (!brands || brands.length === 0) {
        container.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-muted);">暂无账号，请注册</div>';
        return;
    }
    var html = '';
    for (var i = 0; i < brands.length; i++) {
        var b = brands[i];
        html += '<div class="brand-card" style="padding:12px 16px;border-bottom:1px solid var(--border);cursor:pointer;" onclick="editBrand(\'' + b.id + '\')">';
        html += '<div style="font-weight:600;font-size:14px;">' + escapeHtml(b.name || '') + '</div>';
        html += '<div style="font-size:12px;color:var(--text-dim);margin-top:4px;">' + escapeHtml(b.category || '') + ' · ' + escapeHtml(b.target_audience || '') + '</div>';
        html += '</div>';
    }
    container.innerHTML = html;
}

function editBrand(brandId) {
    if (!document.getElementById('brand-edit-id')) return; // 已移至登录页
    var brand = null;
    for (var i = 0; i < cachedBrands.length; i++) {
        if (cachedBrands[i].id === brandId) { brand = cachedBrands[i]; break; }
    }
    if (!brand) return;
    document.getElementById('brand-edit-id').value = brand.id;
    document.getElementById('brand-name').value = brand.name || '';
    document.getElementById('brand-category').value = brand.category || '';
    document.getElementById('brand-audience').value = brand.target_audience || '';
    document.getElementById('brand-desc').value = brand.product_desc || '';
    document.getElementById('brand-style').value = brand.style_tone || '';
    document.getElementById('brand-sellpoints').value = (brand.selling_points || []).join('\n');
    document.getElementById('brand-form-title').textContent = '编辑账号';
    document.getElementById('btn-delete-brand').style.display = 'inline-block';
}

function resetBrandForm() {
    if (!document.getElementById('brand-edit-id')) return; // 已移至登录页
    document.getElementById('brand-name').value = '';
    document.getElementById('brand-category').value = '';
    document.getElementById('brand-audience').value = '';
    document.getElementById('brand-desc').value = '';
    document.getElementById('brand-style').value = '';
    document.getElementById('brand-sellpoints').value = '';
    document.getElementById('brand-form-title').textContent = '注册新账号';
    document.getElementById('btn-delete-brand').style.display = 'none';
}

function saveBrand() {
    if (!document.getElementById('brand-edit-id')) return; // 已移至登录页
    var editId = getVal('brand-edit-id');
    var sellingPointsRaw = getVal('brand-sellpoints');
    var sellingPoints = sellingPointsRaw ? sellingPointsRaw.split('\n').filter(function (s) { return s.trim(); }) : [];
    var payload = {
        name: getVal('brand-name'),
        category: getVal('brand-category'),
        target_audience: getVal('brand-audience'),
        product_desc: getVal('brand-desc'),
        style_tone: getVal('brand-style'),
        selling_points: sellingPoints
    };

    if (!payload.name) { showToast('请输入账号名称', 'error'); return; }

    var url, method;
    if (editId) {
        url = '/api/brands/' + editId;
        method = 'PUT';
    } else {
        url = '/api/brands';
        method = 'POST';
    }

    spinner('spinner-brand', true);
    fetch(url, {
        method: method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
        .then(function (resp) { return resp.json(); })
        .then(function (json) {
            spinner('spinner-brand', false);
            if (json.success) {
                showToast(editId ? '账号更新成功' : '账号创建成功', 'success');
                resetBrandForm();
                fetchAndPopulateBrands();
            } else {
                showToast('保存失败: ' + (json.error || '未知错误'), 'error');
            }
        })
        .catch(function (e) {
            spinner('spinner-brand', false);
            showToast('请求失败: ' + e.message, 'error');
        });
}

function createBrand() {
    if (!document.getElementById('brand-edit-id')) return; // 已移至登录页
    var sellingPointsRaw = getVal('brand-sellpoints');
    var sellingPoints = sellingPointsRaw ? sellingPointsRaw.split('\n').filter(function (s) { return s.trim(); }) : [];
    var payload = {
        name: getVal('brand-name'),
        category: getVal('brand-category'),
        target_audience: getVal('brand-audience'),
        product_desc: getVal('brand-desc'),
        style_tone: getVal('brand-style'),
        selling_points: sellingPoints
    };

    if (!payload.name) { showToast('请输入账号名称', 'error'); return; }

    spinner('spinner-brand', true);
    fetch('/api/brands', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
        .then(function (resp) { return resp.json(); })
        .then(function (json) {
            spinner('spinner-brand', false);
            if (json.success) {
                showToast('账号创建成功', 'success');
                resetBrandForm();
                fetchAndPopulateBrands();
            } else {
                showToast('创建失败: ' + (json.error || '未知错误'), 'error');
            }
        })
        .catch(function (e) {
            spinner('spinner-brand', false);
            showToast('请求失败: ' + e.message, 'error');
        });
}

function deleteBrand(brandId) {
    if (!document.getElementById('brand-edit-id')) return; // 已移至登录页
    var bid = brandId || getVal('brand-edit-id');
    if (!confirm('确定要删除该账号吗？此操作不可恢复。')) return;

    spinner('spinner-brand', true);
    fetch('/api/brands/' + bid, { method: 'DELETE' })
        .then(function (resp) { return resp.json(); })
        .then(function (json) {
            spinner('spinner-brand', false);
            if (json.success) {
                showToast('账号已删除', 'success');
                resetBrandForm();
                fetchAndPopulateBrands();
            } else {
                showToast('删除失败: ' + (json.error || '未知错误'), 'error');
            }
        })
        .catch(function (e) {
            spinner('spinner-brand', false);
            showToast('请求失败: ' + e.message, 'error');
        });
}
