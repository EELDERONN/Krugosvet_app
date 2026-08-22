/* ==========================================================
   КРУГОСВЕТ — ПЕРЕКЛЮЧЕНИЕ ТЕМЫ
   Файл: tours_main/static/tours_main/js/theme.js
   Подключается в конце <body> в base.html.

   Что здесь происходит:
     1. запоминаем выбор в localStorage;
     2. по клику от кнопки расходится размытая волна;
     3. вместе с волной тема раскрывается кругом (View Transitions),
        а в браузерах без них цвета просто плавно перетекают;
     4. в шапку насыпаются мерцающие звёзды — они видны только ночью.
========================================================== */

(function () {
    "use strict";

    var KEY        = "krugosvet-theme";
    var root       = document.documentElement;
    var reduce     = window.matchMedia("(prefers-reduced-motion: reduce)");
    var systemDark = window.matchMedia("(prefers-color-scheme: dark)");

    var busy = false;   // защита от «долбёжки» по кнопке


    /* ---------- сохранение выбора ---------- */

    function readTheme() {
        try { return localStorage.getItem(KEY); } catch (e) { return null; }
    }

    function saveTheme(value) {
        try { localStorage.setItem(KEY, value); } catch (e) { /* приватный режим */ }
    }


    /* ---------- применение темы ---------- */

    function applyTheme(theme) {

        root.setAttribute("data-theme", theme);

        var isDark  = theme === "dark";
        var buttons = document.querySelectorAll(".theme-toggle");

        for (var i = 0; i < buttons.length; i++) {
            buttons[i].setAttribute("aria-checked", String(isDark));
            buttons[i].setAttribute(
                "aria-label",
                isDark ? "Включить светлую тему" : "Включить тёмную тему"
            );
        }

        var meta = document.querySelector('meta[name="theme-color"]');
        if (meta) {
            meta.setAttribute(
                "content",
                getComputedStyle(root).getPropertyValue("--bg").trim() || "#f7fbff"
            );
        }
    }


    /* ==========================================================
       ВОЛНА
       Три кольца разной толщины + мягкий «вздох» в центре.
       Всё размыто фильтром, поэтому выглядит как звуковая волна,
       а не как чёткий круг.
    ========================================================== */

    function radiusFrom(x, y) {
        return Math.hypot(
            Math.max(x, window.innerWidth  - x),
            Math.max(y, window.innerHeight - y)
        );
    }

    function ring(x, y, size, color, opts) {

        var node = document.createElement("span");
        node.className = "theme-wave";
        node.style.left = x + "px";
        node.style.top  = y + "px";
        node.style.setProperty("--wave-color", color);
        node.style.setProperty("--wave-blur", opts.blur + "px");
        document.body.appendChild(node);

        var anim = node.animate(
            [
                {
                    width: "0px", height: "0px",
                    borderWidth: opts.from + "px",
                    opacity: opts.opacity
                },
                {
                    width: size + "px", height: size + "px",
                    borderWidth: opts.to + "px",
                    opacity: 0
                }
            ],
            {
                duration: opts.duration,
                delay:    opts.delay,
                easing:   "cubic-bezier(.18,.74,.24,1)",
                fill:     "forwards"
            }
        );

        anim.onfinish = function () { node.remove(); };
        anim.oncancel = function () { node.remove(); };
    }

    function glowPuff(x, y, size, color) {

        var node = document.createElement("span");
        node.className = "theme-wave-core";
        node.style.left = x + "px";
        node.style.top  = y + "px";
        node.style.setProperty("--wave-color", color);
        document.body.appendChild(node);

        var anim = node.animate(
            [
                { width: "0px",             height: "0px",             opacity: .55 },
                { width: size * .55 + "px", height: size * .55 + "px", opacity: .22, offset: .45 },
                { width: size + "px",       height: size + "px",       opacity: 0 }
            ],
            { duration: 760, easing: "cubic-bezier(.2,.7,.25,1)", fill: "forwards" }
        );

        anim.onfinish = function () { node.remove(); };
        anim.oncancel = function () { node.remove(); };
    }

    function launchWave(x, y, nextTheme) {

        var color = nextTheme === "dark"
            ? "rgba(190,214,255,.80)"    // уходим в ночь — волна холодная
            : "rgba(255,201,128,.80)";   // возвращаемся в день — тёплая

        var max = radiusFrom(x, y) * 2.2;

        glowPuff(x, y, max * .9, color);

        ring(x, y, max,        color, { from: 10, to: 2, blur: 7,  opacity: .85, duration: 680, delay: 0 });
        ring(x, y, max * .94,  color, { from: 5,  to: 1, blur: 4,  opacity: .55, duration: 740, delay: 70 });
        ring(x, y, max * .88,  color, { from: 3,  to: 1, blur: 10, opacity: .35, duration: 820, delay: 140 });
    }


    /* ---------- переключение ---------- */

    function switchTheme(originX, originY) {

        if (busy) return;

        var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
        saveTheme(next);

        if (reduce.matches) {
            applyTheme(next);
            return;
        }

        busy = true;
        window.setTimeout(function () { busy = false; }, 520);

        launchWave(originX, originY, next);

        // Chrome / Edge / Safari 18+: новая тема раскрывается кругом из кнопки
        if (typeof document.startViewTransition === "function") {

            var transition = document.startViewTransition(function () {
                applyTheme(next);
            });

            transition.ready.then(function () {

                var r = radiusFrom(originX, originY);

                root.animate(
                    {
                        clipPath: [
                            "circle(0px at "  + originX + "px " + originY + "px)",
                            "circle(" + r + "px at " + originX + "px " + originY + "px)"
                        ]
                    },
                    {
                        duration:      660,
                        easing:        "cubic-bezier(.18,.74,.24,1)",
                        pseudoElement: "::view-transition-new(root)"
                    }
                );

            }).catch(function () { /* переход прерван — не страшно */ });

        } else {

            // Firefox и старые браузеры: цвета плавно перетекают под волной
            root.classList.add("theme-anim");
            applyTheme(next);
            window.setTimeout(function () {
                root.classList.remove("theme-anim");
            }, 640);
        }
    }


    /* ---------- звёзды в шапке ---------- */

    function fillSky(sky) {

        if (sky.dataset.filled) return;
        sky.dataset.filled = "1";

        var count = parseInt(sky.dataset.stars, 10) || 40;
        var box   = document.createDocumentFragment();

        for (var i = 0; i < count; i++) {

            var big  = Math.random() < 0.18;
            var size = (big ? 2.4 : 1.3) + Math.random() * 0.9;

            var star = document.createElement("i");
            star.className = "sky-star";
            star.style.cssText =
                "--x:"     + (Math.random() * 100).toFixed(2) + "%;" +
                "--y:"     + (Math.random() * 100).toFixed(2) + "%;" +
                "--s:"     + size.toFixed(1) + "px;" +
                "--g:"     + (size * 2.8).toFixed(1) + "px;" +
                "--d:"     + (3.5 + Math.random() * 6).toFixed(2) + "s;" +
                "--delay:" + (-Math.random() * 9).toFixed(2) + "s;" +
                "--p:"     + (0.45 + Math.random() * 0.55).toFixed(2) + ";";

            box.appendChild(star);
        }

        sky.appendChild(box);
    }


    /* ---------- запуск ---------- */

    function init() {

        applyTheme(
            root.getAttribute("data-theme") ||
            readTheme() ||
            (systemDark.matches ? "dark" : "light")
        );

        var skies = document.querySelectorAll(".header-sky");
        for (var i = 0; i < skies.length; i++) fillSky(skies[i]);

        document.addEventListener("click", function (event) {

            var button = event.target.closest && event.target.closest(".theme-toggle");
            if (!button) return;

            event.preventDefault();

            var box = button.getBoundingClientRect();
            switchTheme(box.left + box.width / 2, box.top + box.height / 2);
        });

        // если пользователь ничего не выбирал руками — следим за системой
        var onSystem = function (e) {
            if (!readTheme()) applyTheme(e.matches ? "dark" : "light");
        };

        if (systemDark.addEventListener) {
            systemDark.addEventListener("change", onSystem);
        } else if (systemDark.addListener) {
            systemDark.addListener(onSystem);
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }

})();
