function initUserDropdown() {

    const userBtn = document.getElementById('user-menu-btn');
    const userDropdown = document.getElementById('user-dropdown');

    if (!userBtn || !userDropdown) return;

    let isOpen = false;

    function openDropdown() {

        const notifDropdown = document.getElementById('notif-dropdown');

        if (notifDropdown) {
            notifDropdown.classList.add('hidden');
        }

        userDropdown.classList.remove('hidden');

        isOpen = true;
    }

    function closeDropdown() {

        userDropdown.classList.add('hidden');

        isOpen = false;
    }

    userBtn.addEventListener('click', function (e) {

        e.stopPropagation();

        if (isOpen) {
            closeDropdown();
        } else {
            openDropdown();
        }
    });

    document.addEventListener('click', function (e) {

        if (
            isOpen &&
            !userDropdown.contains(e.target) &&
            !userBtn.contains(e.target)
        ) {
            closeDropdown();
        }
    });

    document.addEventListener('keydown', function (e) {

        if (e.key === 'Escape' && isOpen) {
            closeDropdown();
        }
    });
}