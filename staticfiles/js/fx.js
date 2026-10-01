/* Aurora motion layer — scroll reveal, count-up, spotlight, magnetic CTAs,
   scroll progress and topbar state. Progressive enhancement only: every
   effect degrades to static content if this file never runs or if the user
   prefers reduced motion. */
(function () {
    'use strict';

    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    const finePointer = window.matchMedia('(hover: hover) and (pointer: fine)');
    const documentRoot = document.documentElement;

    documentRoot.classList.remove('no-js');

    /* ---------- scroll progress rail ---------- */
    const progress = document.createElement('div');
    progress.className = 'scroll-progress';
    progress.setAttribute('aria-hidden', 'true');
    document.body.appendChild(progress);

    /* ---------- topbar glass state ---------- */
    const topbar = document.querySelector('.topbar');

    function onScroll() {
        const scrollTop = window.scrollY || documentRoot.scrollTop;
        const height = documentRoot.scrollHeight - window.innerHeight;
        const ratio = height > 0 ? Math.min(1, scrollTop / height) : 0;
        progress.style.transform = 'scaleX(' + ratio.toFixed(4) + ')';
        if (topbar) topbar.classList.toggle('is-scrolled', scrollTop > 8);
    }

    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll, { passive: true });
    onScroll();

    /* ---------- reveal on scroll (with stagger) ---------- */
    document.querySelectorAll('[data-stagger]').forEach(function (group) {
        const step = parseInt(group.dataset.stagger, 10) || 90;
        Array.prototype.forEach.call(group.children, function (child, index) {
            if (!child.hasAttribute('data-reveal')) child.setAttribute('data-reveal', '');
            child.style.setProperty('--reveal-delay', (index * step) + 'ms');
        });
    });

    const revealNodes = document.querySelectorAll('[data-reveal]');

    if (reducedMotion.matches || !('IntersectionObserver' in window)) {
        revealNodes.forEach(function (node) { node.classList.add('is-visible'); });
    } else {
        const observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (!entry.isIntersecting) return;
                entry.target.classList.add('is-visible');
                observer.unobserve(entry.target);
            });
        }, { rootMargin: '0px 0px -8% 0px', threshold: 0.12 });

        revealNodes.forEach(function (node) { observer.observe(node); });
    }

    /* ---------- count-up numbers ---------- */
    function animateCount(node) {
        const raw = (node.dataset.countTarget || node.textContent || '').trim();
        const match = raw.match(/^([^\d\-]*)(-?[\d,]*\.?\d+)(.*)$/);
        if (!match) return;

        const prefix = match[1] || '';
        const suffix = match[3] || '';
        const target = parseFloat(match[2].replace(/,/g, ''));
        if (!isFinite(target)) return;

        const decimals = (match[2].split('.')[1] || '').length;
        const duration = 1400;
        const start = performance.now();

        function tick(now) {
            const t = Math.min(1, (now - start) / duration);
            const eased = 1 - Math.pow(1 - t, 3);
            const value = target * eased;
            node.textContent = prefix + value.toLocaleString(undefined, {
                minimumFractionDigits: decimals,
                maximumFractionDigits: decimals
            }) + suffix;
            if (t < 1) requestAnimationFrame(tick);
            else node.textContent = raw;
        }

        requestAnimationFrame(tick);
    }

    const countNodes = document.querySelectorAll('[data-count]');
    if (countNodes.length) {
        if (reducedMotion.matches || !('IntersectionObserver' in window)) {
            /* leave values as rendered */
        } else {
            const countObserver = new IntersectionObserver(function (entries) {
                entries.forEach(function (entry) {
                    if (!entry.isIntersecting) return;
                    animateCount(entry.target);
                    countObserver.unobserve(entry.target);
                });
            }, { threshold: 0.4 });
            countNodes.forEach(function (node) { countObserver.observe(node); });
        }
    }

    /* ---------- password reveal toggle (auth forms) ---------- */
    document.querySelectorAll('[data-toggle-password]').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var input = document.getElementById(btn.getAttribute('data-toggle-password'));
            if (!input) return;
            var showing = input.type === 'text';
            input.type = showing ? 'password' : 'text';
            btn.setAttribute('aria-pressed', String(!showing));
            btn.setAttribute('aria-label', showing ? 'Show password' : 'Hide password');
            var icon = btn.querySelector('i');
            if (icon) icon.className = showing ? 'fas fa-eye' : 'fas fa-eye-slash';
            input.focus({ preventScroll: true });
        });
    });

    /* ---------- cursor spotlight on cards ---------- */
    if (finePointer.matches) {
        const spotlightSelector = '.stat-card, .person-card, .overview-stat-card, .overview-result, .card';
        document.querySelectorAll(spotlightSelector).forEach(function (card) {
            card.classList.add('spotlight');
            card.addEventListener('pointermove', function (event) {
                const bounds = card.getBoundingClientRect();
                card.style.setProperty('--mx', ((event.clientX - bounds.left) / bounds.width * 100).toFixed(2) + '%');
                card.style.setProperty('--my', ((event.clientY - bounds.top) / bounds.height * 100).toFixed(2) + '%');
            }, { passive: true });
        });

        /* ---------- magnetic primary CTAs ---------- */
        document.querySelectorAll('.btn-primary, .btn-gold, .overview-primary-action').forEach(function (btn) {
            btn.addEventListener('pointermove', function (event) {
                const bounds = btn.getBoundingClientRect();
                const dx = (event.clientX - bounds.left - bounds.width / 2) / bounds.width;
                const dy = (event.clientY - bounds.top - bounds.height / 2) / bounds.height;
                btn.style.transform = 'translate(' + (dx * 8).toFixed(2) + 'px,' + (dy * 6 - 2).toFixed(2) + 'px)';
            }, { passive: true });
            btn.addEventListener('pointerleave', function () {
                btn.style.transform = '';
            });
        });
    }
}());
