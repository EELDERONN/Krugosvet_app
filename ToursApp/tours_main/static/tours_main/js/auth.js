/* ==========================================================
   КРУГОСВЕТ — логика страницы входа / регистрации
   ========================================================== */

document.addEventListener("DOMContentLoaded", () => {

    /* ------------------------------------------------------
       1. Переключение вкладок «Вход / Регистрация»
    ------------------------------------------------------ */

    const switcher = document.querySelector(".auth-switcher");
    const tabButtons = document.querySelectorAll(".auth-switcher__btn");
    const forms = document.querySelectorAll(".auth-form");
    const switchLinks = document.querySelectorAll("[data-switch]");

    function activate(tabName) {

        if (!switcher) return;

        tabButtons.forEach((btn) => {
            const isActive = btn.dataset.tab === tabName;
            btn.classList.toggle("is-active", isActive);
            btn.setAttribute("aria-selected", isActive ? "true" : "false");
        });

        forms.forEach((form) => {
            const isActive = form.dataset.panel === tabName;

            // Снимаем и возвращаем класс, чтобы каскад полей
            // проигрывался заново при каждом переключении
            form.classList.remove("is-active");

            if (isActive) {
                void form.offsetWidth;          // перезапуск анимации
                form.classList.add("is-active");
            }
        });

        switcher.setAttribute("data-active", tabName);

        const url = new URL(window.location);
        url.searchParams.set("tab", tabName);
        window.history.replaceState({}, "", url);
    }

    tabButtons.forEach((btn) => {
        btn.addEventListener("click", () => activate(btn.dataset.tab));
    });

    switchLinks.forEach((link) => {
        link.addEventListener("click", () => activate(link.dataset.switch));
    });

    // Открыть нужную вкладку по ссылке вида /auth/?tab=register
    const paramTab = new URL(window.location).searchParams.get("tab");

    if (paramTab === "register" || paramTab === "login") {
        activate(paramTab);
    }


    /* ------------------------------------------------------
       2. Кнопка «показать пароль»
    ------------------------------------------------------ */

    document.querySelectorAll("[data-eye]").forEach((eye) => {

        eye.addEventListener("click", () => {

            const box = eye.closest(".auth-field__box");
            if (!box) return;

            const input = box.querySelector("input");
            if (!input) return;

            const show = input.type === "password";

            input.type = show ? "text" : "password";
            eye.classList.toggle("is-open", show);
            eye.setAttribute("aria-label", show ? "Скрыть пароль" : "Показать пароль");
        });
    });


    /* ------------------------------------------------------
       3. Индикатор надёжности пароля (только регистрация)
    ------------------------------------------------------ */

    const meter = document.querySelector("[data-meter]");

    if (meter) {

        const meterLabel = meter.querySelector("[data-meter-label]");

        // Поле пароля — соседнее с индикатором внутри того же .auth-field
        const field = meter.closest(".auth-field");
        const passInput = field ? field.querySelector("input") : null;

        const LEVELS = {
            0: "надёжность",
            1: "слабый",
            2: "средний",
            3: "хороший",
            4: "отличный"
        };

        function scorePassword(value) {

            if (!value) return 0;

            let score = 0;

            if (value.length >= 8) score++;
            if (value.length >= 12) score++;

            // Разнообразие символов
            const variety =
                (/[a-z]/.test(value) ? 1 : 0) +
                (/[A-Z]/.test(value) ? 1 : 0) +
                (/[0-9]/.test(value) ? 1 : 0) +
                (/[^A-Za-z0-9]/.test(value) ? 1 : 0);

            if (variety >= 2) score++;
            if (variety >= 3) score++;

            // Слишком короткий пароль не может быть сильным
            if (value.length < 8) score = Math.min(score, 1);

            return Math.min(score, 4);
        }

        if (passInput) {

            passInput.addEventListener("input", () => {

                const level = scorePassword(passInput.value);

                meter.setAttribute("data-level", level);

                if (meterLabel) {
                    meterLabel.textContent = LEVELS[level];
                }
            });
        }
    }

});
