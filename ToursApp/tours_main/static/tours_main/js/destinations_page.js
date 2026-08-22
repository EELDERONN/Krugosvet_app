/* ==========================================================
   КРУГОСВЕТ — СТРАНИЦА «НАПРАВЛЕНИЯ»
   Файл: tours_main/static/tours_main/js/destinations_page.js

   1. плавный переход по якорям (через Lenis, если он есть);
   2. подсветка активной страны в боковом меню + бегунок;
   3. декор у заголовков: сакура, шары, фонарики, снежинки…;
   4. лёгкий параллакс постеров;
   5. появление блоков при прокрутке;
   6. полоса прогресса чтения.

   Всё, что двигается, ставится на паузу, когда секция ушла
   с экрана: девять стран с частицами одновременно — это
   лишняя нагрузка на слабых ноутбуках.
========================================================== */

(function () {
    "use strict";

    var page = document.querySelector(".dst");
    if (!page) return;

    var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    var sections = Array.prototype.slice.call(
        document.querySelectorAll(".dst-country")
    );
    var navItems = Array.prototype.slice.call(
        document.querySelectorAll(".dst-nav__item")
    );
    var pill = document.querySelector(".dst-nav__pill");


    /* ==========================================================
       1. ПЛАВНЫЙ ПЕРЕХОД ПО ЯКОРЯМ
    ========================================================== */

    var HEADER_OFFSET = -118;   // высота шапки + воздух

    function scrollToId(id) {

        var target = document.getElementById(id);
        if (!target) return;

        if (window.lenis && typeof window.lenis.scrollTo === "function") {
            window.lenis.scrollTo(target, {
                offset:   HEADER_OFFSET,
                duration: 1.25
            });
            return;
        }

        var top = target.getBoundingClientRect().top + window.pageYOffset
                  + HEADER_OFFSET;

        window.scrollTo({
            top:      top,
            behavior: reduce ? "auto" : "smooth"
        });
    }

    document.addEventListener("click", function (event) {

        var link = event.target.closest && event.target.closest("[data-jump]");
        if (!link) return;

        event.preventDefault();
        scrollToId(link.getAttribute("data-jump"));
    });


    /* ==========================================================
       2. АКТИВНАЯ СТРАНА В МЕНЮ
    ========================================================== */

    function movePill(item) {

        if (!pill || !item || window.innerWidth <= 980) return;

        pill.style.height    = item.offsetHeight + "px";
        pill.style.transform = "translateY(" + item.offsetTop + "px)";
        pill.style.opacity   = "1";
    }

    function setActive(slug) {

        var current = null;

        navItems.forEach(function (item) {

            var mine = item.getAttribute("data-jump") === slug;
            item.classList.toggle("is-active", mine);

            if (mine) current = item;
        });

        movePill(current);
    }

    if (sections.length) {

        // секция считается активной, когда пересекает середину экрана
        var spy = new IntersectionObserver(function (entries) {

            entries.forEach(function (entry) {
                if (entry.isIntersecting) setActive(entry.target.id);
            });

        }, { rootMargin: "-45% 0px -50% 0px", threshold: 0 });

        sections.forEach(function (section) { spy.observe(section); });

        setActive(sections[0].id);
    }

    window.addEventListener("resize", function () {
        var active = document.querySelector(".dst-nav__item.is-active");
        if (active) movePill(active);
    });


    /* ==========================================================
       3. ДЕКОР У ЗАГОЛОВКОВ
    ========================================================== */

    /* тип декора -> как ведёт себя частица */

    var DECOR = {
        sakura:     { move: "fall",  count: 16, size: [9, 17],  peak: [.55, .95] },
        petal:      { move: "fall",  count: 14, size: [9, 16],  peak: [.5, .9]   },
        leaf:       { move: "fall",  count: 13, size: [10, 18], peak: [.45, .85] },
        frangipani: { move: "fall",  count: 13, size: [11, 19], peak: [.5, .9]   },
        snow:       { move: "fall",  count: 22, size: [4, 9],   peak: [.5, 1]    },
        bubble:     { move: "rise",  count: 18, size: [6, 14],  peak: [.4, .8]   },
        lantern:    { move: "rise",  count: 11, size: [12, 21], peak: [.55, .95] },
        balloon:    { move: "rise",  count: 9,  size: [14, 26], peak: [.6, 1]    },
        star:       { move: "spark", count: 20, size: [7, 14],  peak: [.5, 1]    }
    };

    function rand(min, max) {
        return min + Math.random() * (max - min);
    }

    function buildDecor(box) {

        if (reduce || box.dataset.filled) return;

        var kind = box.getAttribute("data-decor");
        var cfg  = DECOR[kind];
        if (!cfg) return;

        box.dataset.filled = "1";

        var batch = document.createDocumentFragment();

        for (var i = 0; i < cfg.count; i++) {

            var dot = document.createElement("i");

            dot.className = "dst-particle dst-p--" + cfg.move +
                            " dst-p--" + kind;

            var size  = rand(cfg.size[0], cfg.size[1]);
            var drift = rand(-60, 90);

            dot.style.cssText =
                "--x:"     + rand(0, 96).toFixed(1) + "%;" +
                "--size:"  + size.toFixed(1) + "px;" +
                "--dur:"   + rand(6.5, 15).toFixed(2) + "s;" +
                "--delay:" + (-rand(0, 14)).toFixed(2) + "s;" +
                "--drift:" + drift.toFixed(0) + "px;" +
                "--spin:"  + rand(-420, 420).toFixed(0) + "deg;" +
                "--peak:"  + rand(cfg.peak[0], cfg.peak[1]).toFixed(2) + ";" +
                "--y:"     + rand(10, 150).toFixed(0) + "px;";

            batch.appendChild(dot);
        }

        box.appendChild(batch);
    }

    var decorBoxes = Array.prototype.slice.call(
        document.querySelectorAll(".dst-decor")
    );

    if (decorBoxes.length && !reduce) {

        var decorWatch = new IntersectionObserver(function (entries) {

            entries.forEach(function (entry) {

                if (entry.isIntersecting) {
                    buildDecor(entry.target);
                    entry.target.classList.add("is-live");
                } else {
                    // ушло с экрана — анимации замирают
                    entry.target.classList.remove("is-live");
                }
            });

        }, { rootMargin: "180px 0px 180px 0px", threshold: 0 });

        decorBoxes.forEach(function (box) { decorWatch.observe(box); });
    }


    /* ==========================================================
       4. ПАРАЛЛАКС + 5. ПОЯВЛЕНИЕ + 6. ПРОГРЕСС
    ========================================================== */

    var shots = Array.prototype.slice.call(
        document.querySelectorAll(".dst-shot")
    );
    var bar = document.querySelector(".dst-progress i");

    var visibleShots = [];

    if (shots.length && !reduce) {

        var shotWatch = new IntersectionObserver(function (entries) {

            entries.forEach(function (entry) {

                var index = visibleShots.indexOf(entry.target);

                if (entry.isIntersecting && index === -1) {
                    visibleShots.push(entry.target);
                } else if (!entry.isIntersecting && index !== -1) {
                    visibleShots.splice(index, 1);
                }
            });

        }, { rootMargin: "120px 0px 120px 0px", threshold: 0 });

        shots.forEach(function (shot) { shotWatch.observe(shot); });
    }

    var ticking = false;

    function onFrame() {

        ticking = false;

        var vh = window.innerHeight || 1;

        // параллакс: картинка чуть отстаёт от прокрутки
        for (var i = 0; i < visibleShots.length; i++) {

            var shot = visibleShots[i];
            var box  = shot.getBoundingClientRect();
            var img  = shot.querySelector("img");
            if (!img) continue;

            // -1 внизу экрана, +1 наверху
            var progress = (vh / 2 - (box.top + box.height / 2)) / vh;
            img.style.setProperty("--shift", (progress * 14).toFixed(1));
        }

        // полоса прогресса чтения
        if (bar) {

            var doc   = document.documentElement;
            var total = doc.scrollHeight - vh;
            var done  = total > 0 ? window.pageYOffset / total : 0;

            bar.style.width = Math.max(0, Math.min(1, done)) * 100 + "%";
        }
    }

    function requestFrame() {
        if (ticking) return;
        ticking = true;
        window.requestAnimationFrame(onFrame);
    }

    window.addEventListener("scroll", requestFrame, { passive: true });
    window.addEventListener("resize", requestFrame);

    // Lenis крутит страницу сам и обычный scroll иногда не стреляет
    if (window.lenis && typeof window.lenis.on === "function") {
        window.lenis.on("scroll", requestFrame);
    }

    requestFrame();


    /* ---------- появление блоков ---------- */

    var reveals = Array.prototype.slice.call(
        document.querySelectorAll(".dst-reveal")
    );

    if (reveals.length) {

        if (reduce) {

            reveals.forEach(function (node) { node.classList.add("is-in"); });

        } else {

            var revealWatch = new IntersectionObserver(function (entries, obs) {

                entries.forEach(function (entry) {
                    if (!entry.isIntersecting) return;
                    entry.target.classList.add("is-in");
                    obs.unobserve(entry.target);
                });

            }, { rootMargin: "0px 0px -12% 0px", threshold: .08 });

            reveals.forEach(function (node) { revealWatch.observe(node); });
        }
    }


    /* ---------- если пришли по ссылке с #страной ---------- */

    if (window.location.hash.length > 1) {

        var wanted = window.location.hash.slice(1);

        window.setTimeout(function () { scrollToId(wanted); }, 260);
    }

})();
