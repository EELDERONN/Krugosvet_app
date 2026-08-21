/* ==========================================================
   КРУГОСВЕТ — ЛОГИКА ПЕРЕКЛЮЧЕНИЯ ТЕМЫ
   Файл: tours_main/static/tours_main/js/theme.js
   Подключается в конце <body> в base.html.
========================================================== */

(function () {
    "use strict";

    var KEY        = "krugosvet-theme";
    var root       = document.documentElement;
    var reduce     = window.matchMedia("(prefers-reduced-motion: reduce)");
    var systemDark = window.matchMedia("(prefers-color-scheme: dark)");


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
            buttons[i].setAttribute("aria-label", isDark ? "Включить светлую тему" : "Включить тёмную тему");
        }

        var meta = document.querySelector('meta[name="theme-color"]');
        if (meta) {
            meta.setAttribute("content", getComputedStyle(root).getPropertyValue("--bg").trim());
        }
    }


    /* ---------- волна от кнопки ---------- */

    function radiusFrom(x, y) {
        return Math.hypot(
            Math.max(x, window.innerWidth  - x),
            Math.max(y, window.innerHeight - y)
        );
    }

    function launchWave(x, y, nextTheme) {

        var color = nextTheme === "dark"
            ? "rgba(196,218,255,.55)"   // уходим в ночь — волна холодная
            : "rgba(255,196,120,.55)";  // возвращаемся в день — тёплая

        var max = radiusFrom(x, y) * 2.15;

        for (var i = 0; i < 3; i++) {

            var ring = document.createElement("span");
            ring.className = "theme-wave";
            ring.style.left = x + "px";
            ring.style.top  = y + "px";
            ring.style.setProperty("--wave-color", color);
            document.body.appendChild(ring);

            var anim = ring.animate(
                [
                    { width: "0px",       height: "0px",       borderWidth: "3px", opacity: .75 },
                    { width: max + "px",  height: max + "px",  borderWidth: "1px", opacity: 0   }
                ],
                {
                    duration: 680 + i * 70,
                    delay:    i * 95,
                    easing:   "cubic-bezier(.22,.72,.28,1)",
                    fill:     "forwards"
                }
            );

            anim.onfinish = (function (node) {
                return function () { node.remove(); };
            })(ring);
        }
    }


    /* ---------- переключение ---------- */

    function switchTheme(originX, originY) {

        var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
        saveTheme(next);

        if (reduce.matches) {
            applyTheme(next);
            return;
        }

        launchWave(originX, originY, next);

        // Chrome / Edge / Safari 18+: новая тема раскрывается кругом из кнопки
        if (typeof document.startViewTransition === "function") {

            var transition = document.startViewTransition(function () { applyTheme(next); });

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
                        duration:     640,
                        easing:       "cubic-bezier(.22,.72,.28,1)",
                        pseudoElement:"::view-transition-new(root)"
                    }
                );

            }).catch(function () { /* переход прерван — не страшно */ });

        } else {

            // Firefox и старые браузеры: цвета плавно перетекают под волной
            root.classList.add("theme-anim");
            applyTheme(next);
            window.setTimeout(function () { root.classList.remove("theme-anim"); }, 620);
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

            var button = event.target.closest(".theme-toggle");
            if (!button) return;

            var box = button.getBoundingClientRect();
            switchTheme(box.left + box.width / 2, box.top + box.height / 2);
        });

        // если пользователь ничего не выбирал — следим за настройкой системы
        systemDark.addEventListener("change", function (e) {
            if (!readTheme()) applyTheme(e.matches ? "dark" : "light");
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }

})();
