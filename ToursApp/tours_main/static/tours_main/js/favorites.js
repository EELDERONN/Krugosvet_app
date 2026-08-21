/* ==========================================================================
   Кругосвет — избранное в каталоге туров
   favorites.js · без зависимостей

   Сердечко на карточке тура кладёт тур в раздел «Избранное» личного
   кабинета (модель FavoriteTour). Ответ приходит от вьюхи favorite_toggle.
   ========================================================================== */
(function () {
    'use strict';

    const hearts = Array.from(document.querySelectorAll('[data-fav]'));
    if (!hearts.length) return;

    function csrfToken() {
        const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
        if (input) return input.value;
        const m = document.cookie.match(/csrftoken=([^;]+)/);
        return m ? m[1] : '';
    }

    /* маленькое всплывающее сообщение — в каталоге своих тостов нет */
    let host = null;

    function note(message) {
        if (!host) {
            host = document.createElement('div');
            host.className = 'fav-toast-host';
            document.body.appendChild(host);
        }

        const el = document.createElement('div');
        el.className = 'fav-toast';
        el.textContent = message;
        host.appendChild(el);

        requestAnimationFrame(() => el.classList.add('is-in'));

        setTimeout(() => {
            el.classList.remove('is-in');
            setTimeout(() => el.remove(), 400);
        }, 2600);
    }

    hearts.forEach(btn => {
        btn.addEventListener('click', e => {
            e.preventDefault();
            e.stopPropagation();          // чтобы не открылся попап карточки

            const url = btn.dataset.url;
            if (!url || btn.disabled) return;

            btn.disabled = true;

            fetch(url, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken(),
                    'X-Requested-With': 'XMLHttpRequest'
                },
                credentials: 'same-origin'
            })
                .then(r => (r.ok ? r.json() : Promise.reject(r.status)))
                .then(data => {
                    btn.classList.toggle('is-active', data.added);
                    btn.disabled = false;

                    // короткая «пружинка» на сердечке
                    btn.animate(
                        [{ transform: 'scale(1)' },
                         { transform: 'scale(1.28)' },
                         { transform: 'scale(1)' }],
                        { duration: 380, easing: 'cubic-bezier(.34,1.56,.64,1)' }
                    );

                    note(data.added
                        ? '«' + data.title + '» в избранном'
                        : '«' + data.title + '» убран из избранного');
                })
                .catch(status => {
                    btn.disabled = false;

                    if (status === 403 || status === 401) {
                        note('Войдите в аккаунт, чтобы сохранять туры');
                    } else {
                        note('Не получилось — попробуйте ещё раз');
                    }
                });
        });
    });
})();
