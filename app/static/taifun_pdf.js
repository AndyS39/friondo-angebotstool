/* v34 (PLAN_V21 Phase 180, Agent V): TAIFUN-Angebots-PDF per Drag & Drop.
   Zonen tragen data-taifun-dropzone (Makros in templates/_taifun_pdf.html):
   - modus "dialog"  (Dialog „Extern erledigt“): das abgelegte PDF wird VOR dem Speichern über
     POST /angebote/extern/pdf-lesen gelesen; Nummer, Datum und Endbetrag des Dialogs werden
     vorbelegt (leere Felder) und mit „aus PDF gelesen – bitte prüfen“ markiert; die erkannte
     Sparte ist nur ein Vorschlag (Hinweiszeile). Das PDF bleibt im Datei-Feld und geht mit
     dem Dialog an den Server.
   - modus "eintrag" (TAIFUN-Eintrag in Akte, Liste, TAIFUN-Seite): vorhandenes PDF nur nach
     Sicherheitsabfrage ersetzen (Feld bestaetigt=1), dann Häkchen „Nummer/Datum/Endbetrag
     aus dem neuen PDF übernehmen“ (vorbelegt, wenn erkannt) und „PDF speichern“.
   Tastatur: Zone ist fokussierbar, Enter/Leertaste öffnet den Datei-Dialog; am Handy
   (pointer: coarse) gibt es nur den Datei-Dialog. Reines Browser-Skript, ES5, ohne innerHTML. */
