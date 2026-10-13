/* v32 (PLAN_V19 Phase 161/162): Vertriebler-Ansicht „Mein Tag“ (templates/leads/mein_tag.html).
   - viewport-fit=cover (Safe-Area wie die mobile Erfassung v14) – base.html bleibt
     unverändert, darum wird das Viewport-Meta hier ergänzt.
   - Notizfeld „Notiz zum Gespräch“: Speichern per fetch (Accept: application/json) an
     /leads/notiz/<vorgang>, Bestätigung in der Karte; ohne fetch normales Absenden.
   - Dialog „Nächster Schritt“ (verfolgung.js von N): nach „ns:gespeichert“ verschwindet die
     Anruf-Karte aus „Fällig heute“ (Bestellung → Hinweis „jetzt unter Heiße Kunden“),
     „ns:rueckgaengig“ holt sie zurück. Keine Daten in on*-Attributen (v30-Regel). */
(function () {
    'use strict';
    if (window.__meinTagGeladen) { return; }
    window.__meinTagGeladen = true;

    var meta = document.querySelector('meta[name="viewport"]');
    if (meta && meta.getAttribute('content').indexOf('viewport-fit') === -1) {
        meta.setAttribute('content', meta.getAttribute('content') + ', viewport-fit=cover');
    }

    function meldung(form, text, klasse) {
        var m = form.querySelector('.mt-notiz-meldung');
        if (!m) { return; }
        m.textContent = text || '';
        m.hidden = !text;
        m.className = 'mt-notiz-meldung dezent' + (klasse ? ' ' + klasse : '');
    }

    document.addEventListener('submit', function (ev) {
        var form = ev.target;
        if (!form.classList || !form.classList.contains('mt-notiz')) { return; }
        if (!window.fetch || !window.FormData) { return; }
        ev.preventDefault();
        var ta = form.querySelector('textarea');
        var text = (ta.value || '').trim();
        if (!text) { meldung(form, 'Bitte eine Notiz eingeben.', 'fehler'); return; }
        var knopf = form.querySelector('button');
        knopf.disabled = true;
        fetch(form.action, { method: 'POST', body: new FormData(form), credentials: 'same-origin',
                             headers: { 'Accept': 'application/json' } })
            .then(function (r) { return r.json().then(function (a) { return a; }, function () { return null; }); })
            .then(function (antwort) {
                knopf.disabled = false;
                if (!antwort) { window.location.reload(); return; }
                if (!antwort.ok) { meldung(form, antwort.meldung || 'Notiz konnte nicht gespeichert werden.', 'fehler'); return; }
                ta.value = '';
                meldung(form, antwort.meldung || 'Notiz gespeichert.', 'ok');
                var liste = form.closest('.mt-karte') && form.closest('.mt-karte').querySelector('.mt-aktivitaeten ul');
                if (liste && antwort.eintrag) {
                    var li = document.createElement('li');
                    var zeit = document.createElement('span'); zeit.className = 'mt-akt-zeit';
                    zeit.textContent = (antwort.eintrag.zeit || '') + ' ';
                    var art = document.createElement('span'); art.className = 'mt-akt-art'; art.textContent = 'Notiz';
                    li.appendChild(zeit); li.appendChild(art);
                    li.appendChild(document.createTextNode(' ' + (antwort.eintrag.benutzer_name || '') + ': ' + (antwort.eintrag.text || '')));
                    liste.insertBefore(li, liste.firstChild);
                    while (liste.children.length > 3) { liste.removeChild(liste.lastChild); }
                }
            })
            .catch(function () { knopf.disabled = false; meldung(form, 'Speichern fehlgeschlagen (Verbindung).', 'fehler'); });
    });

    function karteVon(el) { return el ? el.closest('[data-mt-karte="faellig"]') : null; }

    function zaehlerSetzen(delta) {
        var block = document.getElementById('faellig');
        var zahl = block && block.querySelector('h2 .mt-zahl');
        if (!zahl) { return; }
        var n = Math.max(0, (parseInt(zahl.textContent, 10) || 0) + delta);
        zahl.textContent = String(n);
        zahl.classList.toggle('rot', n > 0);
    }

    document.addEventListener('ns:gespeichert', function (ev) {
        var karte = karteVon(ev.target);
        if (!karte) { return; }
        var status = (ev.detail && ev.detail.status) || '';
        karte.classList.add('mt-fertig');
        karte.setAttribute('data-mt-status', status);
        var hinweis = karte.querySelector('.ns-bestaetigung-text');
        if (hinweis && status === 'bestellung_angekuendigt') {
            hinweis.textContent += ' – jetzt unter „Heiße Kunden“ (nach dem Neuladen).';
        }
        zaehlerSetzen(-1);
        var sekunden = parseInt((ev.target.getAttribute && ev.target.getAttribute('data-rueckgaengig-s')) || '10', 10);
        window.clearTimeout(karte.__mtTimer);
        karte.__mtTimer = window.setTimeout(function () {
            if (karte.classList.contains('mt-fertig')) { karte.hidden = true; }
        }, (sekunden + 2) * 1000);
    });

    document.addEventListener('ns:rueckgaengig', function (ev) {
        var karte = karteVon(ev.target);
        if (!karte) { return; }
        window.clearTimeout(karte.__mtTimer);
        karte.hidden = false;
        karte.classList.remove('mt-fertig');
        zaehlerSetzen(1);
    });
})();
