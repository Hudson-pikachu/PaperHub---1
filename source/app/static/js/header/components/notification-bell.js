function initNotificationBell() {

    const bellBtn = document.getElementById('notif-bell-btn');
    const dropdown = document.getElementById('notif-dropdown');
    const notifList = document.getElementById('notif-list');
    const notifDot = document.getElementById('notif-dot');
    const notifCountText = document.getElementById('notif-count-text');
    const markAllReadBtn = document.getElementById('mark-all-read-btn');

    if (!bellBtn || !dropdown || !notifList) return;

    const CURRENT_LANG = document.documentElement.lang || 'vi';

    let isOpen = false;
    let hasLoaded = false;
    let worthyThreshold = 7.0;

    // ─────────────────────────────────────
    // HELPERS
    // ─────────────────────────────────────

    function t(viText, enText) {
        return CURRENT_LANG === 'en' ? enText : viText;
    }

    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function formatDate(dateStr) {
        if (!dateStr) return '';
        const d = new Date(dateStr);
        return d.toLocaleDateString(
            CURRENT_LANG === 'en' ? 'en-US' : 'vi-VN',
            {
                day: '2-digit',
                month: '2-digit',
                year: 'numeric'
            }
        );
    }

    // ─────────────────────────────────────
    // INIT BADGE
    // ─────────────────────────────────────

    (async function initBadge() {
        try {
            const resp = await fetch('/unread-count');
            const data = await resp.json();
            if (data.success) {
                updateBadge(data.unread_count || 0);
            }
        } catch (e) { }
    })();

    function updateMarkAllReadBtn(count) {
        if (!markAllReadBtn) return;
        if (count > 0) {
            markAllReadBtn.classList.remove('hidden');
        } else {
            markAllReadBtn.classList.add('hidden');
        }
    }

    function updateBadge(count) {
        updateMarkAllReadBtn(count);

        if (notifCountText) {
            notifCountText.textContent =
                count === 0
                    ? t('0 nghiên cứu mới', '0 new papers')
                    : t(count + ' nghiên cứu mới', count + ' new papers');
        }

        if (!notifDot) return;

        if (count > 0) {
            notifDot.classList.remove('hidden');
            notifDot.textContent = count > 99 ? '99+' : count;
            notifDot.classList.add(
                'flex', 'items-center', 'justify-center',
                'text-[9px]', 'font-bold', 'text-white', 'leading-none'
            );
            notifDot.style.minWidth = count > 9 ? '18px' : '16px';
            notifDot.style.height = count > 9 ? '18px' : '16px';
            notifDot.style.top = '-2px';
            notifDot.style.right = '-4px';
            notifDot.style.padding = '0 2px';
        } else {
            notifDot.classList.add('hidden');
            notifDot.textContent = '';
            notifDot.classList.remove('flex', 'items-center', 'justify-center');
            notifDot.style = '';
        }
    }

    // ─────────────────────────────────────
    // LOAD NOTIFICATIONS
    // ─────────────────────────────────────

    async function loadNotifications() {
        notifList.innerHTML =
            '<div class="px-5 py-8 text-center text-sm text-slate-400">' +
                t('Đang tải...', 'Loading...') +
            '</div>';

        try {
            const resp = await fetch('/new-papers');
            const data = await resp.json();

            const papers = data.papers || [];
            const count = data.count || 0;

            if (data.worthy_threshold != null) {
                worthyThreshold = data.worthy_threshold;
            }

            updateBadge(count);
            hasLoaded = true;

            if (papers.length === 0) {
                notifList.innerHTML =
                    '<div class="px-5 py-8 text-center text-sm text-slate-400">' +
                        t('Chưa có bài nghiên cứu mới.', 'No new research papers.') +
                    '</div>';
            } else {
                notifList.innerHTML = papers.map(function (p) {
                    const notifTitle =
                        (CURRENT_LANG === 'en' && p.title_en)
                            ? p.title_en
                            : p.title;

                    const isWorthy = p.score != null && p.score >= worthyThreshold;
                    const scoreInt = p.score != null ? Math.round(p.score) : 0;
                    const worthyBadge = isWorthy ? (
                        '<span class="inline-flex items-center gap-1 bg-gradient-to-r from-amber-400 to-yellow-500 text-[#5D4037] text-[9px] font-bold px-1.5 py-0.5 rounded-full border border-amber-300 ml-2" style="font-family: \'Segoe UI\', system-ui, sans-serif;">' +
                            '<svg class="w-3 h-3 flex-shrink-0" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/></svg>' +
                            scoreInt + '/10' +
                        '</span>'
                    ) : '';

                    return (
                        '<a' +
                            ' href="/read/' + p.id + '"' +
                            ' class="notif-item block px-5 py-4 hover:bg-slate-50 transition-colors"' +
                            ' data-paper-id="' + p.id + '"' +
                        '>' +
                            '<p class="text-sm leading-snug">' +
                                '<span class="text-[9px] bg-[#1A365D] text-white px-1.5 py-[2px] rounded-full font-semibold mr-2">' +
                                    escapeHtml(p.category) +
                                '</span>' +
                                '<span class="font-semibold text-[#1A365D]">' +
                                    escapeHtml(notifTitle) +
                                '</span>' +
                            '</p>' +
                            '<p class="text-xs text-slate-400 mt-1 flex items-center gap-1">' +
                                formatDate(p.published_date) +
                                worthyBadge +
                            '</p>' +
                        '</a>'
                    );
                }).join('');

                notifList
                    .querySelectorAll('.notif-item')
                    .forEach(function (item) {
                        item.addEventListener('click', function () {
                            const paperId = parseInt(
                                item.getAttribute('data-paper-id')
                            );
                            if (!paperId) return;

                            fetch('/mark-paper-read', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ paper_id: paperId })
                            })
                                .then(r => r.json())
                                .then(function (d) {
                                    if (!d.success) return;
                                    updateBadge(d.unread_count || 0);
                                    item.style.transition = 'opacity 0.3s';
                                    item.style.opacity = '0';
                                    setTimeout(function () {
                                        item.remove();
                                    }, 300);
                                })
                                .catch(function () { });
                        });
                    });
            }

        } catch (err) {
            notifList.innerHTML =
                '<div class="px-5 py-8 text-center text-sm text-red-400">' +
                    t('Lỗi tải thông báo.', 'Error loading notifications.') +
                '</div>';
        }
    }

    // ─────────────────────────────────────
    // DROPDOWN
    // ─────────────────────────────────────

    function openDropdown() {
        const userDropdown = document.getElementById('user-dropdown');
        if (userDropdown) {
            userDropdown.classList.add('hidden');
        }
        dropdown.classList.remove('hidden');
        isOpen = true;
        loadNotifications();
    }

    function closeDropdown() {
        dropdown.classList.add('hidden');
        isOpen = false;
        hasLoaded = false;
    }

    // ─────────────────────────────────────
    // EVENTS
    // ─────────────────────────────────────

    bellBtn.addEventListener('click', function (e) {
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
            !dropdown.contains(e.target) &&
            !bellBtn.contains(e.target)
        ) {
            closeDropdown();
        }
    });

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && isOpen) {
            closeDropdown();
        }
    });

    // ─────────────────────────────────────
    // MARK ALL READ
    // ─────────────────────────────────────

    if (markAllReadBtn) {
        markAllReadBtn.addEventListener('click', async function (e) {
            e.stopPropagation();
            try {
                const resp = await fetch('/mark-all-read', { method: 'POST' });
                const data = await resp.json();
                if (data.success) {
                    updateBadge(0);
                    notifList.innerHTML =
                        '<div class="px-5 py-8 text-center text-sm text-slate-400">' +
                            t('Chưa có bài nghiên cứu mới.', 'No new research papers.') +
                        '</div>';
                }
            } catch (err) {
                console.error('Mark all read error:', err);
            }
        });
    }
}