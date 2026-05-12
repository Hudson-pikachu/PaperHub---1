function initSearchBar() {
    // Tìm tất cả search input trong page (cả desktop lẫn mobile)
    var searchInputs = document.querySelectorAll('input[data-search-input]');
    if (searchInputs.length === 0) return;

    var currentLang = document.documentElement.lang || 'vi';

    searchInputs.forEach(function (input) {
        var form = input.closest('.search-form');
        var dropdown = form ? form.querySelector('.search-dropdown') : null;
        if (!dropdown) return;

        input.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                var q = input.value.trim();
                if (q.length < 1) {
                    dropdown.classList.add('hidden');
                    return;
                }
                doSearch(q, dropdown, input);
            }
        });

        // Close dropdown when clicking outside
        document.addEventListener('click', function (e) {
            if (!form.contains(e.target)) {
                dropdown.classList.add('hidden');
            }
        });

        // Close on Escape
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') {
                dropdown.classList.add('hidden');
            }
        });
    });

    function escapeHtml(text) {
        if (!text) return '';
        var div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function highlight(text, keyword) {
        if (!text || !keyword) return escapeHtml(text);
        var re = new RegExp('(' + keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'gi');
        return escapeHtml(text).replace(re, '<mark class="bg-yellow-200 text-[#1A365D] rounded px-0.5">$1</mark>');
    }

    function pickField(enField, viField) {
        if (currentLang === 'en' && enField && enField.trim() !== '') return enField;
        return viField;
    }

    function formatDate(dateStr) {
        if (!dateStr) return '';
        var d = new Date(dateStr);
        if (isNaN(d.getTime())) return dateStr;
        return d.toLocaleDateString(currentLang === 'en' ? 'en-US' : 'vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric' });
    }

    function doSearch(q, dropdown, input) {
        dropdown.innerHTML = '<div class="px-5 py-4 text-center text-sm text-slate-400">' + (currentLang === 'en' ? 'Searching...' : 'Đang tìm...') + '</div>';
        dropdown.classList.remove('hidden');

        fetch('/search?q=' + encodeURIComponent(q))
            .then(function (r) { return r.json(); })
            .then(function (data) {
                var papers = data.papers || [];
                if (papers.length === 0) {
                    dropdown.innerHTML = '<div class="px-5 py-8 text-center text-sm text-slate-400">' + (currentLang === 'en' ? 'No results found for "' : 'Không tìm thấy kết quả cho "') + escapeHtml(q) + '"</div>';
                    return;
                }

                var html = '';
                papers.forEach(function (p) {
                    // Ưu tiên hiển thị theo ngôn ngữ khớp: nếu title_en/abstract_en khớp keyword → hiện tiếng Anh, ngược lại hiện tiếng Việt
                    var kw = q.toLowerCase();
                    var titleEnMatch = p.title_en && p.title_en.toLowerCase().indexOf(kw) !== -1;
                    var abstractEnMatch = p.abstract_en && p.abstract_en.toLowerCase().indexOf(kw) !== -1;
                    var titleViMatch = p.title && p.title.toLowerCase().indexOf(kw) !== -1;
                    var abstractViMatch = p.abstract && p.abstract.toLowerCase().indexOf(kw) !== -1;

                    // Nếu chỉ khớp tiếng Anh (không khớp tiếng Việt) → hiện tiếng Anh
                    // Nếu chỉ khớp tiếng Việt → hiện tiếng Việt
                    // Nếu cả 2 cùng khớp → theo currentLang
                    var useEn = false;
                    if ((titleEnMatch || abstractEnMatch) && !titleViMatch && !abstractViMatch) {
                        useEn = true;
                    } else if (!titleEnMatch && !abstractEnMatch && (titleViMatch || abstractViMatch)) {
                        useEn = false;
                    } else {
                        useEn = currentLang === 'en';
                    }

                    var displayTitle = useEn ? (p.title_en || p.title) : p.title;
                    var displayAbstract = useEn ? (p.abstract_en || p.abstract) : (p.abstract || p.abstract_en || '');
                    var authors = p.authors || '';
                    var maxAuthorLen = 80;
                    if (authors.length > maxAuthorLen) {
                        authors = authors.substring(0, maxAuthorLen) + '...';
                    }

                    html += '<a href="/read/' + p.id + '" class="search-result-item block px-5 py-4 hover:bg-slate-50 transition-colors border-b border-slate-100 last:border-b-0">' +
                        '<div class="flex items-start gap-3">' +
                        '<div class="flex-1 min-w-0">' +
                        '<p class="text-sm leading-snug font-semibold text-[#1A365D]">' + highlight(displayTitle, q) + '</p>' +
                        '<p class="text-xs text-slate-400 mt-1">' + escapeHtml(authors) + ' • ' + escapeHtml(p.category || '') + ' • ' + formatDate(p.published_date) + '</p>' +
                        '<p class="text-xs text-slate-500 mt-1 line-clamp-2">' + highlight(displayAbstract, q) + '</p>' +
                        '</div>' +
                        '</div>' +
                        '</a>';
                });

                dropdown.innerHTML = html;
            })
            .catch(function () {
                dropdown.innerHTML = '<div class="px-5 py-8 text-center text-sm text-red-400">' + (currentLang === 'en' ? 'Search error. Please try again.' : 'Lỗi tìm kiếm, vui lòng thử lại.') + '</div>';
            });
    }
}