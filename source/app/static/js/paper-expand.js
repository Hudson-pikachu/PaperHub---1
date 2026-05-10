// Expand / collapse abstract paper - Event delegation
document.addEventListener('click', function (e) {
    // Xử lý nút "Xem thêm"
    const expandBtn = e.target.closest('.expand-btn');
    if (expandBtn) {
        const card = expandBtn.closest('.paper-card');
        if (!card) return;
        const text = card.querySelector('.abstract-text');
        const overlay = card.querySelector('.abstract-overlay');
        const collapseBtn = card.querySelector('.collapse-btn');
        if (!text || !overlay || !collapseBtn) return;
        text.style.maxHeight = `${text.scrollHeight}px`;
        overlay.classList.add('hidden');
        collapseBtn.classList.remove('hidden');
        text.setAttribute('aria-expanded', 'true');
        return;
    }

    // Xử lý nút "Thu gọn"
    const collapseBtn = e.target.closest('.collapse-btn');
    if (collapseBtn) {
        const card = collapseBtn.closest('.paper-card');
        if (!card) return;
        const text = card.querySelector('.abstract-text');
        const overlay = card.querySelector('.abstract-overlay');
        const expandBtn = card.querySelector('.expand-btn');
        if (!text || !overlay || !expandBtn) return;
        text.style.maxHeight = '5.5rem';
        overlay.classList.remove('hidden');
        collapseBtn.classList.add('hidden');
        text.setAttribute('aria-expanded', 'false');
        return;
    }
});
