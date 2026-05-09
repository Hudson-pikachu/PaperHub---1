//Back to top
const backToTopBtn = document.getElementById('back-to-top');
window.addEventListener('scroll', () => {
    if (window.scrollY > 400) {
        backToTopBtn.classList.remove('hidden');
        backToTopBtn.classList.add('flex');
    } else {
        backToTopBtn.classList.add('hidden');
        backToTopBtn.classList.remove('flex');
    }
});
backToTopBtn.addEventListener('click', () => {
    window.scrollTo({
        top: 0,
        behavior: 'smooth'
    });
});