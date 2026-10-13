/* v32 (PLAN_V19 Phase 163): Dialog „Nächster Schritt“ (templates/vorgaenge/_naechster_schritt.html).
   - Knöpfe „Abgelehnt“ / „Nochmal anrufen“ klappen ihr Formular auf (nur eines offen),
     „Bestellung kommt“ speichert sofort.
   - Grund-Chips: bei data-freitext-pflicht="1" wird das Freitextfeld Pflicht.
   - Speichern per fetch (Accept: application/json), Bestätigungszeile mit Rückgängig-Link
     (data-rueckgaengig-s Sekunden, Standard 10); ohne fetch läuft das Formular normal
     (Redirect auf „zurueck“).
   - Notiz: Textarea [data-ns-notiz="<vorgang>"] (im Dialog oder in der Anruf-Karte von
     „Mein Tag“) wird beim Absenden in das Hidden-Feld „notiz“ gespiegelt.
   - Nach Erfolg: Chip [data-verfolgung-chip="<vorgang>"] wird aktualisiert, CustomEvent
     „ns:gespeichert“ bzw. „ns:rueckgaengig“ am .ns-dialog (detail = Antwort).
   Alle Daten aus data-Attributen – kein tojson in on*-Attributen (v30-Regel). */
(function () {
    'use strict';
    if (window.__nsGeladen) { return; }
    window.__nsGeladen = true;

    var TEXTE = {
        versendet: 'Versendet', nachgefasst: 'Nachgefasst',
        bestellung_angekuendigt: 'Bestellung angekündigt', angenommen: 'Angenommen', abgelehnt: 'Abgelehnt'
    };

    function dialogVon(el) { return el ? el.closest('.ns-dialog') : null; }

    function aufklappen(dialog, schritt) {
        dialog.querySelectorAll('.ns-aufklapp').forEach(function (f) {
            var offen = schritt && f.classList.contains('ns-form-' + schritt);
            f.hidden = !offen;
        });
        dialog.querySelectorAll('button[data-ns-schritt]').forEach(function (b) {
            if (b.hasAttribute('aria-expanded')) {
                b.setAttribute('aria-expanded', b.getAttribute('data-ns-schritt') === schritt ? 'true' : 'false');
            }
        });
        if (schritt) {
            var form = dialog.querySelector('.ns-form-' + schritt);
            var erstes = form && form.querySelector('input[type="radio"]:checked, input[type="radio"]');
            if (erstes && erstes.focus) { try { erstes.focus({ preventScroll: true }); } catch (x) { /* egal */ } }
        }
    }

    function freitextPruefen(form) {
        var feld = form.querySelector('.ns-freitext');
        var eingabe = form.querySelector('input[name="freitext"]');
        if (!feld || !eingabe) { return; }
        var gewaehlt = form.querySelector('input[name="grund_id"]:checked');
        var pflicht = !!(gewaehlt && gewaehlt.getAttribute('data-freitext-pflicht') === '1');
        feld.hidden = !gewaehlt;
        eingabe.required = pflicht;
        var markierung = feld.querySelector('.ns-pflicht');
        if (markierung) { markierung.hidden = !pflicht; }
    }

    function datumPruefen(form) {
        var datum = form.querySelector('input[name="datum"]');
        var wahl = form.querySelector('input[name="wann"][value="datum"]');
        if (!datum || !wahl) { return; }
        datum.required = wahl.checked;
    }

    function notizSpiegeln(form, dialog) {
        var id = dialog.getAttribute('data-vorgang');
        var quelle = document.querySelector('[data-ns-notiz="' + id + '"]');
        var ziel = form.querySelector('.ns-notiz-spiegel');
        if (ziel) { ziel.value = quelle ? (quelle.value || '') : ''; }
    }

    function fehler(dialog, text) {
        var f = dialog.querySelector('.ns-fehler');
        if (!f) { return; }
        f.textContent = text || '';
        f.hidden = !text;
    }

    function chipAktualisieren(vorgangId, status) {
        document.querySelectorAll('[data-verfolgung-chip="' + vorgangId + '"]').forEach(function (chip) {
            Array.prototype.slice.call(chip.classList).forEach(function (k) {
                if (k.indexOf('vf-') === 0) { chip.classList.remove(k); }
            });
            if (status) {
                chip.classList.add('vf-' + status);
                chip.hidden = false;
                var punkt = chip.querySelector('.abzeichen-punkt');
                chip.textContent = '';
                if (punkt) { chip.appendChild(punkt); chip.appendChild(document.createTextNode(TEXTE[status] || status)); }
                else { chip.textContent = TEXTE[status] || status; }
                chip.title = 'Verfolgung: ' + (TEXTE[status] || status);
            } else {
                chip.hidden = true;
            }
        });
    }

    function bestaetigen(dialog, antwort) {
        var zeile = dialog.querySelector('.ns-bestaetigung');
        var text = dialog.querySelector('.ns-bestaetigung-text');
        var link = dialog.querySelector('.ns-rueckgaengig');
        if (!zeile || !text) { return; }
        text.textContent = '✓ ' + (antwort.meldung || 'Gespeichert.');
        zeile.hidden = false;
        dialog.classList.add('ns-fertig');
        dialog.setAttribute('data-status', antwort.status || '');
        if (link) {
            var info = antwort.rueckgaengig || null;
            if (info && info.token) {
                link.hidden = false;
                link.setAttribute('data-token', info.token);
                var sekunden = parseInt(dialog.getAttribute('data-rueckgaengig-s') || info.sekunden || 10, 10);
                window.clearTimeout(dialog.__nsTimer);
                dialog.__nsTimer = window.setTimeout(function () { link.hidden = true; }, sekunden * 1000);
            } else {
                link.hidden = true;
            }
        }
    }

    function senden(form, dialog) {
        var knoepfe = form.querySelectorAll('button');
        knoepfe.forEach(function (b) { b.disabled = true; });
        fehler(dialog, '');
        var daten = new FormData(form);
        return fetch(form.action, { method: 'POST', body: daten, credentials: 'same-origin',
                                    headers: { 'Accept': 'application/json' } })
            .then(function (r) {
                return r.json().then(function (antwort) { return { status: r.status, antwort: antwort }; },
                                     function () { return { status: r.status, antwort: null }; });
            })
            .then(function (erg) {
                knoepfe.forEach(function (b) { b.disabled = false; });
                if (!erg.antwort) { window.location.reload(); return; }
                if (!erg.antwort.ok) { fehler(dialog, erg.antwort.meldung || 'Speichern fehlgeschlagen.'); return; }
                aufklappen(dialog, null);
                chipAktualisieren(dialog.getAttribute('data-vorgang'), erg.antwort.status || '');
                bestaetigen(dialog, erg.antwort);
                dialog.dispatchEvent(new CustomEvent('ns:gespeichert', { bubbles: true, detail: erg.antwort }));
            })
            .catch(function () {
                knoepfe.forEach(function (b) { b.disabled = false; });
                fehler(dialog, 'Speichern fehlgeschlagen (Verbindung). Bitte erneut versuchen.');
            });
    }

    function rueckgaengig(dialog, token) {
        var daten = new URLSearchParams();
        daten.set('schritt', 'rueckgaengig');
        daten.set('token', token);
        fehler(dialog, '');
        return fetch(dialog.getAttribute('data-url'), { method: 'POST', body: daten, credentials: 'same-origin',
                                                       headers: { 'Accept': 'application/json' } })
            .then(function (r) { return r.json(); })
            .then(function (antwort) {
                if (!antwort || !antwort.ok) { fehler(dialog, (antwort && antwort.meldung) || 'Rückgängig fehlgeschlagen.'); return; }
                var text = dialog.querySelector('.ns-bestaetigung-text');
                var link = dialog.querySelector('.ns-rueckgaengig');
                if (text) { text.textContent = '↶ ' + (antwort.meldung || 'Rückgängig gemacht.'); }
                if (link) { link.hidden = true; }
                dialog.classList.remove('ns-fertig');
                dialog.setAttribute('data-status', antwort.status || '');
                chipAktualisieren(dialog.getAttribute('data-vorgang'), antwort.status || '');
                dialog.dispatchEvent(new CustomEvent('ns:rueckgaengig', { bubbles: true, detail: antwort }));
            })
            .catch(function () { fehler(dialog, 'Rückgängig fehlgeschlagen (Verbindung).'); });
    }

    document.addEventListener('click', function (ev) {
        var knopf = ev.target.closest('button[data-ns-schritt]');
        if (knopf && knopf.type === 'button') {
            var dialog = dialogVon(knopf);
            if (!dialog) { return; }
            var schritt = knopf.getAttribute('data-ns-schritt');
            var form = dialog.querySelector('.ns-form-' + schritt);
            var offen = form && !form.hidden;
            aufklappen(dialog, offen ? null : schritt);
            if (form && !offen) { freitextPruefen(form); datumPruefen(form); }
            return;
        }
        var abbrechen = ev.target.closest('.ns-abbrechen');
        if (abbrechen) {
            var d2 = dialogVon(abbrechen);
            if (d2) { aufklappen(d2, null); }
            return;
        }
        var link = ev.target.closest('.ns-rueckgaengig');
        if (link) {
            ev.preventDefault();
            var d3 = dialogVon(link);
            if (d3 && window.fetch) { rueckgaengig(d3, link.getAttribute('data-token') || ''); }
        }
    });

    document.addEventListener('change', function (ev) {
        var form = ev.target.closest('.ns-form');
        if (!form) { return; }
        if (ev.target.name === 'grund_id') { freitextPruefen(form); }
        if (ev.target.name === 'wann') { datumPruefen(form); }
        if (ev.target.name === 'datum' && ev.target.value) {
            var wahl = form.querySelector('input[name="wann"][value="datum"]');
            if (wahl) { wahl.checked = true; datumPruefen(form); }
        }
    });

    document.addEventListener('submit', function (ev) {
        var form = ev.target;
        if (!form.classList || !form.classList.contains('ns-form')) { return; }
        var dialog = dialogVon(form);
        if (!dialog) { return; }
        notizSpiegeln(form, dialog);
        if (!window.fetch || !window.FormData) { return; }   // Rückfall: normales Absenden
        ev.preventDefault();
        senden(form, dialog);
    });
})();
