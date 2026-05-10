//Lấy phần tử modal Login từ HTML
const loginModal = document.getElementById('login-modal');

//Lấy phần tử modal Register từ HTML
const registerModal = document.getElementById('register-modal');

//Bấm Esc đế đóng modal ()
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        if (loginModal) {
            loginModal.classList.add('hidden');
            loginModal.classList.remove('flex');
        }

        if (registerModal) {
            registerModal.classList.add('hidden');
            registerModal.classList.remove('flex');
        }
    }
});

//LOGIN MODAL
const openLoginBtn = document.getElementById('open-login-modal');

if (openLoginBtn) {
    openLoginBtn.addEventListener('click', () => {
        loginModal.classList.remove('hidden');
        loginModal.classList.add('flex');
    });
}

//Khi bấm nút "Đóng" trong modal Login
const closeLoginBtn = document.getElementById('close-login-modal');

if (closeLoginBtn) {
    closeLoginBtn.addEventListener('click', () => {
        //Ẩn modal Login
        loginModal.classList.add('hidden');

        //Xóa class flex
        loginModal.classList.remove('flex');
    });
}

//Click backdrop để đóng modal login
if (loginModal) {

    loginModal.addEventListener('click', (e) => {
        if (e.target === loginModal) {
            loginModal.classList.add('hidden');
            loginModal.classList.remove('flex');
        }
    });
}

//REGISTER MODAL
const openRegisterBtn = document.getElementById('open-register-modal');

if (openRegisterBtn) {
    openRegisterBtn.addEventListener('click', () => {
        registerModal.classList.remove('hidden');
        registerModal.classList.add('flex');
    });
}

//Khi bấm nút "Đóng" trong modal Register
const closeRegisterBtn = document.getElementById('close-register-modal');

if (closeRegisterBtn) {
    closeRegisterBtn.addEventListener('click', () => {
        //Ẩn modal Register
        registerModal.classList.add('hidden');

        //Xóa class flex
        registerModal.classList.remove('flex');
    });
}

//Click backdrop để đóng modal register
if (registerModal) {
    registerModal.addEventListener('click', (e) => {
        if (e.target === registerModal) {
            registerModal.classList.add('hidden');
            registerModal.classList.remove('flex');
        }
    });
}

//Switch Login -> Register
const switchToRegisterBtn = document.getElementById('switch-to-register-modal');

if (switchToRegisterBtn) {

    switchToRegisterBtn.addEventListener('click', () => {

        loginModal.classList.add('hidden');
        loginModal.classList.remove('flex');

        registerModal.classList.remove('hidden');
        registerModal.classList.add('flex');

    });

}

//Switch Register -> Login
const switchToLoginBtn = document.getElementById('switch-to-login-modal');

if (switchToLoginBtn) {

    switchToLoginBtn.addEventListener('click', () => {

        registerModal.classList.add('hidden');
        registerModal.classList.remove('flex');

        loginModal.classList.remove('hidden');
        loginModal.classList.add('flex');

    });

}