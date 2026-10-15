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
   v33 (PLAN_V20 Phase 176, Agent N):
   - Zähler „Nachgefasst (n)“: der Chip nimmt antwort.status_text, die Kopfzeile
     [data-ns-versuche] / [data-ns-einwand] folgt antwort.versuche / antwort.einwand
     (auch nach Rückgängig).
   - Block „Nachfass-Mail“ (.ns-mail): Knopf data-ns-schritt="mail" klappt das Formular
     .ns-form-mail auf (nicht .ns-form – es ist kein Schritt), „Vorschau“ holt GET
     data-vorschau-url?vorlage=n (JSON betreff/html), „Senden“ POST per fetch (JSON) →
     Bestätigungszeile ohne Rückgängig, CustomEvent „ns:mail“; ohne fetch normales Absenden.
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

    function chipAktualisieren(vorgangId, status, statusText, versuche) {
        var text = statusText || TEXTE[status] || status;
        document.querySelectorAll('[data-verfolgung-chip="' + vorgangId + '"]').forEach(function (chip) {
            Array.prototype.slice.call(chip.classList).forEach(function (k) {
                if (k.indexOf('vf-') === 0) { chip.classList.remove(k); }
            });
            if (status) {
                chip.classList.add('vf-' + status);
                chip.hidden = false;
                var punkt = chip.querySelector('.abzeichen-punkt');
                chip.textContent = '';
                if (punkt) { chip.appendChild(punkt); chip.appendChild(document.createTextNode(text)); }
                else { chip.textContent = text; }
                chip.title = 'Verfolgung: ' + text;
                if (typeof versuche === 'number') { chip.setAttribute('data-versuche', String(versuche)); }
            } else {
                chip.hidden = true;
            }
        });
    }

    /* v33: Kopfzeile der Anruf-Karte (Zähler + letzter Einwand) nach Antwort nachziehen */
    function kopfAktualisieren(dialog, antwort) {
        var id = dialog.getAttribute('data-vorgang');
        var versuche = (typeof antwort.versuche === 'number') ? antwort.versuche : null;
        if (versuche !== null) {
            dialog.setAttribute('data-versuche', String(versuche));
            document.querySelectorAll('[data-ns-versuche="' + id + '"]').forEach(function (el) {
                el.textContent = versuche + ' Nachfass-Anruf' + (versuche === 1 ? '' : 'e');
                el.hidden = versuche <= 0;
            });
        }
        if (typeof antwort.einwand === 'string' && antwort.einwand) {
            document.querySelectorAll('[data-ns-einwand="' + id + '"]').forEach(function (el) {
                el.textContent = '';
                el.appendChild(document.createTextNode('Letzter Einwand: '));
                var fett = document.createElement('strong');
                fett.textContent = antwort.einwand;
                el.appendChild(fett);
                el.hidden = false;
            });
        }
        var kopf = dialog.querySelector('.ns-kopf');
        if (kopf) {
            var sichtbar = Array.prototype.some.call(kopf.children, function (c) { return !c.hidden; });
            kopf.hidden = !sichtbar;
        }
    }

    function bestaetigen(dialog, antwort, ohneRueckgaengig) {
        var zeile = dialog.querySelector('.ns-bestaetigung');
        var text = dialog.querySelector('.ns-bestaetigung-text');
        var link = dialog.querySelector('.ns-rueckgaengig');
        if (!zeile || !text) { return; }
        text.textContent = '✓ ' + (antwort.meldung || 'Gespeichert.');
        zeile.hidden = false;
        if (!ohneRueckgaengig) {
            dialog.classList.add('ns-fertig');
            dialog.setAttribute('data-status', antwort.status || '');
        }
        if (link) {
            var info = (!ohneRueckgaengig && antwort.rueckgaengig) || null;
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
                chipAktualisieren(dialog.getAttribute('data-vorgang'), erg.antwort.status || '',
                                  erg.antwort.status_text || '', erg.antwort.versuche);
                kopfAktualisieren(dialog, erg.antwort);
                bestaetigen(dialog, erg.antwort, false);
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
                chipAktualisieren(dialog.getAttribute('data-vorgang'), antwort.status || '',
                                  antwort.status_text || '', antwort.versuche);
                kopfAktualisieren(dialog, antwort);
                dialog.dispatchEvent(new CustomEvent('ns:rueckgaengig', { bubbles: true, detail: antwort }));
            })
            .catch(function () { fehler(dialog, 'Rückgängig fehlgeschlagen (Verbindung).'); });
    }

    /* v33: Nachfass-Mail – Vorschau (GET JSON) und Senden (POST JSON) */
    function mailVorschau(form, dialog) {
        var block = form.closest('.ns-mail');
        var url = block ? block.getAttribute('data-vorschau-url') : '';
        var vorlage = form.querySelector('input[name="vorlage"]:checked');
        var ziel = form.querySelector('.ns-mail-vorschau');
        if (!url || !ziel) { return; }
        fehler(dialog, '');
        fetch(url + (url.indexOf('?') >= 0 ? '&' : '?') + 'vorlage=' + encodeURIComponent(vorlage ? vorlage.value : '1'),
              { credentials: 'same-origin', headers: { 'Accept': 'application/json' } })
            .then(function (r) { return r.json(); })
            .then(function (antwort) {
                if (!antwort || !antwort.ok) { fehler(dialog, (antwort && antwort.meldung) || 'Vorschau nicht möglich.'); return; }
                var betreff = ziel.querySelector('.ns-mail-betreff');
                var inhalt = ziel.querySelector('.ns-mail-inhalt');
                if (betreff) { betreff.textContent = 'Betreff: ' + (antwort.betreff || ''); }
                /* HTML stammt aus der eigenen Vorlage + Signatur (Server) – wie die Vorlagen-Vorschau */
                if (inhalt) { inhalt.innerHTML = antwort.html || ''; }
                ziel.hidden = false;
            })
            .catch(function () { fehler(dialog, 'Vorschau nicht möglich (Verbindung).'); });
    }

    function mailSenden(form, dialog) {
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
                if (!erg.antwort.ok) { fehler(dialog, erg.antwort.meldung || 'Nachfass-Mail nicht gesendet.'); return; }
                aufklappen(dialog, null);
                bestaetigen(dialog, erg.antwort, true);
                dialog.dispatchEvent(new CustomEvent('ns:mail', { bubbles: true, detail: erg.antwort }));
            })
            .catch(function () {
                knoepfe.forEach(function (b) { b.disabled = false; });
                fehler(dialog, 'Nachfass-Mail nicht gesendet (Verbindung). Bitte erneut versuchen.');
            });
    }

    document.addEventListener('click', function (ev) {
        var knopf = ev.target.closest('button[data-ns-schritt]');
        if (knopf && knopf.type === 'button') {
            var dialog = dialogVon(knopf);
            if (!dialog || knopf.disabled) { return; }
            var schritt = knopf.getAttribute('data-ns-schritt');
            var form = dialog.querySelector('.ns-form-' + schritt);
            var offen = form && !form.hidden;
            aufklappen(dialog, offen ? null : schritt);
            if (form && !offen) { freitextPruefen(form); datumPruefen(form); }
            return;
        }
        var vorschau = ev.target.closest('.ns-mail-vorschau-knopf');
        if (vorschau) {
            var f0 = vorschau.closest('form');
            var d0 = dialogVon(vorschau);
            if (f0 && d0 && window.fetch) { mailVorschau(f0, d0); }
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
        if (!form.classList) { return; }
        var dialog = dialogVon(form);
        if (!dialog) { return; }
        if (form.classList.contains('ns-mail-form')) {
            if (!window.fetch || !window.FormData) { return; }   // Rückfall: normales Absenden
            ev.preventDefault();
            mailSenden(form, dialog);
            return;
        }
        if (!form.classList.contains('ns-form')) { return; }
        notizSpiegeln(form, dialog);
        if (!window.fetch || !window.FormData) { return; }   // Rückfall: normales Absenden
        ev.preventDefault();
        senden(form, dialog);
    });
})();
