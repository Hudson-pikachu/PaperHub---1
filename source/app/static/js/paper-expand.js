//Expand / collapse abstract paper
document.querySelectorAll('.paper-card').forEach(card => {
    const text = card.querySelector('.abstract-text');
    const overlay = card.querySelector('.abstract-overlay');
    const expandBtn = card.querySelector('.expand-btn');
    const collapseBtn = card.querySelector('.collapse-btn');
    if (!text || !overlay || !expandBtn || !collapseBtn) return;
    expandBtn.addEventListener('click', () => {
        text.style.maxHeight = `${text.scrollHeight}px`;
        overlay.classList.add('hidden');
        collapseBtn.classList.remove('hidden');
        text.setAttribute('aria-expanded', 'true');
    });
    collapseBtn.addEventListener('click', () => {
        text.style.maxHeight = '5.5rem';
        overlay.classList.remove('hidden');
        collapseBtn.classList.add('hidden');
        text.setAttribute('aria-expanded', 'false');
    });
});