/* ==========================================================================
   КРУГОСВЕТ — КАТАЛОГ ТУРОВ
   Файл: tours_main/static/tours_main/js/tours_filter.js

   Что здесь живёт:

   1.  Живой фильтр (без перезагрузки страницы)
   2.  Двойной ползунок цены
   3.  Сортировка
   4.  Счётчик найденного + пустой экран
   5.  Появление карточек при скролле
   6.  Наведение на карточку: она подрастает и расталкивает соседей
   7.  Синхронизация фильтра со ссылкой (можно скинуть другу)
   8.  Свои выпадающие списки вместо системного <select>

   Зависимостей нет. Карточки НЕ пересоздаются — они только прячутся,
   поэтому popup.js и favorites.js продолжают работать как работали.
   ========================================================================== */

(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', init);

    function init() {

        const panel = document.getElementById('tourFilter');
        const results = document.getElementById('toursResults');
        const empty = document.getElementById('toursEmpty');

        if (!panel || !results) return;

        const cards = Array.from(results.querySelectorAll('[data-tour]'));

        /* ------------------------------------------------------------------
           ЭЛЕМЕНТЫ УПРАВЛЕНИЯ
        ------------------------------------------------------------------ */

        const searchBox = panel.querySelector('.fsearch');
        const searchInput = panel.querySelector('[data-f-search]');
        const searchClear = panel.querySelector('[data-search-clear]');

        const countryBoxes = Array.from(panel.querySelectorAll('[data-f-country]'));
        const foodBoxes = Array.from(panel.querySelectorAll('[data-f-food]'));
        const nightRadios = Array.from(panel.querySelectorAll('[data-f-nights]'));

        const departureSelect = panel.querySelector('[data-f-departure]');
        const hotSwitch = panel.querySelector('[data-f-hot]');

        const rangeWrap = panel.querySelector('[data-range]');
        const rangeMin = panel.querySelector('[data-range-min]');
        const rangeMax = panel.querySelector('[data-range-max]');
        const rangeFill = panel.querySelector('[data-range-fill]');
        const priceLabel = panel.querySelector('[data-price-label]');
        const rangeFloor = panel.querySelector('[data-range-floor]');
        const rangeCeil = panel.querySelector('[data-range-ceil]');

        const sortSelect = document.querySelector('[data-f-sort]');

        const applyBtn = panel.querySelector('[data-filter-apply]');
        const applyLabel = panel.querySelector('[data-apply-label]');
        const resetBtns = Array.from(document.querySelectorAll('[data-filter-reset]'));
        const toggleBtn = panel.querySelector('[data-filter-toggle]');

        const counters = Array.from(document.querySelectorAll('[data-count]'));
        const counterWords = Array.from(document.querySelectorAll('[data-count-word]'));

        /* сюда складываем функции обновления кастомных выпадашек */
        const dropSyncs = [];

        const PRICE_MIN = Number(panel.dataset.priceMin || 0);
        const PRICE_MAX = Number(panel.dataset.priceMax || 0);

        /* ------------------------------------------------------------------
           МЕЛОЧИ
        ------------------------------------------------------------------ */

        const money = n => Number(n).toLocaleString('ru-RU');

        /** «1 тур», «2 тура», «7 туров» */
        function tourWord(n) {
            const ten = n % 10;
            const hundred = n % 100;

            if (ten === 1 && hundred !== 11) return 'тур';
            if (ten >= 2 && ten <= 4 && (hundred < 12 || hundred > 14)) return 'тура';
            return 'туров';
        }

        /* Пока на карточке висит transform, браузер держит её отдельным слоем
           и текст выглядит подмыленным. Как только всё доехало — снимаем
           transform совсем, и шрифты снова рисуются идеально резко. */

        function unsettleAll() {
            cards.forEach(card => card.classList.remove('is-settled'));
        }

        function settleAll() {
            cards.forEach(card => {
                if (card.hidden) return;
                if (!card.classList.contains('is-in')) return;
                if (card.classList.contains('is-hovered')) return;

                const shift = parseFloat(card.style.getPropertyValue('--shift')) || 0;
                if (shift !== 0) return;

                card.classList.add('is-settled');
            });
        }

        function debounce(fn, wait) {
            let timer = null;
            return function () {
                clearTimeout(timer);
                timer = setTimeout(fn, wait);
            };
        }

        function scrollToResults() {
            const top = results.getBoundingClientRect().top + window.pageYOffset - 110;

            /* на сайте включён Lenis — если он есть, скроллим через него.
               try/catch на случай, если библиотека не подгрузилась */
            try {
                if (typeof lenis !== 'undefined' && lenis &&
                    typeof lenis.scrollTo === 'function') {
                    lenis.scrollTo(top, { duration: 1.1 });
                    return;
                }
            } catch (e) { /* Lenis недоступен — скроллим обычным способом */ }

            window.scrollTo({ top: top, behavior: 'smooth' });
        }

        /* ------------------------------------------------------------------
           1. ПОЛЗУНОК ЦЕНЫ
        ------------------------------------------------------------------ */

        function clampRange(changed) {
            let lo = Number(rangeMin.value);
            let hi = Number(rangeMax.value);

            if (lo > hi) {
                if (changed === 'min') {
                    lo = hi;
                    rangeMin.value = lo;
                } else {
                    hi = lo;
                    rangeMax.value = hi;
                }
            }
            return { lo: lo, hi: hi };
        }

        function paintRange(changed) {
            if (!rangeMin || !rangeMax) return { lo: 0, hi: Infinity };

            const bounds = clampRange(changed);
            const span = (PRICE_MAX - PRICE_MIN) || 1;

            const left = ((bounds.lo - PRICE_MIN) / span) * 100;
            const right = 100 - ((bounds.hi - PRICE_MIN) / span) * 100;

            rangeFill.style.left = left + '%';
            rangeFill.style.right = right + '%';

            /* если оба «бегунка» уехали вправо — верхний должен быть тот,
               за который реально можно схватиться */
            rangeWrap.classList.toggle('is-min-top', left > 65);

            if (priceLabel) {
                priceLabel.textContent = money(bounds.lo) + ' — ' + money(bounds.hi);
            }

            return bounds;
        }

        if (rangeFloor) rangeFloor.textContent = money(PRICE_MIN) + ' ₽';
        if (rangeCeil) rangeCeil.textContent = money(PRICE_MAX) + ' ₽';

        /* ------------------------------------------------------------------
           2. СБОР СОСТОЯНИЯ ФИЛЬТРА
        ------------------------------------------------------------------ */

        function readState() {
            const bounds = paintRange();

            const nightsValue = (nightRadios.find(r => r.checked) || {}).value || '';
            let nightsFrom = 0;
            let nightsTo = 999;

            if (nightsValue) {
                const parts = nightsValue.split('-');
                nightsFrom = Number(parts[0]) || 0;
                nightsTo = Number(parts[1]) || 999;
            }

            return {
                query: (searchInput ? searchInput.value : '').trim().toLowerCase(),
                countries: countryBoxes.filter(b => b.checked).map(b => b.value),
                foods: foodBoxes.filter(b => b.checked).map(b => b.value.toLowerCase()),
                priceFrom: bounds.lo,
                priceTo: bounds.hi,
                nightsFrom: nightsFrom,
                nightsTo: nightsTo,
                nightsValue: nightsValue,
                departure: departureSelect ? departureSelect.value : '',
                hotOnly: hotSwitch ? hotSwitch.checked : false,
                sort: sortSelect ? sortSelect.value : 'price-asc'
            };
        }

        function matches(card, state) {

            if (state.query && card.dataset.search.indexOf(state.query) === -1) {
                return false;
            }

            if (state.countries.length &&
                state.countries.indexOf(card.dataset.country) === -1) {
                return false;
            }

            if (state.foods.length &&
                state.foods.indexOf((card.dataset.food || '').toLowerCase()) === -1) {
                return false;
            }

            const price = Number(card.dataset.price);
            if (price < state.priceFrom || price > state.priceTo) return false;

            const nights = Number(card.dataset.nights);
            if (nights < state.nightsFrom || nights > state.nightsTo) return false;

            if (state.departure && card.dataset.departure !== state.departure) return false;

            if (state.hotOnly && card.dataset.hot !== '1') return false;

            return true;
        }

        /* ------------------------------------------------------------------
           3. СОРТИРОВКА
        ------------------------------------------------------------------ */

        function sortCards(list, mode) {
            const copy = list.slice();

            const byPrice = c => Number(c.dataset.price);
            const byRating = c => parseFloat(c.dataset.rating) || 0;
            const byNights = c => Number(c.dataset.nights);

            if (mode === 'price-desc') copy.sort((a, b) => byPrice(b) - byPrice(a));
            else if (mode === 'rating-desc') copy.sort((a, b) => byRating(b) - byRating(a));
            else if (mode === 'nights-desc') copy.sort((a, b) => byNights(b) - byNights(a));
            else copy.sort((a, b) => byPrice(a) - byPrice(b));

            copy.forEach((card, i) => { card.style.order = String(i); });

            return copy;
        }

        /* ------------------------------------------------------------------
           4. ПРИМЕНЕНИЕ ФИЛЬТРА
        ------------------------------------------------------------------ */

        let visibleCards = [];

        function applyFilter(options) {
            const silent = options && options.silent;
            const state = readState();

            /* --- 1. замораживаем анимации и запоминаем, кто где стоял --- */

            cards.forEach(card => {
                card.classList.add('no-anim');
                card.classList.remove('is-hovered');
                card.classList.remove('is-settled');
                card.style.setProperty('--shift', '0px');
            });

            void results.offsetWidth;

            const before = new Map();
            cards.forEach(card => {
                if (!card.hidden) before.set(card, card.getBoundingClientRect().top);
            });

            /* --- 2. собственно фильтрация и сортировка --- */

            const shown = [];
            const revealed = [];

            cards.forEach(card => {
                const ok = matches(card, state);
                const wasHidden = card.hidden;

                card.hidden = !ok;

                if (ok) {
                    shown.push(card);
                    if (wasHidden) revealed.push(card);
                }
            });

            visibleCards = sortCards(shown, state.sort);

            /* вернувшиеся карточки прячем «в ноль», чтобы потом красиво вплыли */
            revealed.forEach(card => card.classList.remove('is-in'));

            /* --- 3. FLIP: сдвигаем карточки на старое место... --- */

            void results.offsetWidth;

            const moved = [];

            visibleCards.forEach(card => {
                if (!before.has(card)) return;

                const delta = before.get(card) - card.getBoundingClientRect().top;

                if (Math.abs(delta) > 1) {
                    card.style.setProperty('--shift', delta + 'px');
                    moved.push(card);
                }
            });

            void results.offsetWidth;

            /* --- 4. ...и отпускаем — карточки сами переедут на новое --- */

            cards.forEach(card => card.classList.remove('no-anim'));

            requestAnimationFrame(() => {

                moved.forEach(card => card.style.setProperty('--shift', '0px'));

                revealed.forEach((card, i) => {
                    setTimeout(() => card.classList.add('is-in'), 60 + i * 65);
                });

                settleSoon();

            });

            /* счётчики */
            const total = shown.length;

            counters.forEach(el => { el.textContent = total; });
            counterWords.forEach(el => { el.textContent = tourWord(total); });

            if (applyLabel) {
                applyLabel.textContent = total
                    ? 'Показать ' + total + ' ' + tourWord(total)
                    : 'Ничего не найдено';
            }

            if (applyBtn) applyBtn.disabled = total === 0;

            if (empty) empty.hidden = total !== 0;

            if (!silent) syncUrl(state);
        }

        const applySoon = debounce(applyFilter, 200);
        const settleSoon = debounce(settleAll, 650);

        /* ------------------------------------------------------------------
           5. ССЫЛКА С ФИЛЬТРОМ
        ------------------------------------------------------------------ */

        function syncUrl(state) {
            const params = new URLSearchParams();

            if (state.query) params.set('q', state.query);
            if (state.countries.length) params.set('c', state.countries.join(','));
            if (state.foods.length) params.set('f', state.foods.join(','));
            if (state.priceFrom > PRICE_MIN) params.set('pmin', state.priceFrom);
            if (state.priceTo < PRICE_MAX) params.set('pmax', state.priceTo);
            if (state.nightsValue) params.set('n', state.nightsValue);
            if (state.departure) params.set('dep', state.departure);
            if (state.hotOnly) params.set('hot', '1');
            if (state.sort !== 'price-asc') params.set('sort', state.sort);

            const search = params.toString();

            history.replaceState(
                null, '',
                location.pathname + (search ? '?' + search : '')
            );
        }

        function restoreFromUrl() {
            const params = new URLSearchParams(location.search);
            if (!params.toString()) return;

            if (searchInput && params.get('q')) {
                searchInput.value = params.get('q');
            }

            const countries = (params.get('c') || '').split(',').filter(Boolean);
            countryBoxes.forEach(b => { b.checked = countries.indexOf(b.value) !== -1; });

            const foods = (params.get('f') || '').split(',').filter(Boolean);
            foodBoxes.forEach(b => {
                b.checked = foods.indexOf(b.value.toLowerCase()) !== -1;
            });

            if (rangeMin && params.get('pmin')) rangeMin.value = params.get('pmin');
            if (rangeMax && params.get('pmax')) rangeMax.value = params.get('pmax');

            const nights = params.get('n');
            if (nights) {
                const radio = nightRadios.find(r => r.value === nights);
                if (radio) radio.checked = true;
            }

            if (departureSelect && params.get('dep')) {
                departureSelect.value = params.get('dep');
            }

            if (hotSwitch) hotSwitch.checked = params.get('hot') === '1';

            if (sortSelect && params.get('sort')) sortSelect.value = params.get('sort');
        }

        /* ------------------------------------------------------------------
           6. ПОДПИСКИ
        ------------------------------------------------------------------ */

        if (searchInput) {
            searchInput.addEventListener('input', () => {
                if (searchBox) {
                    searchBox.classList.toggle('is-filled', searchInput.value !== '');
                }
                applySoon();
            });
        }

        if (searchClear) {
            searchClear.addEventListener('click', () => {
                searchInput.value = '';
                searchBox.classList.remove('is-filled');
                applyFilter();
                searchInput.focus();
            });
        }

        countryBoxes.concat(foodBoxes).forEach(box => {
            box.addEventListener('change', () => applyFilter());
        });

        nightRadios.forEach(radio => {
            radio.addEventListener('change', () => applyFilter());
        });

        if (departureSelect) {
            departureSelect.addEventListener('change', () => applyFilter());
        }

        if (hotSwitch) {
            hotSwitch.addEventListener('change', () => applyFilter());
        }

        if (sortSelect) {
            sortSelect.addEventListener('change', () => applyFilter());
        }

        if (rangeMin && rangeMax) {

            rangeMin.addEventListener('input', () => { paintRange('min'); applySoon(); });
            rangeMax.addEventListener('input', () => { paintRange('max'); applySoon(); });

            /* мгновенный отклик, когда бегунок отпустили */
            [rangeMin, rangeMax].forEach(input => {
                input.addEventListener('change', () => applyFilter());
            });
        }

        if (applyBtn) {
            applyBtn.addEventListener('click', () => {
                applyFilter();
                scrollToResults();

                if (window.innerWidth <= 1250) {
                    panel.classList.remove('is-open');
                }
            });
        }

        resetBtns.forEach(btn => {
            btn.addEventListener('click', () => {

                if (searchInput) searchInput.value = '';
                if (searchBox) searchBox.classList.remove('is-filled');

                countryBoxes.forEach(b => { b.checked = false; });
                foodBoxes.forEach(b => { b.checked = false; });

                if (nightRadios.length) nightRadios[0].checked = true;

                if (rangeMin) rangeMin.value = PRICE_MIN;
                if (rangeMax) rangeMax.value = PRICE_MAX;

                if (departureSelect) departureSelect.value = '';
                if (hotSwitch) hotSwitch.checked = false;
                if (sortSelect) sortSelect.value = 'price-asc';

                paintRange();
                dropSyncs.forEach(sync => sync());
                applyFilter();
            });
        });

        if (toggleBtn) {
            toggleBtn.addEventListener('click', () => {
                panel.classList.toggle('is-open');
            });
        }

        /* ------------------------------------------------------------------
           7. ПОЯВЛЕНИЕ КАРТОЧЕК ПРИ СКРОЛЛЕ
        ------------------------------------------------------------------ */

        if ('IntersectionObserver' in window) {

            const io = new IntersectionObserver((entries, obs) => {

                entries.forEach((entry, i) => {
                    if (!entry.isIntersecting) return;

                    setTimeout(() => {
                        entry.target.classList.add('is-in');
                        settleSoon();
                    }, i * 70);

                    obs.unobserve(entry.target);
                });

            }, { rootMargin: '0px 0px -8% 0px', threshold: .12 });

            cards.forEach(card => io.observe(card));

        } else {
            cards.forEach(card => card.classList.add('is-in'));
            settleSoon();
        }

        /* ------------------------------------------------------------------
           8. НАВЕДЕНИЕ: КАРТОЧКА РАСТЁТ И РАСТАЛКИВАЕТ СОСЕДЕЙ
           Соседей сверху уводим вверх, снизу — вниз, потом всё возвращается.
        ------------------------------------------------------------------ */

        const canHover = window.matchMedia('(hover: hover) and (pointer: fine)').matches;
        const calmMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

        if (canHover && !calmMotion) {

            const PUSH = 15;   // на сколько пикселей разъезжаются соседи

            function clearShifts() {
                cards.forEach(card => card.style.setProperty('--shift', '0px'));
            }

            cards.forEach(card => {

                card.addEventListener('mouseenter', () => {
                    if (card.hidden || window.innerWidth <= 950) return;

                    unsettleAll();
                    card.classList.add('is-hovered');

                    const index = visibleCards.indexOf(card);
                    if (index === -1) return;

                    visibleCards.forEach((other, i) => {
                        if (other === card) {
                            other.style.setProperty('--shift', '0px');
                        } else if (i < index) {
                            other.style.setProperty('--shift', '-' + PUSH + 'px');
                        } else {
                            other.style.setProperty('--shift', PUSH + 'px');
                        }
                    });
                });

                card.addEventListener('mouseleave', () => {
                    card.classList.remove('is-hovered');
                    clearShifts();
                    settleSoon();
                });

            });

            /* если курсор ушёл со списка целиком — на всякий случай возвращаем всё */
            results.addEventListener('mouseleave', () => {
                cards.forEach(card => card.classList.remove('is-hovered'));
                clearShifts();
                settleSoon();
            });
        }

        /* ------------------------------------------------------------------
           9. КРАСИВЫЕ ВЫПАДАЮЩИЕ СПИСКИ
           Родной <select> нельзя оформить — браузер рисует его список сам.
           Поэтому строим свой список рядом, а настоящий select оставляем
           спрятанным: он по-прежнему хранит значение и шлёт событие change,
           так что вся остальная логика фильтра ничего не замечает.
        ------------------------------------------------------------------ */

        function makeDropdown(select) {
            if (!select) return;

            const wrap = select.closest('.fselect');
            if (!wrap) return;

            const options = Array.from(select.options);

            wrap.classList.add('is-custom');

            const drop = document.createElement('div');
            drop.className = 'fdrop';

            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'fdrop__btn';
            button.setAttribute('aria-haspopup', 'listbox');
            button.setAttribute('aria-expanded', 'false');

            const label = document.createElement('span');
            label.className = 'fdrop__label';

            button.appendChild(label);
            button.insertAdjacentHTML('beforeend',
                '<svg class="fdrop__chevron" viewBox="0 0 24 24" fill="none" aria-hidden="true">' +
                '<path d="M6 9.5l6 6 6-6" stroke="currentColor" stroke-width="2.2" ' +
                'stroke-linecap="round" stroke-linejoin="round"/></svg>');

            const list = document.createElement('div');
            list.className = 'fdrop__list';
            list.setAttribute('role', 'listbox');

            const items = options.map(option => {
                const item = document.createElement('button');
                item.type = 'button';
                item.className = 'fdrop__item';
                item.setAttribute('role', 'option');
                item.dataset.value = option.value;

                item.insertAdjacentHTML('beforeend',
                    '<span>' + option.textContent.trim() + '</span>' +
                    '<svg viewBox="0 0 24 24" fill="none" aria-hidden="true">' +
                    '<path d="M5 12.5l4.5 4.5L19 7.5" stroke="currentColor" ' +
                    'stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>');

                item.addEventListener('click', () => {
                    select.value = option.value;
                    select.dispatchEvent(new Event('change', { bubbles: true }));
                    sync();
                    close();
                    button.focus();
                });

                list.appendChild(item);
                return item;
            });

            drop.appendChild(button);
            drop.appendChild(list);
            wrap.appendChild(drop);

            function sync() {
                const current = options.find(o => o.value === select.value) || options[0];
                label.textContent = current ? current.textContent.trim() : '';

                items.forEach(item => {
                    item.classList.toggle('is-active', item.dataset.value === select.value);
                });
            }

            function open() {
                document.querySelectorAll('.fdrop.is-open').forEach(other => {
                    if (other !== drop) other.classList.remove('is-open');
                });

                drop.classList.add('is-open');
                button.setAttribute('aria-expanded', 'true');
            }

            function close() {
                drop.classList.remove('is-open');
                button.setAttribute('aria-expanded', 'false');
            }

            button.addEventListener('click', e => {
                e.stopPropagation();
                drop.classList.contains('is-open') ? close() : open();
            });

            button.addEventListener('keydown', e => {
                if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
                    e.preventDefault();
                    open();
                    const active = list.querySelector('.is-active') || items[0];
                    if (active) active.focus();
                }
            });

            list.addEventListener('keydown', e => {
                const focused = items.indexOf(document.activeElement);

                if (e.key === 'Escape') {
                    close();
                    button.focus();
                }

                if (e.key === 'ArrowDown' && focused > -1) {
                    e.preventDefault();
                    (items[focused + 1] || items[0]).focus();
                }

                if (e.key === 'ArrowUp' && focused > -1) {
                    e.preventDefault();
                    (items[focused - 1] || items[items.length - 1]).focus();
                }
            });

            document.addEventListener('click', e => {
                if (!drop.contains(e.target)) close();
            });

            /* страница скроллится — список не должен «висеть» отдельно */
            window.addEventListener('scroll', () => {
                if (drop.classList.contains('is-open')) close();
            }, { passive: true });

            dropSyncs.push(sync);
            sync();
        }

        /* ------------------------------------------------------------------
           10. СТАРТ
        ------------------------------------------------------------------ */

        restoreFromUrl();

        makeDropdown(sortSelect);
        makeDropdown(departureSelect);

        if (searchBox && searchInput && searchInput.value) {
            searchBox.classList.add('is-filled');
        }

        paintRange();
        applyFilter({ silent: true });
    }

})();