(function () {
    'use strict';
    var MAX_BYTES = 20 * 1024 * 1024;
    var PRUEFEN = 'aus PDF gelesen – bitte prüfen';
    var SPARTEN = { WB: 'Wallbox', WP: 'Wärmepumpe', KL: 'Klimaanlage', PV: 'Photovoltaik' };

    function statusElement(zone) {
        var p = zone.nextElementSibling;
        if (p && p.hasAttribute('data-taifun-status')) { return p; }
        var form = zone.closest('form');
        return form ? form.querySelector('[data-taifun-status]') : null;
    }

    function status(zone, text, fehler) {
        var p = statusElement(zone);
        if (!p) { return; }
        p.textContent = text || '';
        p.hidden = !text;
        p.classList.toggle('tp-fehler', !!fehler);
    }

    function dateiPruefen(datei) {
        if (!datei) { return 'Bitte eine PDF-Datei wählen.'; }
        var name = (datei.name || '').toLowerCase();
        var typ = (datei.type || '').toLowerCase();
        if (typ !== 'application/pdf' && name.slice(-4) !== '.pdf') {
            return 'Die Datei ist kein PDF.';
        }
        if (datei.size > MAX_BYTES) {
            return 'Das PDF ist größer als 20 MB – bitte eine kleinere Datei wählen.';
        }
        return '';
    }

    function eingabeFeld(zone) {
        return zone.querySelector('input[type="file"]');
    }

    function eingabeLeeren(zone) {
        var feld = eingabeFeld(zone);
        if (feld) { try { feld.value = ''; } catch (e) { /* IE: Feld bleibt */ } }
    }

    function dateiSetzen(zone, datei) {
        var feld = eingabeFeld(zone);
        if (!feld) { return false; }
        try {
            var dt = new DataTransfer();
            dt.items.add(datei);
            feld.files = dt.files;
            return true;
        } catch (e) {
            return false;
        }
    }

    function lesen(zone, datei) {
        var fd = new FormData();
        fd.append('pdf_datei', datei, datei.name);
        return fetch(zone.getAttribute('data-lesen-url') || '/angebote/extern/pdf-lesen', {
            method: 'POST', body: fd, credentials: 'same-origin',
            headers: { 'Accept': 'application/json' }
        }).then(function (antwort) {
            return antwort.json().then(function (daten) {
                if (!antwort.ok || !daten || daten.ok === false) {
                    throw new Error((daten && daten.meldung) || ('Lesen fehlgeschlagen (' + antwort.status + ')'));
                }
                return daten;
            });
        });
    }

    /* --- Dialog „Extern erledigt“: Felder vorbelegen ------------------------------------ */

    function hinweisAnFeld(feld, text) {
        var alt = feld.parentElement.querySelector('[data-tp-hinweis]');
        if (alt) { alt.parentElement.removeChild(alt); }
        if (!text) { return; }
        var span = document.createElement('span');
        span.className = 'tp-hinweis';
        span.setAttribute('data-tp-hinweis', '1');
        span.textContent = text;
        feld.parentElement.appendChild(span);
    }

    function dialogAnwenden(zone, daten) {
        var form = zone.closest('form');
        if (!form) { return; }
        var felder = { nummer: 'taifun_nummer', datum: 'datum', endbetrag: 'endbetrag' };
        var gelesen = 0;
        Object.keys(felder).forEach(function (key) {
            var feld = form.querySelector('[data-tp-feld="' + key + '"]')
                || form.querySelector('[name="' + felder[key] + '"]');
            if (!feld) { return; }
            var wert = daten[key] || '';
            if (!wert) {
                hinweisAnFeld(feld, '');
                return;
            }
            if (!feld.value || feld.value === feld.defaultValue) {
                feld.value = wert;
                feld.classList.add('tp-aus-pdf');
                hinweisAnFeld(feld, PRUEFEN);
                gelesen += 1;
            } else if (feld.value !== wert) {
                hinweisAnFeld(feld, 'im PDF: ' + wert + ' – bitte prüfen');
            } else {
                hinweisAnFeld(feld, PRUEFEN);
            }
        });
        var sparteZeile = form.querySelector('[data-taifun-sparte]');
        if (sparteZeile) {
            var eigene = sparteZeile.getAttribute('data-sparte') || '';
            if (daten.sparte) {
                var name = SPARTEN[daten.sparte] || daten.sparte;
                sparteZeile.textContent = 'Im PDF erkannt: ' + name
                    + (eigene && eigene !== daten.sparte
                        ? ' – diese Erfassung ist ' + (SPARTEN[eigene] || eigene) + ', bitte prüfen'
                        : ' (nur Vorschlag)');
                sparteZeile.hidden = false;
            } else {
                sparteZeile.hidden = true;
            }
        }
        var text = daten.text_gefunden
            ? (gelesen ? gelesen + ' Feld(er) aus dem PDF vorbelegt – bitte prüfen.' : 'PDF gelesen – keine neuen Werte übernommen.')
            : 'Kein Text im PDF gefunden – Felder bitte von Hand ausfüllen.';
        if (daten.hinweis) { text += ' ' + daten.hinweis; }
        status(zone, (daten.dateiname ? daten.dateiname + ': ' : '') + text, !daten.text_gefunden);
    }

    /* --- TAIFUN-Eintrag: Ersetzen + „übernehmen“-Häkchen ---------------------------------- */

    function eintragAnwenden(zone, daten) {
        var form = zone.closest('form');
        var block = form ? form.querySelector('[data-taifun-ergebnis]') : null;
        if (!form || !block) { return; }
        var werte = { nummer: daten.nummer || '', datum: daten.datum || '', endbetrag: daten.endbetrag || '' };
        if (werte.datum) {
            var teile = werte.datum.split('-');
            if (teile.length === 3) { werte.datum = teile[2] + '.' + teile[1] + '.' + teile[0]; }
        }
        if (werte.endbetrag) { werte.endbetrag += ' €'; }
        Object.keys(werte).forEach(function (key) {
            var anzeige = block.querySelector('[data-feld="' + key + '"]');
            var haken = block.querySelector('[data-uebernehmen="' + key + '"]');
            if (anzeige) { anzeige.textContent = werte[key] || 'nicht erkannt'; }
            if (haken) {
                haken.disabled = !werte[key];
                haken.checked = !!werte[key];
            }
        });
        var name = block.querySelector('[data-feld="dateiname"]');
        if (name) { name.textContent = daten.dateiname || ''; }
        var ersetzt = block.querySelector('[data-feld="ersetzt-hinweis"]');
        if (ersetzt) {
            ersetzt.textContent = zone.getAttribute('data-ersetzen') === '1'
                ? '– ersetzt das vorhandene PDF beim Speichern' : '';
        }
        var hinweis = block.querySelector('[data-feld="hinweis"]');
        if (hinweis) {
            var text = daten.text_gefunden ? (daten.hinweis || '') : 'Kein Text im PDF gefunden – es wird nur das PDF gespeichert.';
            hinweis.textContent = text;
            hinweis.hidden = !text;
        }
        block.hidden = false;
        status(zone, '', false);
    }

    function eintragZuruecksetzen(zone) {
        var form = zone.closest('form');
        if (!form) { return; }
        var block = form.querySelector('[data-taifun-ergebnis]');
        if (block) { block.hidden = true; }
        var best = form.querySelector('[data-taifun-bestaetigt]');
        if (best) { best.value = '0'; }
        eingabeLeeren(zone);
        status(zone, '', false);
    }

    /* --- gemeinsamer Ablauf nach Auswahl/Ablegen ----------------------------------------- */

    function verarbeiten(zone, datei) {
        var modus = zone.getAttribute('data-modus') || 'dialog';
        var fehler = dateiPruefen(datei);
        if (fehler) {
            eingabeLeeren(zone);
            if (modus === 'eintrag') { eintragZuruecksetzen(zone); }
            status(zone, fehler, true);
            return;
        }
        if (modus === 'eintrag' && zone.getAttribute('data-ersetzen') === '1') {
            if (!window.confirm('Am Eintrag liegt bereits ein TAIFUN-PDF. Durch „' + datei.name + '“ ersetzen?')) {
                eintragZuruecksetzen(zone);
                return;
            }
            var form = zone.closest('form');
            var best = form ? form.querySelector('[data-taifun-bestaetigt]') : null;
            if (best) { best.value = '1'; }
        }
        status(zone, 'PDF wird gelesen …', false);
        lesen(zone, datei).then(function (daten) {
            if (modus === 'eintrag') { eintragAnwenden(zone, daten); } else { dialogAnwenden(zone, daten); }
        }).catch(function (problem) {
            status(zone, (problem && problem.message) || 'PDF konnte nicht gelesen werden.', true);
            if (modus === 'eintrag') {
                var form2 = zone.closest('form');
                var block = form2 ? form2.querySelector('[data-taifun-ergebnis]') : null;
                if (block) { block.hidden = false; }
            }
        });
    }

    function init(zone) {
        var feld = eingabeFeld(zone);
        if (!feld) { return; }
        zone.classList.add('tp-aktiv');
        feld.addEventListener('change', function () {
            if (feld.files && feld.files[0]) { verarbeiten(zone, feld.files[0]); }
        });
        zone.addEventListener('click', function (ev) {
            if (ev.target === feld || ev.target.closest('input, a, button, label')) { return; }
            feld.click();
        });
        zone.addEventListener('keydown', function (ev) {
            if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); feld.click(); }
        });
        zone.addEventListener('dragover', function (ev) {
            ev.preventDefault();
            if (ev.dataTransfer) { ev.dataTransfer.dropEffect = 'copy'; }
            zone.classList.add('drop');
        });
        zone.addEventListener('dragleave', function () { zone.classList.remove('drop'); });
        zone.addEventListener('drop', function (ev) {
            ev.preventDefault();
            zone.classList.remove('drop');
            var dateien = ev.dataTransfer ? ev.dataTransfer.files : null;
            if (!dateien || !dateien.length) { return; }
            if (dateien.length > 1) { status(zone, 'Bitte nur EIN PDF ablegen.', true); return; }
            if (!dateiSetzen(zone, dateien[0])) {
                status(zone, 'Ablegen wird von diesem Browser nicht unterstützt – bitte über „auswählen“.', true);
                return;
            }
            verarbeiten(zone, dateien[0]);
        });
        var form = zone.closest('form');
        var abbrechen = form ? form.querySelector('[data-taifun-abbrechen]') : null;
        if (abbrechen) {
            abbrechen.addEventListener('click', function () { eintragZuruecksetzen(zone); });
        }
    }

    window.taifunPdfAbsenden = function (form) {
        var feld = form.querySelector('input[type="file"]');
        if (!feld || !feld.files || !feld.files.length) {
            window.alert('Bitte zuerst ein TAIFUN-PDF ablegen oder auswählen.');
            return false;
        }
        return true;
    };

    function start() {
        Array.prototype.forEach.call(document.querySelectorAll('[data-taifun-dropzone]'), init);
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', start);
    } else {
        start();
    }
})();
