/* ==========================================================================
   Кругосвет — Личный кабинет
   account.js  ·  без зависимостей, работает вместе с Lenis из base.html
   ========================================================================== */
(function () {
    'use strict';

    const root = document.querySelector('.acc');
    if (!root) return;

    const REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const COARSE = window.matchMedia('(hover: none)').matches;
    const $ = (s, c = document) => c.querySelector(s);
    const $$ = (s, c = document) => Array.from(c.querySelectorAll(s));
    const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
    const nf = new Intl.NumberFormat('ru-RU');

    /* ----------------------------------------------------------------------
       0. Включаем SVG-преломление только там, где оно не ломает рендер
       ---------------------------------------------------------------------- */
    (function enableLiquidGlass() {
        if (REDUCED || COARSE) return;
        const ua = navigator.userAgent;
        const isSafari = /^((?!chrome|android).)*safari/i.test(ua);
        const supports = CSS.supports('backdrop-filter', 'blur(1px)') ||
                         CSS.supports('-webkit-backdrop-filter', 'blur(1px)');
        // Safari некорректно комбинирует backdrop-filter + SVG filter — там оставляем чистое стекло
        if (supports && !isSafari) document.documentElement.classList.add('lg-on');
    })();

    /* ======================================================================
       1. Тосты с распадом на частицы
       Живут TOAST_LIFE мс, при наведении пауза, по клику закрываются сразу.
       Уходя — рассыпаются в пыль и улетают вправо, будто их сдуло ветром.
       ====================================================================== */
    const toastHost = $('[data-toasts]');
    const TOAST_LIFE = 3400;   // сколько висит, мс
    const TOAST_MAX = 4;       // сколько показываем одновременно
    const BLOW_MS = 900;       // длительность распада

    const SVG_NS = 'http://www.w3.org/2000/svg';
    let dustLayer = null, filterHost = null, filterSeq = 0;

    function getDustLayer() {
        if (!dustLayer) {
            dustLayer = document.createElement('div');
            dustLayer.className = 'dust-layer';
            document.body.appendChild(dustLayer);
        }
        return dustLayer;
    }

    // отдельный SVG-фильтр на каждый тост, иначе распады будут мешать друг другу
    function makeDissolveFilter() {
        if (!filterHost) {
            filterHost = document.createElementNS(SVG_NS, 'svg');
            filterHost.setAttribute('class', 'dust-filters');
            filterHost.setAttribute('aria-hidden', 'true');
            document.body.appendChild(filterHost);
        }

        const id = 'toast-dissolve-' + (++filterSeq);
        const filter = document.createElementNS(SVG_NS, 'filter');
        filter.setAttribute('id', id);
        filter.setAttribute('x', '-80%');
        filter.setAttribute('y', '-80%');
        filter.setAttribute('width', '260%');
        filter.setAttribute('height', '260%');
        filter.setAttribute('color-interpolation-filters', 'sRGB');

        const turb = document.createElementNS(SVG_NS, 'feTurbulence');
        turb.setAttribute('type', 'fractalNoise');
        turb.setAttribute('baseFrequency', '0.02');
        turb.setAttribute('numOctaves', '2');
        turb.setAttribute('seed', String(Math.floor(performance.now() % 100)));
        turb.setAttribute('result', 'noise');

        const disp = document.createElementNS(SVG_NS, 'feDisplacementMap');
        disp.setAttribute('in', 'SourceGraphic');
        disp.setAttribute('in2', 'noise');
        disp.setAttribute('scale', '0');
        disp.setAttribute('xChannelSelector', 'R');
        disp.setAttribute('yChannelSelector', 'G');

        filter.appendChild(turb);
        filter.appendChild(disp);
        filterHost.appendChild(filter);

        return { id, filter, turb, disp };
    }

    // облако пыли по площади тоста; левый край срывается первым — как порыв ветра
    function spawnDust(rect) {
        const layer = getDustLayer();

        const TONES = ['', ' dust--accent', ' dust--spark'];

        for (let i = 0; i < 34; i++) {
            const dot = document.createElement('span');
            const x = rect.left + Math.random() * rect.width;
            const y = rect.top + Math.random() * rect.height;
            const size = 3 + Math.random() * 5;

            dot.className = 'dust' + TONES[Math.floor(Math.random() * TONES.length)];
            dot.style.left = x + 'px';
            dot.style.top = y + 'px';
            dot.style.width = dot.style.height = size + 'px';
            layer.appendChild(dot);

            const dx = 90 + Math.random() * 230;
            const dy = -70 + Math.random() * 80;
            const delay = ((x - rect.left) / rect.width) * 190;

            const anim = dot.animate([
                { transform: 'translate3d(0,0,0) scale(1)', opacity: .95 },
                { transform: `translate3d(${dx * .32}px, ${dy * .45}px, 0) scale(.85)`, opacity: .75, offset: .35 },
                { transform: `translate3d(${dx}px, ${dy}px, 0) scale(.15)`, opacity: 0 }
            ], {
                duration: 760 + Math.random() * 560,
                delay,
                easing: 'cubic-bezier(.15,.7,.3,1)',
                fill: 'forwards'
            });

            anim.onfinish = () => dot.remove();
        }
    }

    function dismissToast(el) {
        if (!el || el.dataset.gone === '1') return;
        el.dataset.gone = '1';
        clearTimeout(Number(el.dataset.timer));

        const rect = el.getBoundingClientRect();

        // запоминаем, где стоят соседи, чтобы плавно подтянуть их на освободившееся место
        const siblings = $$('.toast', toastHost).filter(t => t !== el);
        const before = siblings.map(t => t.getBoundingClientRect().top);

        // переносим в фиксированный слой: .toast-host прижат к низу и при
        // схлопывании уехал бы вместе с улетающим тостом
        el.style.position = 'fixed';
        el.style.left = rect.left + 'px';
        el.style.top = rect.top + 'px';
        el.style.width = rect.width + 'px';
        el.style.margin = '0';
        el.style.pointerEvents = 'none';
        getDustLayer().appendChild(el);

        siblings.forEach((t, i) => {
            const delta = before[i] - t.getBoundingClientRect().top;
            if (!delta || REDUCED) return;
            t.animate([{ transform: `translateY(${delta}px)` }, { transform: 'none' }],
                { duration: 320, easing: 'cubic-bezier(.22,.61,.36,1)' });
        });

        if (REDUCED) { el.remove(); return; }

        spawnDust(rect);

        const f = makeDissolveFilter();
        el.style.filter = `url(#${f.id})`;
        el.style.backdropFilter = 'none';
        el.style.webkitBackdropFilter = 'none';

        const t0 = performance.now();

        (function blow(now) {
            const p = clamp((now - t0) / BLOW_MS, 0, 1);
            const e = p * p;                                   // распад ускоряется

            f.disp.setAttribute('scale', (e * 95).toFixed(1));
            f.turb.setAttribute('baseFrequency', (0.02 + e * 0.06).toFixed(4));

            el.style.opacity = String(1 - e);
            el.style.transform =
                `translate3d(${e * 170}px, ${-p * 24}px, 0) skewX(${p * 12}deg) scale(${1 + p * .06})`;

            if (p < 1) requestAnimationFrame(blow);
            else { el.remove(); f.filter.remove(); }
        })(t0);
    }

    function scheduleToast(el, delay) {
        clearTimeout(Number(el.dataset.timer));
        el.dataset.timer = String(setTimeout(() => dismissToast(el), delay));
    }

    function toast(message) {
        if (!toastHost || !message) return;

        // не даём стопке разрастаться — самые старые сдуваем раньше
        const live = $$('.toast', toastHost).filter(t => t.dataset.gone !== '1');
        live.slice(0, Math.max(0, live.length - TOAST_MAX + 1)).forEach(dismissToast);

        const el = document.createElement('div');
        el.className = 'toast';
        el.innerHTML =
            '<span class="toast__ic">' +
            '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
            'stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="m4 12 5 5L20 6"/></svg>' +
            '</span><span></span>';
        el.lastElementChild.textContent = message;

        el.addEventListener('pointerenter', () => clearTimeout(Number(el.dataset.timer)));
        el.addEventListener('pointerleave', () => scheduleToast(el, 1200));
        el.addEventListener('click', () => dismissToast(el));

        toastHost.appendChild(el);
        scheduleToast(el, TOAST_LIFE);
    }

    document.addEventListener('acc:toast', e => toast(e.detail));

    /* ----------------------------------------------------------------------
       2. Навигация по разделам (табы + hash + история)
       ---------------------------------------------------------------------- */
    const nav = $('[data-nav]');
    const navItems = $$('.acc-nav__item');
    const pill = $('[data-pill]');
    const panels = $$('.panel');

    function movePill(item) {
        if (!pill || !item || window.innerWidth <= 1000) return;
        pill.style.setProperty('--pill-y', item.offsetTop + 'px');
        pill.style.height = item.offsetHeight + 'px';
        pill.style.opacity = '1';
    }

    function activate(name, push) {
        const item = navItems.find(b => b.dataset.tab === name);
        if (!item) return;

        navItems.forEach(b => b.classList.toggle('is-active', b === item));
        panels.forEach(p => p.classList.toggle('is-active', p.dataset.panel === name));
        movePill(item);

        // повторный запуск анимаций внутри открытой панели
        const panel = panels.find(p => p.dataset.panel === name);
        if (panel) {
            $$('.reveal', panel).forEach((el, i) => {
                el.classList.remove('is-in');
                el.style.setProperty('--i', i);
            });
            requestAnimationFrame(() => $$('.reveal', panel).forEach(el => el.classList.add('is-in')));
            runCounters(panel);
            runProgress(panel);
        }

        if (push) history.replaceState(null, '', '#' + name);
        // Lenis перехватывает скролл — если он есть, крутим через него
        if (window.lenis && typeof window.lenis.scrollTo === 'function') {
            window.lenis.scrollTo(0, { duration: 0.9 });
        } else {
            window.scrollTo(0, 0);
        }
    }

    navItems.forEach(b => b.addEventListener('click', () => activate(b.dataset.tab, true)));
    $$('[data-tab-link]').forEach(a => a.addEventListener('click', e => {
        e.preventDefault();
        activate(a.dataset.tabLink, true);
    }));

    const startTab = location.hash.replace('#', '');
    if (startTab && navItems.some(b => b.dataset.tab === startTab)) {
        activate(startTab, false);
    } else if (nav) {
        requestAnimationFrame(() => movePill(navItems[0]));
    }

    window.addEventListener('resize', () => {
        const active = navItems.find(b => b.classList.contains('is-active'));
        if (window.innerWidth <= 1000) {
            if (pill) pill.style.opacity = '0';
        } else {
            movePill(active);
        }
    });

    /* ----------------------------------------------------------------------
       3. Появление блоков при скролле
       ---------------------------------------------------------------------- */
    const io = 'IntersectionObserver' in window
        ? new IntersectionObserver((entries, obs) => {
            entries.forEach(en => {
                if (!en.isIntersecting) return;
                en.target.classList.add('is-in');
                obs.unobserve(en.target);
            });
        }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 })
        : null;

    // порядковый индекс для каскада (--i) — раньше проставлялся inline в шаблоне
    function stagger() {
        $$('.reveal').filter(el => !el.closest('.panel'))
            .forEach((el, i) => el.style.setProperty('--i', i));

        $$('.panel').forEach(panel =>
            $$('.reveal', panel).forEach((el, i) => el.style.setProperty('--i', i)));
    }
    stagger();

    function observeReveals(scope) {
        $$('.reveal', scope || document).forEach(el => {
            if (io) io.observe(el); else el.classList.add('is-in');
        });
    }
    observeReveals();

    /* ----------------------------------------------------------------------
       4. Счётчики
       ---------------------------------------------------------------------- */
    function animateNumber(el) {
        const target = parseFloat(String(el.dataset.count).replace(/\s/g, '')) || 0;
        if (REDUCED) { el.textContent = nf.format(target); return; }

        const dur = 1400;
        const t0 = performance.now();

        (function tick(now) {
            const p = clamp((now - t0) / dur, 0, 1);
            const eased = 1 - Math.pow(1 - p, 4);
            el.textContent = nf.format(Math.round(target * eased));
            if (p < 1) requestAnimationFrame(tick);
        })(t0);
    }

    function runCounters(scope) {
        $$('[data-count]', scope || document).forEach(el => {
            if (el.dataset.counted === '1') return;
            const start = () => { el.dataset.counted = '1'; animateNumber(el); };
            if (!io) return start();
            const once = new IntersectionObserver((en, obs) => {
                if (en[0].isIntersecting) { start(); obs.disconnect(); }
            }, { threshold: 0.4 });
            once.observe(el);
        });
    }
    runCounters();

    /* ----------------------------------------------------------------------
       5. Прогресс-бары
       ---------------------------------------------------------------------- */
    function runProgress(scope) {
        $$('[data-progress]', scope || document).forEach(bar => {
            const val = clamp(parseFloat(bar.dataset.progress) || 0, 0, 100);
            requestAnimationFrame(() => { bar.style.width = val + '%'; });
        });
    }
    setTimeout(runProgress, 120);

    /* ----------------------------------------------------------------------
       6. Спекулярный блик за курсором
       ---------------------------------------------------------------------- */
    if (!COARSE) {
        document.addEventListener('pointermove', e => {
            const card = e.target.closest('[data-shine]');
            if (!card) return;
            const r = card.getBoundingClientRect();
            card.style.setProperty('--mx', ((e.clientX - r.left) / r.width * 100) + '%');
            card.style.setProperty('--my', ((e.clientY - r.top) / r.height * 100) + '%');
        }, { passive: true });
    }

    /* ----------------------------------------------------------------------
       7. 3D-tilt
       ---------------------------------------------------------------------- */
    if (!COARSE && !REDUCED) {
        $$('[data-tilt]').forEach(card => {
            const max = parseFloat(card.dataset.tilt) || 6;
            let raf = null;

            card.addEventListener('pointermove', e => {
                if (raf) return;
                raf = requestAnimationFrame(() => {
                    raf = null;
                    const r = card.getBoundingClientRect();
                    const px = (e.clientX - r.left) / r.width - 0.5;
                    const py = (e.clientY - r.top) / r.height - 0.5;
                    card.style.setProperty('--ry', (px * max).toFixed(2) + 'deg');
                    card.style.setProperty('--rx', (-py * max).toFixed(2) + 'deg');
                });
            });

            card.addEventListener('pointerleave', () => {
                card.style.setProperty('--rx', '0deg');
                card.style.setProperty('--ry', '0deg');
            });
        });
    }

    /* ----------------------------------------------------------------------
       8. Магнитные кнопки + ripple
       ---------------------------------------------------------------------- */
    if (!COARSE && !REDUCED) {
        $$('[data-magnetic]').forEach(btn => {
            const power = 0.28;

            btn.addEventListener('pointermove', e => {
                const r = btn.getBoundingClientRect();
                btn.style.setProperty('--tx', ((e.clientX - r.left - r.width / 2) * power).toFixed(1) + 'px');
                btn.style.setProperty('--ty', ((e.clientY - r.top - r.height / 2) * power).toFixed(1) + 'px');
            });

            btn.addEventListener('pointerleave', () => {
                btn.style.setProperty('--tx', '0px');
                btn.style.setProperty('--ty', '0px');
            });
        });
    }

    document.addEventListener('pointerdown', e => {
        const btn = e.target.closest('.btn, .chip, .acc-nav__item');
        if (!btn || REDUCED) return;
        const r = btn.getBoundingClientRect();
        const size = Math.max(r.width, r.height);
        const ink = document.createElement('span');
        ink.className = 'ripple';
        ink.style.width = ink.style.height = size + 'px';
        ink.style.left = (e.clientX - r.left - size / 2) + 'px';
        ink.style.top = (e.clientY - r.top - size / 2) + 'px';
        btn.appendChild(ink);
        ink.addEventListener('animationend', () => ink.remove(), { once: true });
    });

    /* ----------------------------------------------------------------------
       9. Параллакс фоновых блобов
       ---------------------------------------------------------------------- */
    if (!COARSE && !REDUCED) {
        const blobs = $$('[data-depth]');
        let raf = null, mx = 0, my = 0;

        window.addEventListener('pointermove', e => {
            mx = (e.clientX / window.innerWidth - 0.5);
            my = (e.clientY / window.innerHeight - 0.5);
            if (raf) return;
            raf = requestAnimationFrame(() => {
                raf = null;
                blobs.forEach(b => {
                    const d = parseFloat(b.dataset.depth) || 0;
                    b.style.setProperty('--px', (mx * d).toFixed(1) + 'px');
                    b.style.setProperty('--py', (my * d).toFixed(1) + 'px');
                });
            });
        }, { passive: true });
    }

    /* ----------------------------------------------------------------------
       10. Обратный отсчёт до вылета
       ---------------------------------------------------------------------- */
    $$('[data-countdown]').forEach(box => {
        const target = new Date(box.dataset.countdown).getTime();
        if (isNaN(target)) return;

        const cells = {
            d: $('[data-cd="d"]', box),
            h: $('[data-cd="h"]', box),
            m: $('[data-cd="m"]', box),
            s: $('[data-cd="s"]', box)
        };

        const pad = n => String(n).padStart(2, '0');

        function set(el, val) {
            if (!el || el.textContent === val) return;
            el.textContent = val;
            if (REDUCED) return;
            el.animate(
                [{ transform: 'translateY(-6px)', opacity: 0.4 }, { transform: 'none', opacity: 1 }],
                { duration: 320, easing: 'cubic-bezier(.34,1.56,.64,1)' }
            );
        }

        (function tick() {
            let diff = Math.max(0, target - Date.now());
            const d = Math.floor(diff / 864e5); diff -= d * 864e5;
            const h = Math.floor(diff / 36e5); diff -= h * 36e5;
            const m = Math.floor(diff / 6e4); diff -= m * 6e4;
            const s = Math.floor(diff / 1e3);

            set(cells.d, pad(d));
            set(cells.h, pad(h));
            set(cells.m, pad(m));
            set(cells.s, pad(s));

            setTimeout(tick, 1000);
        })();
    });

    /* ----------------------------------------------------------------------
       11. Фильтр бронирований
       ---------------------------------------------------------------------- */
    const filters = $('[data-filters]');
    if (filters) {
        const cards = $$('[data-bookings] .booking');
        const empty = $('[data-empty]');

        filters.addEventListener('click', e => {
            const chip = e.target.closest('[data-filter]');
            if (!chip) return;

            $$('[data-filter]', filters).forEach(c => c.classList.toggle('is-active', c === chip));
            const f = chip.dataset.filter;
            let shown = 0;

            cards.forEach((card, i) => {
                const ok = f === 'all' || card.dataset.status === f;
                card.classList.toggle('is-hidden', !ok);
                if (ok) {
                    shown++;
                    card.style.setProperty('--i', i);
                    card.classList.remove('is-in');
                    requestAnimationFrame(() => card.classList.add('is-in'));
                }
            });

            if (empty) empty.hidden = shown > 0;
        });
    }

    /* ----------------------------------------------------------------------
       12. Обмен с сервером
       ---------------------------------------------------------------------- */
    function csrfToken() {
        const input = $('input[name="csrfmiddlewaretoken"]');
        if (input) return input.value;
        const m = document.cookie.match(/csrftoken=([^;]+)/);
        return m ? m[1] : '';
    }

    function postTo(url) {
        return fetch(url, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken(),
                'X-Requested-With': 'XMLHttpRequest'
            },
            credentials: 'same-origin'
        }).then(r => (r.ok ? r.json() : Promise.reject(r.status)));
    }

    /* ---- избранное: снять сердечко ---------------------------------------- */
    document.addEventListener('click', e => {
        const heart = e.target.closest('[data-unfav]');
        if (!heart || !heart.dataset.url) return;

        const card = heart.closest('.fav');
        const title = $('h3', card) ? $('h3', card).textContent.trim() : 'Тур';
        heart.disabled = true;

        postTo(heart.dataset.url)
            .then(data => {
                card.classList.add('is-removing');
                setTimeout(() => {
                    card.remove();
                    const counter = $('.acc-nav__item[data-tab="favorites"] .acc-nav__count');
                    if (counter) counter.textContent = data.total;
                    toast('«' + title + '» убран из избранного');
                }, 380);
            })
            .catch(() => {
                heart.disabled = false;
                toast('Не получилось — обновите страницу');
            });
    });

    /* ---- уведомления: «прочитать все» ------------------------------------- */
    const readAllForm = $('[data-read-all-form]');
    if (readAllForm) {
        readAllForm.addEventListener('submit', e => {
            e.preventDefault();
            const unread = $$('.note.is-unread');

            postTo(readAllForm.action)
                .then(() => {
                    unread.forEach((note, i) =>
                        setTimeout(() => note.classList.remove('is-unread'), i * 80));
                    const badge = $('.acc-nav__item[data-tab="notifications"] .acc-nav__count');
                    if (badge) badge.textContent = '0';
                    toast(unread.length ? 'Все уведомления прочитаны' : 'Новых уведомлений нет');
                })
                .catch(() => readAllForm.submit());   // без JS-ответа — обычная отправка
        });
    }

    /* ---- сообщения от Django (messages) показываем теми же тостами -------- */
    $$('.server-messages [data-message]').forEach((node, i) =>
        setTimeout(() => toast(node.textContent.trim()), 350 + i * 260));

    document.addEventListener('click', e => {
        const note = e.target.closest('[data-note]');
        if (note) note.classList.remove('is-unread');
    });

    /* ----------------------------------------------------------------------
       14. Загрузка документов
       ---------------------------------------------------------------------- */
    const dz = $('[data-dropzone]');
    if (dz) {
        const input = $('input[type="file"]', dz);
        const form = dz.closest('[data-upload-form]');

        ['dragenter', 'dragover'].forEach(ev =>
            dz.addEventListener(ev, e => { e.preventDefault(); dz.classList.add('is-over'); }));

        ['dragleave', 'drop'].forEach(ev =>
            dz.addEventListener(ev, e => { e.preventDefault(); dz.classList.remove('is-over'); }));

        // перетащили файл — кладём его в input и отправляем форму
        dz.addEventListener('drop', e => {
            const files = e.dataTransfer && e.dataTransfer.files;
            if (!files || !files.length || !input) return;
            input.files = files;
            toast('Загружаем: ' + files[0].name);
            if (form) form.submit();
        });

        if (input) {
            input.addEventListener('change', () => {
                if (!input.files.length) return;
                toast('Загружаем: ' + input.files[0].name);
                if (form) form.submit();
            });
        }

        // кнопка «Загрузить документ» в шапке раздела
        const picker = $('[data-pick-file]');
        if (picker && input) picker.addEventListener('click', () => input.click());
    }

    /* ----------------------------------------------------------------------
       15. Подтверждения, тосты, переключатели
       ---------------------------------------------------------------------- */

    // data-confirm на кнопке — спросить перед действием
    document.addEventListener('click', e => {
        const el = e.target.closest('[data-confirm]');
        if (!el || el.tagName === 'FORM') return;
        if (!confirm(el.dataset.confirm)) {
            e.preventDefault();
            e.stopImmediatePropagation();
        }
    }, true);

    // data-confirm на форме — спросить перед отправкой
    $$('form[data-confirm]').forEach(form => {
        form.addEventListener('submit', e => {
            if (!confirm(form.dataset.confirm)) e.preventDefault();
        });
    });

    document.addEventListener('click', e => {
        const el = e.target.closest('[data-toast]');
        if (el) toast(el.dataset.toast);
    });

    // переключатели живут внутри формы — напоминаем нажать «Сохранить»
    $$('.switch input').forEach(input => {
        input.addEventListener('change', () => {
            const form = input.closest('form');
            if (!form) return;
            const save = $('button[type="submit"]', form);
            if (save) {
                save.classList.add('btn--nudge');
                setTimeout(() => save.classList.remove('btn--nudge'), 900);
            }
        });
    });

    /* ----------------------------------------------------------------------
       16. Сохранение профиля без перезагрузки (если бэкенд ещё не готов)
       ---------------------------------------------------------------------- */
    const profileForm = $('.panel[data-panel="settings"] form');
    if (profileForm && !profileForm.getAttribute('action')) {
        profileForm.addEventListener('submit', e => {
            e.preventDefault();
            toast('Изменения сохранены');
        });
    }
})();
