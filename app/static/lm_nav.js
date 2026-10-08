/* Lead-Management v29 (PLAN_LEAD_V4 Phase 141): „Mehr …“ als Flyout.
   Das <details id="lm-mehr"> der Icon-Leiste (leadmanagement/_nav.html) öffnet
   ein Panel (.lm-leiste-menue[data-flyout], position: fixed – nie innerhalb der Menüspalte
   gescrollt), das rechts neben der Leiste auf Höhe des Eintrags steht; unter
   900 px (untere Icon-Zeile) öffnet es nach oben. Schließen per Klick
   außerhalb, Escape oder erneutem Klick auf den Eintrag. Vanilla JS. */
(function () {
    'use strict';
    if (window.__lmNavGeladen) { return; }
    window.__lmNavGeladen = true;
    const mehr = document.getElementById('lm-mehr');
    if (!mehr) { return; }
    const summary = mehr.querySelector('summary');
    const panel = mehr.querySelector('.lm-leiste-menue[data-flyout]');
    if (!summary || !panel) { return; }

    function unten() { return window.innerWidth <= 900; }

    function positionieren() {
        if (!mehr.open) { return; }
        mehr.classList.toggle('lm-flyout-oben', unten());
        if (unten()) {
            panel.style.removeProperty('--lm-flyout-top');
            return;
        }
        const rect = summary.getBoundingClientRect();
        let oben = rect.top;
        const hoehe = panel.offsetHeight;
        if (oben + hoehe > window.innerHeight - 8) {
            oben = Math.max(8, window.innerHeight - hoehe - 8);
        }
        panel.style.setProperty('--lm-flyout-top', Math.round(oben) + 'px');
    }

    function schliessen(fokus) {
        if (!mehr.open) { return; }
        mehr.removeAttribute('open');
        if (fokus) { summary.focus(); }
    }

    mehr.addEventListener('toggle', positionieren);
    window.addEventListener('resize', positionieren);
    window.addEventListener('scroll', positionieren, { passive: true });
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' || e.key === 'Esc') { schliessen(true); }
    });
    document.addEventListener('click', function (e) {
        if (mehr.open && !mehr.contains(e.target)) { schliessen(false); }
    });
    // Tastatur im Panel: Pfeiltasten zwischen den Einträgen
    panel.addEventListener('keydown', function (e) {
        const eintraege = Array.from(panel.querySelectorAll('a[role=menuitem]'));
        const i = eintraege.indexOf(document.activeElement);
        if (e.key === 'ArrowDown') { e.preventDefault(); (eintraege[i + 1] || eintraege[0]).focus(); }
        if (e.key === 'ArrowUp') { e.preventDefault(); (eintraege[i - 1] || eintraege[eintraege.length - 1]).focus(); }
    });
})();
