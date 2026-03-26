document.addEventListener('DOMContentLoaded', function () {
    setTimeout(function () {
        document.querySelectorAll('.alert').forEach(function (el) {
            el.style.transition = 'opacity 0.5s';
            el.style.opacity = '0';
            setTimeout(function () { el.remove(); }, 500);
        });
    }, 4000);
});
