(function () {
    // Tìm tất cả container lang-switch chưa được khởi tạo
    document.querySelectorAll('.lang-switch-container').forEach(function (container) {
        if (container.dataset.initialized) return;
        container.dataset.initialized = 'true';

        var btn = container.querySelector('.lang-switch-btn');
        var dropdown = container.querySelector('.lang-switch-dropdown');
        if (!btn || !dropdown) return;

        var isOpen = false;

        function openDropdown() {
            dropdown.classList.remove('hidden');
            isOpen = true;
        }

        function closeDropdown() {
            dropdown.classList.add('hidden');
            isOpen = false;
        }

        btn.addEventListener('click', function (e) {
            e.stopPropagation();
            if (isOpen) {
                closeDropdown();
            } else {
                openDropdown();
            }
        });

        // Close on outside click
        document.addEventListener('click', function () {
            if (isOpen) closeDropdown();
        });

        // Close on Escape
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && isOpen) closeDropdown();
        });
    });
})();