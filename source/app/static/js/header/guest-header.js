//Begin show login modal box
const mobileLoginBtn = document.getElementById('mobile-open-login-modal');

if (mobileLoginBtn) {

    mobileLoginBtn.addEventListener('click', () => {

        // Ẩn gate message nếu có (reset từ lần trước)
        const gateMsg = document.getElementById('login-gate-message');
        if (gateMsg) {
            gateMsg.classList.add('hidden');
        }

        loginModal.classList.remove('hidden');
        loginModal.classList.add('flex');

    });

}
//End show login modal box