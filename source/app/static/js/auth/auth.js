/**
 * auth.js — Xử lý đăng nhập / đăng ký qua AJAX (fetch API)
 * Giao tiếp với:  POST /auth/login  |  POST /auth/register
 */

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Hiển thị lỗi trong modal */
function showAuthError(errorEl, message) {
    errorEl.textContent = message;
    errorEl.classList.remove('hidden');
}

/** Ẩn lỗi */
function clearAuthError(errorEl) {
    errorEl.textContent = '';
    errorEl.classList.add('hidden');
}

/** Khoá / mở nút submit trong lúc loading */
function setLoading(btn, isLoading, defaultText) {
    btn.disabled = isLoading;
    btn.textContent = isLoading ? 'Đang xử lý...' : defaultText;
}

// ── Login Form ────────────────────────────────────────────────────────────────

const loginForm = document.getElementById('login-form');
if (loginForm) {
    loginForm.addEventListener('submit', async function (e) {
        e.preventDefault();

        const identifierEl = document.getElementById('login-identifier');
        const passwordEl   = document.getElementById('login-password');
        const rememberEl   = document.getElementById('login-remember');
        const errorEl      = document.getElementById('login-error');
        const submitBtn    = document.getElementById('login-submit');

        clearAuthError(errorEl);
        setLoading(submitBtn, true, 'Đăng nhập');

        try {
            const res = await fetch('/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    identifier: identifierEl.value.trim(),
                    password:   passwordEl.value,
                    remember:   rememberEl ? rememberEl.checked : false,
                }),
            });

            const data = await res.json();

            if (data.success) {
                // Đăng nhập thành công → reload trang
                window.location.href = data.redirect || '/';
            } else {
                showAuthError(errorEl, data.message || 'Đăng nhập thất bại.');
                setLoading(submitBtn, false, 'Đăng nhập');
            }
        } catch (err) {
            showAuthError(errorEl, 'Lỗi kết nối. Vui lòng thử lại.');
            setLoading(submitBtn, false, 'Đăng nhập');
        }
    });
}

// ── Register Form ─────────────────────────────────────────────────────────────

const registerForm = document.getElementById('register-form');
if (registerForm) {
    registerForm.addEventListener('submit', async function (e) {
        e.preventDefault();

        const usernameEl = document.getElementById('register-username');
        const emailEl    = document.getElementById('register-email');
        const passwordEl = document.getElementById('register-password');
        const confirmEl  = document.getElementById('register-confirm');
        const errorEl    = document.getElementById('register-error');
        const submitBtn  = document.getElementById('register-submit');

        clearAuthError(errorEl);

        // Client-side quick check: password match
        if (passwordEl.value !== confirmEl.value) {
            showAuthError(errorEl, 'Mật khẩu xác nhận không khớp.');
            return;
        }

        setLoading(submitBtn, true, 'Đăng ký');

        try {
            const res = await fetch('/auth/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    username:         usernameEl.value.trim(),
                    email:            emailEl.value.trim(),
                    password:         passwordEl.value,
                    confirm_password: confirmEl.value,
                }),
            });

            const data = await res.json();

            if (data.success) {
                // Đăng ký thành công → reload trang
                window.location.href = data.redirect || '/';
            } else {
                showAuthError(errorEl, data.message || 'Đăng ký thất bại.');
                setLoading(submitBtn, false, 'Đăng ký');
            }
        } catch (err) {
            showAuthError(errorEl, 'Lỗi kết nối. Vui lòng thử lại.');
            setLoading(submitBtn, false, 'Đăng ký');
        }
    });
}
