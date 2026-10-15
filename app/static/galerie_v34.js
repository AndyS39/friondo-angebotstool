/* v34 (PLAN_V21 Phase 181): Galerie – mehrere Fotos, verschiedene Ordner, EIN Upload + Kamera-Serie.
   Gehört zur Sammelbox-Komponente in _galerie.html (Makro sammelbox, Klasse .pj-gal-sammel.gal34):
   - „Fotos aufnehmen“ (input capture=environment) oder „Dateien wählen“ (multiple) füllen eine Liste
     mit Vorschaubild, Dateiname/Größe, Ordner-Dropdown und Bemerkung je Datei; der Kamera-Knopf
     heißt ab dem ersten Foto „Weiteres Foto“ (Kamera-Serie – die Fotos bleiben bis zum Upload im
     Speicher der Seite, kein Zwischen-Upload, Hinweis beim Verlassen der Seite).
   - Bilder werden beim Hinzufügen auf dem Gerät verkleinert (bild_verkleinern.js, 2000 px / JPEG 85 %;
     PDFs unverändert).
   - Modus „upload“ (Vorgangs-/Projektakte, Montage-Backend): „n Fotos hochladen“ sendet EINEN Request
     an POST /vorgaenge/<id>/galerie/upload (dateien, datei_ordner, datei_bemerkung positionsgleich,
     Accept: application/json), Fortschrittsbalken über XMLHttpRequest, Teilerfolg je Datei: erfolgreich
     abgelegte Zeilen verschwinden, fehlgeschlagene bleiben mit Grund stehen; „Abbrechen“ lässt die
     Liste stehen.
   - Modus „formular“ (mobile Erfassung, Seite Einschätzung): die Dateien werden je Ordner in die
     versteckten Felder galerie_<i> des Seitenformulars gelegt (DataTransfer) und mit „Weiter“ gesendet –
     die Serverroute der Erfassung bleibt unverändert.
   Nur Browser-Skript; Markup/CSS in _galerie.html und galerie_v34.css (Tokens). */
