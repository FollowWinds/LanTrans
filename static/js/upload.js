/**
 * 局域网文件共享 — 上传模块
 * 使用 XMLHttpRequest 实现真实上传进度、超时检测、失败弹窗
 */

(function () {
    'use strict';

    // ---- DOM 引用 ----
    const form = document.querySelector('.upload-form');
    const fileInput = document.getElementById('fileInput');
    const uploadBtn = document.getElementById('uploadBtn');
    const cancelBtn = document.getElementById('cancelBtn');
    const progressContainer = document.getElementById('progressContainer');
    const progressBar = document.getElementById('progressBar');
    const progressPercent = document.getElementById('progressPercent');
    const progressSpeed = document.getElementById('progressSpeed');
    const modalOverlay = document.getElementById('modalOverlay');
    const modalIcon = document.getElementById('modalIcon');
    const modalTitle = document.getElementById('modalTitle');
    const modalBody = document.getElementById('modalBody');
    const modalClose = document.getElementById('modalClose');

    let xhr = null;
    let startTime = 0;
    const UPLOAD_TIMEOUT = 120000; // 2 分钟超时

    // ---- 事件绑定 ----
    form.addEventListener('submit', onUploadStart);
    cancelBtn.addEventListener('click', onCancel);
    modalClose.addEventListener('click', hideModal);
    modalOverlay.addEventListener('click', function (e) {
        if (e.target === modalOverlay) hideModal();
    });
    // ESC 关闭弹窗
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') hideModal();
    });

    // ---- 开始上传 ----
    function onUploadStart(e) {
        e.preventDefault();

        const file = fileInput.files[0];
        if (!file) {
            showModal('⚠️', '未选择文件', '请先选择一个文件再上传。');
            return;
        }

        // 切换到上传中 UI
        setUploadingUI(true);

        const formData = new FormData();
        formData.append('file', file);

        xhr = new XMLHttpRequest();
        xhr.open('POST', form.action, true);
        xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
        xhr.timeout = UPLOAD_TIMEOUT;

        startTime = Date.now();

        // ---- 上传进度 ----
        xhr.upload.addEventListener('progress', function (e) {
            if (e.lengthComputable && e.total > 0) {
                const pct = Math.round((e.loaded / e.total) * 100);
                progressBar.style.width = pct + '%';
                progressPercent.textContent = pct + '%';

                const elapsed = (Date.now() - startTime) / 1000;
                if (elapsed > 0.3) {
                    const speed = e.loaded / elapsed;
                    progressSpeed.textContent = formatSpeed(speed);
                }
            }
        });

        // ---- 上传完成 ----
        xhr.addEventListener('load', function () {
            setUploadingUI(false);

            if (xhr.status === 200) {
                try {
                    const resp = JSON.parse(xhr.responseText);
                    if (resp.success) {
                        // 成功：绿色完成态
                        progressBar.classList.add('complete');
                        progressBar.style.width = '100%';
                        progressPercent.textContent = '✅ ' + (resp.message || '上传成功');
                        progressSpeed.textContent = resp.size_str || '';
                        progressContainer.style.display = 'block';
                        // 1.5 秒后刷新页面
                        setTimeout(function () { location.reload(); }, 1500);
                    } else {
                        showModal('❌', '上传失败', resp.error || '服务器返回错误，请稍后重试。');
                    }
                } catch (parseErr) {
                    // 非 JSON 响应（可能是重定向页面），直接刷新
                    location.reload();
                }
                return;
            }

            // HTTP 错误状态
            handleHttpError(xhr.status);
        });

        // ---- 超时 ----
        xhr.addEventListener('timeout', function () {
            setUploadingUI(false);
            showModal('⏱️', '上传超时',
                '上传时间超过 ' + (UPLOAD_TIMEOUT / 1000) + ' 秒，请检查：\n\n' +
                '1. 网络连接是否稳定\n' +
                '2. 文件是否过大（建议压缩后重试）\n' +
                '3. 服务器是否正常运行');
        });

        // ---- 网络错误 ----
        xhr.addEventListener('error', function () {
            setUploadingUI(false);
            showModal('🔌', '网络错误',
                '无法连接到服务器，请检查：\n\n' +
                '• 是否连接到同一 Wi-Fi\n' +
                '• 服务器是否仍在运行\n' +
                '• 防火墙是否阻止了连接');
        });

        // ---- 取消 ----
        xhr.addEventListener('abort', function () {
            setUploadingUI(false);
            progressContainer.style.display = 'none';
            progressBar.classList.remove('complete');
            progressBar.style.width = '0%';
        });

        xhr.send(formData);
    }

    // ---- 取消上传 ----
    function onCancel() {
        if (xhr && xhr.readyState !== XMLHttpRequest.DONE) {
            xhr.abort();
        }
    }

    // ---- HTTP 错误处理 ----
    function handleHttpError(status) {
        switch (status) {
            case 413:
                showModal('📦', '文件过大',
                    '文件大小超过服务器限制（500MB）。\n\n请压缩文件或分批上传。');
                break;
            case 404:
                showModal('🔍', '服务不可用',
                    '上传接口不存在（404），请检查服务器是否正常运行。');
                break;
            case 500:
            case 502:
            case 503:
                showModal('💥', '服务器错误',
                    '服务器内部错误（HTTP ' + status + '）。\n\n请稍后重试，或重启服务器。');
                break;
            default:
                showModal('❌', '上传失败',
                    '服务器返回错误状态（HTTP ' + status + '）。\n\n请稍后重试。');
        }
    }

    // ---- UI 切换 ----
    function setUploadingUI(uploading) {
        if (uploading) {
            uploadBtn.style.display = 'none';
            cancelBtn.style.display = 'inline-block';
            progressContainer.style.display = 'block';
            progressBar.classList.remove('complete');
            progressBar.style.width = '0%';
            progressPercent.textContent = '0%';
            progressSpeed.textContent = '';
            progressContainer.classList.add('uploading');
        } else {
            uploadBtn.style.display = 'inline-block';
            cancelBtn.style.display = 'none';
            progressContainer.classList.remove('uploading');
        }
    }

    // ---- 弹窗 ----
    function showModal(icon, title, body) {
        modalIcon.textContent = icon;
        modalTitle.textContent = title;
        modalBody.textContent = body;
        modalOverlay.classList.add('active');
    }

    function hideModal() {
        modalOverlay.classList.remove('active');
    }

    // ---- 速度格式化 ----
    function formatSpeed(bytesPerSec) {
        if (bytesPerSec < 1024) return Math.round(bytesPerSec) + ' B/s';
        if (bytesPerSec < 1048576) return (bytesPerSec / 1024).toFixed(1) + ' KB/s';
        return (bytesPerSec / 1048576).toFixed(1) + ' MB/s';
    }
})();