(function () {
    'use strict';
    var MAX_DATEIEN = 60;   // [ANNAHME] Obergrenze je Sammel-Upload (Speicher des Handys)

    function zustand(box) {
        if (!box._gal34) { box._gal34 = { dateien: [], laufend: 0, xhr: null, gesendet: false }; }
        return box._gal34;
    }

    function groesseText(bytes) {
        if (!bytes && bytes !== 0) { return ''; }
        if (bytes < 1024 * 1024) { return Math.max(1, Math.round(bytes / 1024)) + ' KB'; }
        return (Math.round(bytes / (1024 * 1024) * 10) / 10).toString().replace('.', ',') + ' MB';
    }

    function istBild(datei) {
        return !!datei && typeof datei.type === 'string' && datei.type.indexOf('image/') === 0;
    }

    function hauptOrdner(box) {
        var sel = box.querySelector('.haupt-ordner');
        return sel ? sel.value : '';
    }

    function zeileBauen(box, eintrag) {
        var vorlage = box.querySelector('template.gal34-vorlage');
        var zeile;
        if (vorlage && vorlage.content) {
            zeile = vorlage.content.firstElementChild.cloneNode(true);
        } else {
            zeile = document.createElement('div');
            zeile.className = 'gal34-zeile';
        }
        var bild = zeile.querySelector('img');
        var doku = zeile.querySelector('.gal34-doku');
        if (istBild(eintrag.datei)) {
            if (bild) {
                eintrag.url = URL.createObjectURL(eintrag.datei);
                bild.src = eintrag.url;
                bild.alt = eintrag.name;
            }
            if (doku) { doku.hidden = true; }
        } else {
            if (bild) { bild.hidden = true; }
            if (doku) { doku.hidden = false; }
        }
        var name = zeile.querySelector('.gal34-name');
        if (name) { name.textContent = eintrag.name; name.title = eintrag.name; }
        var groesse = zeile.querySelector('.gal34-groesse');
        if (groesse) { groesse.textContent = groesseText(eintrag.datei.size); }
        var wahl = zeile.querySelector('select');
        if (wahl) {
            wahl.value = eintrag.ordner;
            if (wahl.value !== eintrag.ordner && wahl.options.length) { eintrag.ordner = wahl.value; }
            wahl.addEventListener('change', function () { eintrag.ordner = wahl.value; sync(box); });
        }
        var bemerkung = zeile.querySelector('input.gal34-bemerkung');
        if (bemerkung) {
            bemerkung.value = eintrag.bemerkung || '';
            bemerkung.addEventListener('input', function () { eintrag.bemerkung = bemerkung.value; });
        }
        var weg = zeile.querySelector('.gal34-weg');
        if (weg) {
            weg.addEventListener('click', function () { entfernen(box, eintrag); });
        }
        eintrag.zeile = zeile;
        return zeile;
    }

    function entfernen(box, eintrag) {
        var st = zustand(box);
        var i = st.dateien.indexOf(eintrag);
        if (i >= 0) { st.dateien.splice(i, 1); }
        if (eintrag.url) { try { URL.revokeObjectURL(eintrag.url); } catch (e) { /* egal */ } }
        if (eintrag.zeile) { eintrag.zeile.remove(); }
        aktualisieren(box);
        sync(box);
    }

    function hinzufuegen(box, input) {
        var st = zustand(box);
        var neue = Array.prototype.slice.call(input.files || []);
        input.value = '';
        if (!neue.length) { return; }
        if (st.dateien.length + neue.length > MAX_DATEIEN) {
            statusText(box, 'Höchstens ' + MAX_DATEIEN + ' Dateien je Upload – bitte zuerst hochladen.', true);
            neue = neue.slice(0, Math.max(0, MAX_DATEIEN - st.dateien.length));
        }
        var liste = box.querySelector('.gal34-liste');
        neue.forEach(function (datei) {
            var eintrag = { datei: datei, name: datei.name, ordner: hauptOrdner(box), bemerkung: '', fehler: '' };
            st.dateien.push(eintrag);
            liste.appendChild(zeileBauen(box, eintrag));
            if (window.bildVerkleinern && istBild(datei)) {
                st.laufend += 1;
                window.bildVerkleinern(datei).then(function (klein) {
                    eintrag.datei = klein || datei;
                    var g = eintrag.zeile && eintrag.zeile.querySelector('.gal34-groesse');
                    if (g) { g.textContent = groesseText(eintrag.datei.size); }
                }).catch(function () { /* Original bleibt */ }).then(function () {
                    st.laufend -= 1;
                    sync(box);
                });
            }
        });
        aktualisieren(box);
        sync(box);
    }

    function aktualisieren(box) {
        var st = zustand(box);
        var n = st.dateien.length;
        var fuss = box.querySelector('.fuss');
        if (fuss) { fuss.hidden = n === 0; }
        var zahl = box.querySelector('.zahl');
        if (zahl) { zahl.textContent = n; }
        var kameraText = box.querySelector('.gal34-kamera-text');
        if (kameraText) {
            kameraText.textContent = n ? (kameraText.getAttribute('data-weiter') || 'Weiteres Foto')
                                       : (kameraText.getAttribute('data-start') || 'Fotos aufnehmen');
        }
        var liste = box.querySelector('.gal34-liste');
        if (liste) { liste.hidden = n === 0; }
        if (!n) { statusText(box, '', false); }
    }

    function statusText(box, text, fehler) {
        var s = box.querySelector('.gal34-status');
        if (!s) { return; }
        s.textContent = text || '';
        s.hidden = !text;
        s.classList.toggle('fehler', !!fehler);
    }

    function alleUebernehmen(box) {
        var st = zustand(box);
        var ordner = hauptOrdner(box);
        var bem = box.querySelector('.fuss input.bemerkung');
        st.dateien.forEach(function (e) {
            e.ordner = ordner;
            var sel = e.zeile && e.zeile.querySelector('select');
            if (sel) { sel.value = ordner; }
            if (bem && bem.value) {
                e.bemerkung = bem.value;
                var feld = e.zeile && e.zeile.querySelector('input.gal34-bemerkung');
                if (feld) { feld.value = bem.value; }
            }
        });
        sync(box);
    }

    /* Modus formular: Dateien je Ordner in die versteckten Felder des Seitenformulars legen */
    function sync(box) {
        if (box.getAttribute('data-modus') !== 'formular' || typeof DataTransfer === 'undefined') { return; }
        var st = zustand(box);
        var ziele = box.querySelectorAll('input.gal34-ziel[data-ordner]');
        Array.prototype.forEach.call(ziele, function (ziel) {
            var dt = new DataTransfer();
            st.dateien.forEach(function (e) {
                if (e.ordner === ziel.getAttribute('data-ordner')) { dt.items.add(e.datei); }
            });
            try { ziel.files = dt.files; } catch (e) { /* Browser ohne Zuweisung */ }
        });
        var form = box.closest('form');
        if (form) { form.dataset.bilderVerkleinert = '1'; }   /* bereits verkleinert – bild_verkleinern.js überspringt */
    }

    function fortschritt(box, prozent, sichtbar) {
        var p = box.querySelector('progress.gal34-fortschritt');
        if (!p) { return; }
        p.hidden = !sichtbar;
        p.value = Math.max(0, Math.min(100, prozent || 0));
    }

    function knoepfe(box, laufend) {
        var hoch = box.querySelector('.gal34-hochladen');
        var abbr = box.querySelector('.gal34-abbrechen');
        var leer = box.querySelector('.gal34-leeren');
        if (hoch) { hoch.disabled = laufend; }
        if (abbr) { abbr.hidden = !laufend; }
        if (leer) { leer.disabled = laufend; }
    }

    function hochladen(box) {
        var st = zustand(box);
        if (!st.dateien.length || st.xhr) { return; }
        if (st.laufend) {
            statusText(box, 'Fotos werden noch verkleinert …', false);
            setTimeout(function () { hochladen(box); }, 150);
            return;
        }
        var url = box.getAttribute('data-upload-url') || ('/vorgaenge/' + box.getAttribute('data-vorgang') + '/galerie/upload');
        var daten = new FormData();
        daten.append('ordner', hauptOrdner(box));
        daten.append('sparte', box.getAttribute('data-sparte') || 'WP');
        daten.append('zurueck', box.getAttribute('data-zurueck') || window.location.pathname);
        var bem = box.querySelector('.fuss input.bemerkung');
        daten.append('bemerkung', bem ? bem.value : '');
        var gesendet = st.dateien.slice();
        gesendet.forEach(function (e) {
            daten.append('dateien', e.datei, e.datei.name);
            daten.append('datei_ordner', e.ordner || '');
            daten.append('datei_bemerkung', e.bemerkung || '');
        });
        var xhr = new XMLHttpRequest();
        st.xhr = xhr;
        knoepfe(box, true);
        fortschritt(box, 0, true);
        statusText(box, 'Lade ' + gesendet.length + ' Datei(en) hoch …', false);
        xhr.open('POST', url, true);
        xhr.setRequestHeader('Accept', 'application/json');
        xhr.withCredentials = true;
        if (xhr.upload) {
            xhr.upload.addEventListener('progress', function (ev) {
                if (ev.lengthComputable) { fortschritt(box, ev.loaded / ev.total * 100, true); }
            });
        }
        xhr.onload = function () {
            st.xhr = null;
            var antwort = null;
            try { antwort = JSON.parse(xhr.responseText || 'null'); } catch (e) { antwort = null; }
            if (xhr.status >= 200 && xhr.status < 300 && antwort) {
                fortschritt(box, 100, true);
                /* erfolgreiche Zeilen entfernen, fehlgeschlagene bleiben mit Grund stehen */
                (antwort.abgelegt || []).forEach(function (a) {
                    var e = gesendet[a.nr];
                    if (e) {
                        var i = st.dateien.indexOf(e);
                        if (i >= 0) { st.dateien.splice(i, 1); }
                        if (e.zeile) { e.zeile.remove(); }
                    }
                });
                (antwort.fehler || []).forEach(function (f) {
                    var e = gesendet[f.nr];
                    if (e && e.zeile) {
                        var g = e.zeile.querySelector('.gal34-groesse');
                        if (g) { g.textContent = 'nicht abgelegt: ' + (f.grund || 'Fehler'); g.classList.add('fehler'); }
                    }
                });
                aktualisieren(box);
                if (antwort.ok && !st.dateien.length) {
                    st.gesendet = true;
                    window.location = antwort.ziel || (box.getAttribute('data-zurueck') || window.location.pathname) + '#galerie';
                    return;
                }
                knoepfe(box, false);
                statusText(box, antwort.meldung || 'Upload teilweise fehlgeschlagen.', true);
                return;
            }
            knoepfe(box, false);
            fortschritt(box, 0, false);
            statusText(box, (antwort && antwort.meldung) ? antwort.meldung
                       : 'Upload fehlgeschlagen (HTTP ' + xhr.status + ') – die Liste bleibt erhalten, bitte erneut versuchen.', true);
        };
        xhr.onerror = function () {
            st.xhr = null;
            knoepfe(box, false);
            fortschritt(box, 0, false);
            statusText(box, 'Keine Verbindung – die Liste bleibt erhalten, bitte erneut versuchen.', true);
        };
        xhr.onabort = function () {
            st.xhr = null;
            knoepfe(box, false);
            fortschritt(box, 0, false);
            statusText(box, 'Upload abgebrochen – die Liste bleibt erhalten.', false);
        };
        xhr.send(daten);
    }

    function abbrechen(box) {
        var st = zustand(box);
        if (st.xhr) { st.xhr.abort(); }
    }

    function leeren(box) {
        var st = zustand(box);
        if (st.xhr) { return; }
        st.dateien.slice().forEach(function (e) { entfernen(box, e); });
    }

    function einrichten(box) {
        if (box._gal34init) { return; }
        box._gal34init = true;
        zustand(box);
        Array.prototype.forEach.call(box.querySelectorAll('input[type=file][data-gal34]'), function (input) {
            input.addEventListener('change', function () { hinzufuegen(box, input); });
        });
        var alle = box.querySelector('.gal34-alle');
        if (alle) { alle.addEventListener('click', function () { alleUebernehmen(box); }); }
        var hoch = box.querySelector('.gal34-hochladen');
        if (hoch) { hoch.addEventListener('click', function () { hochladen(box); }); }
        var abbr = box.querySelector('.gal34-abbrechen');
        if (abbr) { abbr.addEventListener('click', function () { abbrechen(box); }); }
        var leer = box.querySelector('.gal34-leeren');
        if (leer) { leer.addEventListener('click', function () { leeren(box); }); }
        var haupt = box.querySelector('.haupt-ordner');
        if (haupt) {
            haupt.addEventListener('change', function () {
                /* neue Dateien bekommen den Standard-Ordner; bestehende Zeilen bleiben */
            });
        }
        var form = box.closest('form');
        if (form && box.getAttribute('data-modus') === 'formular') {
            form.addEventListener('submit', function () { zustand(box).gesendet = true; });
        }
        aktualisieren(box);
    }

    function alleBoxen() {
        return Array.prototype.slice.call(document.querySelectorAll('.pj-gal-sammel.gal34'));
    }

    function init() { alleBoxen().forEach(einrichten); }

    window.addEventListener('beforeunload', function (ev) {
        var offen = alleBoxen().some(function (box) {
            var st = zustand(box);
            return st.dateien.length && !st.gesendet && !st.xhr;
        });
        if (offen) {
            ev.preventDefault();
            ev.returnValue = 'Es liegen noch nicht hochgeladene Fotos in der Liste.';
            return ev.returnValue;
        }
        return undefined;
    });

    if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', init); } else { init(); }
    window.gal34 = { init: init, einrichten: einrichten, hochladen: hochladen, MAX_DATEIEN: MAX_DATEIEN };
})();
