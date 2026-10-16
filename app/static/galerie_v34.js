/* v34 (PLAN_V21 Phase 181): Galerie – mehrere Fotos, verschiedene Ordner, EIN Upload + Kamera-Serie.
   Gehört zur Sammelbox-Komponente in _galerie.html (Makro sammelbox, Klasse .pj-gal-sammel.gal34):
   - „Fotos aufnehmen“ (input capture=environment) oder „Dateien wählen“ (multiple) füllen eine Liste
     mit Vorschaubild, Dateiname/Größe, Ordner-Dropdown und Bemerkung je Datei; der Kamera-Knopf
     heißt ab dem ersten Foto „Weiteres Foto“ (Kamera-Serie – die Fotos bleiben bis zum Upload im
     Speicher der Seite, kein Zwischen-Upload, Hinweis beim Verlassen der Seite).
   - Bilder werden beim Hinzufügen auf dem Gerät verkleinert (bild_verkleinern.js, 2000 px / JPEG 85 %;
     PDFs unverändert).
   - Modus „upload“ (Vorgangs-/Projektakte, Montage-Backend): „Hochladen (n)“ sendet EINEN Request
     an POST /vorgaenge/<id>/galerie/upload (dateien, datei_ordner, datei_bemerkung positionsgleich,
     Accept: application/json), Fortschritt über XMLHttpRequest, Teilerfolg je Datei: erfolgreich
     abgelegte Zeilen verschwinden, fehlgeschlagene bleiben mit Grund stehen; „Abbrechen“ lässt die
     Liste stehen.
   - Modus „formular“ (mobile Erfassung, Seite Einschätzung): die Dateien werden je Ordner in die
     versteckten Felder galerie_<i> des Seitenformulars gelegt (DataTransfer) und mit „Weiter“ gesendet –
     die Serverroute der Erfassung bleibt unverändert.
   v38 (PLAN_V23 Phase 201, Agent G): Knopf „Hochladen (n)“ (bei 0 deaktiviert) öffnet vor dem Senden
   das Pop-up „Fotos werden hochgeladen“ (Makro galerie_upload_dialog in _galerie.html): Fortschritt je
   Datei und gesamt (aus dem Byte-Anteil des EINEN Requests abgeleitet – Multipart-Reihenfolge =
   Listenreihenfolge [ANNAHME]), Zeile „Voraussichtlich noch ca. N Sekunden“ (Startwert 500 KB/s
   [ANNAHME]; ab der ersten fertigen Datei die gemessene Geschwindigkeit, Aktualisierung alle 2 s,
   unter 5 s „Gleich fertig“), kein Schließen während des Uploads (Esc abgefangen), „Abbrechen“ bricht
   den Request ab (Liste bleibt). Danach „3 Fotos hochgeladen“ (Erfolgsfarbe, schließt nach 3 s, Liste
   leer, Galerie-Kacheln ohne Neuladen – Ereignis gal34:hochgeladen für galerie_v38.js) oder „2 von 3 Fotos
   hochgeladen“ (Warnfarbe, fehlgeschlagene Dateien mit Grund, „Erneut versuchen“ sendet nur diese).
   Netzfehler/Timeout/Status 0 → „Kein Netz. Die Fotos bleiben gespeichert und werden später
   hochgeladen.“ – die Dateien wandern in den Offline-Zwischenspeicher (galerie_puffer.js, IndexedDB),
   die Liste wird geleert, der Hinweiskasten der Galerie übernimmt („Jetzt hochladen“ → dateienHinzufuegen
   + hochladen). HTTP 403/404 beim Upload aus dem Puffer → Einträge bleiben mit „Vorgang nicht mehr
   vorhanden“. Keine Seitennavigation mehr nach dem Upload (bis v37: window.location = ziel).
   Nur Browser-Skript; Markup/CSS in _galerie.html, galerie_v34.css und galerie_v38.css (Tokens). */
(function () {
    'use strict';
    var MAX_DATEIEN = 60;   // [ANNAHME] Obergrenze je Sammel-Upload (Speicher des Handys)
    var START_BYTES_JE_S = 500 * 1024;       // [ANNAHME] Startwert der Dauer-Schätzung: 500 KB/s
    var DAUER_TAKT_MS = 2000;                // Anzeige der Restdauer alle 2 Sekunden
    var GLEICH_FERTIG_S = 5;                 // unter 5 Sekunden „Gleich fertig“
    var SCHLIESSEN_NACH_MS = 3000;           // Erfolgs-Pop-up schließt nach 3 Sekunden
    var UPLOAD_TIMEOUT_MS = 10 * 60 * 1000;  // [ANNAHME] Timeout des Requests (gilt als „Kein Netz“)
    var KEIN_NETZ = 'Kein Netz. Die Fotos bleiben gespeichert und werden später hochgeladen.';
    var PUFFER_VOLL = 'Zwischenspeicher voll, bitte zuerst hochladen';

    function zustand(box) {
        if (!box._gal34) { box._gal34 = { dateien: [], laufend: 0, xhr: null, gesendet: false, lauf: null }; }
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

    function fotosText(anzahl, nurBilder) {
        if (nurBilder) { return anzahl + (anzahl === 1 ? ' Foto' : ' Fotos'); }
        return anzahl + (anzahl === 1 ? ' Datei' : ' Dateien');
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

    /* v38: bereits verkleinerte Dateien aus dem Offline-Zwischenspeicher (Hinweiskasten „Jetzt
       hochladen“) in die Liste legen – eintraege: [{datei (File), ordner, bemerkung, puffer_id}] */
    function dateienHinzufuegen(box, eintraege) {
        var st = zustand(box);
        var liste = box.querySelector('.gal34-liste');
        var frei = Math.max(0, MAX_DATEIEN - st.dateien.length);
        (eintraege || []).slice(0, frei).forEach(function (e) {
            if (!e || !e.datei) { return; }
            var eintrag = { datei: e.datei, name: e.datei.name || e.name || 'foto.jpg',
                            ordner: e.ordner || hauptOrdner(box), bemerkung: e.bemerkung || '',
                            fehler: '', puffer_id: e.puffer_id || null };
            st.dateien.push(eintrag);
            liste.appendChild(zeileBauen(box, eintrag));
        });
        aktualisieren(box);
        sync(box);
        return st.dateien.length;
    }

    function aktualisieren(box) {
        var st = zustand(box);
        var n = st.dateien.length;
        var fuss = box.querySelector('.fuss');
        if (fuss) { fuss.hidden = n === 0; }
        var zahl = box.querySelector('.zahl');
        if (zahl) { zahl.textContent = n; }
        /* v38: „Hochladen (n)“ bei 0 deaktiviert */
        var hoch = box.querySelector('.gal34-hochladen');
        if (hoch && !st.xhr) { hoch.disabled = n === 0; }
        var kameraText = box.querySelector('.gal34-kamera-text');
        if (kameraText) {
            kameraText.textContent = n ? (kameraText.getAttribute('data-weiter') || 'Weiteres Foto')
                                       : (kameraText.getAttribute('data-start') || 'Fotos aufnehmen');
        }
        var liste = box.querySelector('.gal34-liste');
        if (liste) { liste.hidden = n === 0; }
        if (!n) { statusText(box, '', false); }
        ereignis(box, 'gal34:liste', { anzahl: n });
    }

    function statusText(box, text, fehler) {
        var s = box.querySelector('.gal34-status');
        if (!s) { return; }
        s.textContent = text || '';
        s.hidden = !text;
        s.classList.toggle('fehler', !!fehler);
    }

    function ereignis(box, name, detail) {
        try {
            box.dispatchEvent(new CustomEvent(name, { bubbles: true, detail: detail || {} }));
        } catch (e) { /* Browser ohne CustomEvent-Konstruktor */ }
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
        var st = zustand(box);
        var hoch = box.querySelector('.gal34-hochladen');
        var abbr = box.querySelector('.gal34-abbrechen');
        var leer = box.querySelector('.gal34-leeren');
        if (hoch) { hoch.disabled = laufend || !st.dateien.length; }
        if (abbr) { abbr.hidden = !laufend; }
        if (leer) { leer.disabled = laufend; }
    }

    /* ---- v38: Pop-up „Fotos werden hochgeladen“ ---------------------------------------------- */

    function dialogVon(box) { return box.querySelector('dialog.gal38-dialog'); }

    function dauerText(sekunden) {
        if (sekunden < GLEICH_FERTIG_S) { return 'Gleich fertig …'; }
        if (sekunden >= 120) { return 'Voraussichtlich noch ca. ' + Math.ceil(sekunden / 60) + ' Minuten'; }
        return 'Voraussichtlich noch ca. ' + Math.ceil(sekunden) + ' Sekunden';
    }

    function dialogTitel(lauf, text, art) {
        var dlg = lauf.dlg;
        if (!dlg) { return; }
        var t = dlg.querySelector('.gal38-dlg-titel');
        if (t) { t.textContent = text; }
        dlg.classList.remove('erfolg', 'warnung', 'fehler');
        if (art) { dlg.classList.add(art); }
    }

    function dialogKnoepfe(lauf, abbrechen, erneut, schliessen) {
        var dlg = lauf.dlg;
        if (!dlg) { return; }
        var a = dlg.querySelector('.gal38-dlg-abbrechen');
        var e = dlg.querySelector('.gal38-dlg-erneut');
        var s = dlg.querySelector('.gal38-dlg-schliessen');
        if (a) { a.hidden = !abbrechen; }
        if (e) { e.hidden = !erneut; }
        if (s) { s.hidden = !schliessen; }
    }

    function dialogMeldung(lauf, text) {
        var m = lauf.dlg && lauf.dlg.querySelector('.gal38-dlg-meldung');
        if (!m) { return; }
        m.textContent = text || '';
        m.hidden = !text;
    }

    function dialogDauer(lauf, text) {
        var d = lauf.dlg && lauf.dlg.querySelector('.gal38-dlg-dauer');
        if (!d) { return; }
        d.textContent = text || '';
        d.hidden = !text;
    }

    function dialogStart(box, gesendet) {
        var dlg = dialogVon(box);
        var gesamt = gesendet.reduce(function (s, e) { return s + (e.datei.size || 0); }, 0);
        var lauf = { box: box, dlg: dlg, dateien: gesendet, gesamt: gesamt, start: Date.now(),
                     geladen: 0, total: 0, timer: null, zeilen: [], ersteFertig: false, offen: true };
        if (!dlg) { return lauf; }
        dialogTitel(lauf, 'Fotos werden hochgeladen', '');
        var container = dlg.querySelector('.gal38-dlg-dateien');
        var vorlage = dlg.querySelector('template.gal38-dlg-vorlage');
        if (container) {
            container.textContent = '';
            gesendet.forEach(function (e) {
                var zeile;
                if (vorlage && vorlage.content) {
                    zeile = vorlage.content.firstElementChild.cloneNode(true);
                } else {
                    zeile = document.createElement('div');
                    zeile.className = 'gal38-dlg-zeile';
                }
                var name = zeile.querySelector('.gal38-dlg-name');
                if (name) { name.textContent = e.name; name.title = e.name; }
                var stand = zeile.querySelector('.gal38-dlg-stand');
                if (stand) { stand.textContent = groesseText(e.datei.size); }
                container.appendChild(zeile);
                lauf.zeilen.push(zeile);
            });
        }
        var gesamtBalken = dlg.querySelector('.gal38-dlg-gesamt');
        if (gesamtBalken) { gesamtBalken.hidden = false; gesamtBalken.value = 0; }
        var fehlerListe = dlg.querySelector('.gal38-dlg-fehler');
        if (fehlerListe) { fehlerListe.textContent = ''; fehlerListe.hidden = true; }
        dialogMeldung(lauf, '');
        dialogDauer(lauf, dauerText(gesamt / START_BYTES_JE_S));
        dialogKnoepfe(lauf, true, false, false);
        if (!dlg.open) {
            try { dlg.showModal(); } catch (e) { dlg.setAttribute('open', ''); }
        }
        lauf.timer = setInterval(function () { dauerAktualisieren(lauf); }, DAUER_TAKT_MS);
        return lauf;
    }

    function geschwindigkeit(lauf) {
        var sekunden = (Date.now() - lauf.start) / 1000;
        if (sekunden <= 0 || lauf.geladen <= 0) { return START_BYTES_JE_S; }
        var gemessen = lauf.geladen / sekunden;
        if (lauf.ersteFertig) { return gemessen; }
        /* [ANNAHME] vor der ersten fertigen Datei gilt der Startwert – außer die Messung liegt nach dem
           ersten Takt schon DARUNTER (langsames Netz): dann nie zu optimistisch „Gleich fertig“ anzeigen */
        if (sekunden >= DAUER_TAKT_MS / 1000 && gemessen < START_BYTES_JE_S) { return gemessen; }
        return START_BYTES_JE_S;
    }

    function dauerAktualisieren(lauf) {
        if (!lauf.offen) { return; }
        var total = lauf.total || lauf.gesamt;
        var rest = Math.max(0, total - lauf.geladen);
        dialogDauer(lauf, dauerText(rest / geschwindigkeit(lauf)));
    }

    function dialogFortschritt(lauf, geladen, total) {
        lauf.geladen = geladen;
        lauf.total = total;
        var dlg = lauf.dlg;
        if (!dlg) { return; }
        var gesamtBalken = dlg.querySelector('.gal38-dlg-gesamt');
        if (gesamtBalken && total > 0) { gesamtBalken.value = Math.min(100, geladen / total * 100); }
        /* Fortschritt je Datei aus dem Byte-Anteil: der Multipart-Body enthält die Dateien in
           Listenreihenfolge [ANNAHME]; Kopfzeilen-Anteil wird über total/gesamt herausgerechnet */
        var anteil = total > 0 ? Math.min(1, geladen / total) * lauf.gesamt : 0;
        var versatz = 0;
        lauf.dateien.forEach(function (e, i) {
            var groesse = e.datei.size || 0;
            var prozent = groesse > 0 ? Math.max(0, Math.min(100, (anteil - versatz) / groesse * 100)) : 100;
            versatz += groesse;
            var zeile = lauf.zeilen[i];
            if (!zeile) { return; }
            var balken = zeile.querySelector('progress');
            if (balken) { balken.value = prozent; }
            if (i === 0 && prozent >= 100) { lauf.ersteFertig = true; }
            var stand = zeile.querySelector('.gal38-dlg-stand');
            if (stand && prozent >= 100) { stand.textContent = 'übertragen'; }
        });
    }

    function dialogSchliessen(lauf) {
        if (!lauf) { return; }
        lauf.offen = false;
        if (lauf.timer) { clearInterval(lauf.timer); lauf.timer = null; }
        if (lauf.schliessTimer) { clearTimeout(lauf.schliessTimer); lauf.schliessTimer = null; }
        var dlg = lauf.dlg;
        if (dlg) {
            if (dlg.open && typeof dlg.close === 'function') { try { dlg.close(); } catch (e) { /* egal */ } }
            dlg.removeAttribute('open');
        }
        var st = zustand(lauf.box);
        if (st.lauf === lauf) { st.lauf = null; }
    }

    function dialogFertig(lauf, abgelegt, fehler, nurBilder) {
        if (lauf.timer) { clearInterval(lauf.timer); lauf.timer = null; }
        var dlg = lauf.dlg;
        var nOk = abgelegt.length, nAlle = nOk + fehler.length;
        if (!dlg) { return; }
        lauf.zeilen.forEach(function (zeile, i) {
            var balken = zeile.querySelector('progress');
            var stand = zeile.querySelector('.gal38-dlg-stand');
            var f = null;
            fehler.forEach(function (x) { if (x.nr === i) { f = x; } });
            if (f) {
                zeile.classList.add('fehler');
                if (stand) { stand.textContent = f.grund || 'nicht abgelegt'; }
            } else {
                if (balken) { balken.value = 100; }
                if (stand) { stand.textContent = 'hochgeladen'; }
                zeile.classList.add('ok');
            }
        });
        var gesamtBalken = dlg.querySelector('.gal38-dlg-gesamt');
        if (gesamtBalken) { gesamtBalken.value = 100; }
        dialogDauer(lauf, '');
        if (!fehler.length) {
            dialogTitel(lauf, fotosText(nOk, nurBilder) + ' hochgeladen', 'erfolg');
            dialogMeldung(lauf, '');
            dialogKnoepfe(lauf, false, false, true);
            lauf.schliessTimer = setTimeout(function () { dialogSchliessen(lauf); }, SCHLIESSEN_NACH_MS);
            return;
        }
        dialogTitel(lauf, nOk + ' von ' + nAlle + (nurBilder ? ' Fotos' : ' Dateien') + ' hochgeladen', 'warnung');
        var liste = dlg.querySelector('.gal38-dlg-fehler');
        if (liste) {
            liste.textContent = '';
            fehler.forEach(function (f) {
                var li = document.createElement('li');
                li.textContent = (f.name || 'Datei') + ' – ' + (f.grund || 'nicht abgelegt');
                liste.appendChild(li);
            });
            liste.hidden = false;
        }
        dialogMeldung(lauf, 'Nicht hochgeladen:');
        dialogKnoepfe(lauf, false, true, true);
    }

    function dialogFehler(lauf, titel, text, erneut) {
        if (lauf.timer) { clearInterval(lauf.timer); lauf.timer = null; }
        if (!lauf.dlg) { return; }
        dialogTitel(lauf, titel, 'fehler');
        dialogDauer(lauf, '');
        dialogMeldung(lauf, text);
        dialogKnoepfe(lauf, false, !!erneut, true);
    }

    /* ---- v38: Netzfehler → Offline-Zwischenspeicher ------------------------------------------ */

    function seitenTitel() {
        var t = (document.title || '').split(' – ')[0].split(' - ')[0].trim();
        return t;
    }

    function pufferAblegen(box, gesendet) {
        var st = zustand(box);
        var neue = gesendet.filter(function (e) { return !e.puffer_id && st.dateien.indexOf(e) >= 0; });
        if (!window.galPuffer || !window.galPuffer.verfuegbar()) {
            return Promise.resolve({ ok: false, grund: 'kein IndexedDB' });
        }
        var vorgang = Number(box.getAttribute('data-vorgang')) || 0;
        var eintraege = neue.map(function (e) {
            return { vorgang_id: vorgang, sparte: box.getAttribute('data-sparte') || 'WP',
                     ordner: e.ordner || hauptOrdner(box), bemerkung: e.bemerkung || '',
                     name: e.name, typ: e.datei.type, blob: e.datei, titel: seitenTitel() };
        });
        return window.galPuffer.hinzufuegen(eintraege).then(function (ids) {
            neue.forEach(function (e, i) { e.puffer_id = ids[i] || true; });
            /* Liste leeren: die Fotos liegen jetzt im Zwischenspeicher (Hinweiskasten übernimmt) */
            gesendet.forEach(function (e) {
                if (e.puffer_id && st.dateien.indexOf(e) >= 0) { entfernen(box, e); }
            });
            window.galPuffer.geaendert();
            return { ok: true, anzahl: eintraege.length };
        }).catch(function (fehler) {
            /* schon gepufferte Einträge (Upload aus dem Hinweiskasten) bleiben im Puffer – aus der Liste nehmen */
            gesendet.forEach(function (e) {
                if (e.puffer_id && st.dateien.indexOf(e) >= 0) { entfernen(box, e); }
            });
            return { ok: false, grund: fehler && fehler.name === 'voll' ? 'voll' : String(fehler && fehler.message || fehler) };
        });
    }

    function netzFehler(box, lauf, gesendet) {
        var st = zustand(box);
        knoepfe(box, false);
        fortschritt(box, 0, false);
        pufferAblegen(box, gesendet).then(function (ergebnis) {
            if (ergebnis.ok) {
                statusText(box, KEIN_NETZ, true);
                dialogFehler(lauf, 'Upload nicht möglich', KEIN_NETZ, false);
            } else if (ergebnis.grund === 'voll') {
                statusText(box, PUFFER_VOLL + ' – die Liste bleibt erhalten.', true);
                dialogFehler(lauf, 'Upload nicht möglich', 'Kein Netz. ' + PUFFER_VOLL + '.', true);
            } else {
                statusText(box, 'Keine Verbindung – die Liste bleibt erhalten, bitte erneut versuchen.', true);
                dialogFehler(lauf, 'Upload nicht möglich',
                             'Keine Verbindung – die Liste bleibt erhalten, bitte erneut versuchen.', true);
            }
            ereignis(box, 'gal34:kein-netz', { anzahl: gesendet.length, gepuffert: !!ergebnis.ok });
            if (!st.dateien.length) { st.gesendet = true; }
        });
    }

    function pufferEntfernen(gesendet, abgelegt) {
        var ids = [];
        abgelegt.forEach(function (a) {
            var e = gesendet[a.nr];
            if (e && e.puffer_id && e.puffer_id !== true) { ids.push(e.puffer_id); }
        });
        if (ids.length && window.galPuffer) {
            window.galPuffer.entfernen(ids).then(function () { window.galPuffer.geaendert(); })
                .catch(function () { /* bleibt im Puffer, Hinweiskasten zeigt es */ });
        }
    }

    function pufferVorgangFehlt(box, gesendet) {
        var st = zustand(box);
        var ids = [];
        gesendet.forEach(function (e) {
            if (e.puffer_id && e.puffer_id !== true) {
                ids.push(e.puffer_id);
                if (st.dateien.indexOf(e) >= 0) { entfernen(box, e); }
            }
        });
        if (ids.length && window.galPuffer) {
            window.galPuffer.markierenVorgangFehlt(ids).then(function () { window.galPuffer.geaendert(); })
                .catch(function () { /* egal */ });
        }
        return ids.length;
    }

    /* ---- Upload (EIN Request) ------------------------------------------------------------------ */

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
        var nurBilder = gesendet.every(function (e) { return istBild(e.datei); });
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
        var lauf = dialogStart(box, gesendet);
        st.lauf = lauf;
        xhr.open('POST', url, true);
        xhr.setRequestHeader('Accept', 'application/json');
        xhr.withCredentials = true;
        xhr.timeout = UPLOAD_TIMEOUT_MS;
        if (xhr.upload) {
            xhr.upload.addEventListener('progress', function (ev) {
                if (ev.lengthComputable) {
                    fortschritt(box, ev.loaded / ev.total * 100, true);
                    dialogFortschritt(lauf, ev.loaded, ev.total);
                }
            });
        }
        xhr.onload = function () {
            st.xhr = null;
            var antwort = null;
            try { antwort = JSON.parse(xhr.responseText || 'null'); } catch (e) { antwort = null; }
            if (xhr.status === 0) { netzFehler(box, lauf, gesendet); return; }
            if (xhr.status >= 200 && xhr.status < 300 && antwort) {
                fortschritt(box, 100, true);
                dialogFortschritt(lauf, 1, 1);
                var abgelegt = antwort.abgelegt || [];
                var fehler = antwort.fehler || [];
                /* erfolgreiche Zeilen entfernen, fehlgeschlagene bleiben mit Grund stehen */
                abgelegt.forEach(function (a) {
                    var e = gesendet[a.nr];
                    if (e) {
                        var i = st.dateien.indexOf(e);
                        if (i >= 0) { st.dateien.splice(i, 1); }
                        if (e.url) { try { URL.revokeObjectURL(e.url); } catch (x) { /* egal */ } }
                        if (e.zeile) { e.zeile.remove(); }
                    }
                });
                fehler.forEach(function (f) {
                    var e = gesendet[f.nr];
                    if (e && e.zeile) {
                        var g = e.zeile.querySelector('.gal34-groesse');
                        if (g) { g.textContent = 'nicht abgelegt: ' + (f.grund || 'Fehler'); g.classList.add('fehler'); }
                    }
                });
                pufferEntfernen(gesendet, abgelegt);
                aktualisieren(box);
                knoepfe(box, false);
                if (antwort.ok && !st.dateien.length) { st.gesendet = true; }
                statusText(box, antwort.meldung || (fehler.length ? 'Upload teilweise fehlgeschlagen.' : ''), !!fehler.length);
                dialogFertig(lauf, abgelegt, fehler, nurBilder);
                ereignis(box, 'gal34:hochgeladen', { abgelegt: abgelegt, fehler: fehler, antwort: antwort });
                return;
            }
            knoepfe(box, false);
            fortschritt(box, 0, false);
            var meldung = (antwort && antwort.meldung) ? antwort.meldung
                : 'Upload fehlgeschlagen (HTTP ' + xhr.status + ') – die Liste bleibt erhalten, bitte erneut versuchen.';
            if (xhr.status === 403 || xhr.status === 404) {
                /* Upload aus dem Zwischenspeicher: der Vorgang ist weg (archiviert/gelöscht) oder gesperrt –
                   Einträge bleiben im Puffer mit „Vorgang nicht mehr vorhanden“, verwerfbar */
                var markiert = pufferVorgangFehlt(box, gesendet);
                if (markiert) { meldung = window.galPuffer.FEHLER_VORGANG + ' – ' + meldung; }
            }
            statusText(box, meldung, true);
            dialogFehler(lauf, 'Upload fehlgeschlagen', meldung, st.dateien.length > 0);
        };
        xhr.onerror = function () { st.xhr = null; netzFehler(box, lauf, gesendet); };
        xhr.ontimeout = function () { st.xhr = null; netzFehler(box, lauf, gesendet); };
        xhr.onabort = function () {
            st.xhr = null;
            knoepfe(box, false);
            fortschritt(box, 0, false);
            dialogSchliessen(lauf);
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

    function dialogEinrichten(box) {
        var dlg = dialogVon(box);
        if (!dlg || dlg._gal38init) { return; }
        dlg._gal38init = true;
        var st = zustand(box);
        dlg.addEventListener('cancel', function (ev) {
            /* Esc: kein Schließen, solange der Upload läuft */
            if (st.xhr) { ev.preventDefault(); }
        });
        var a = dlg.querySelector('.gal38-dlg-abbrechen');
        if (a) { a.addEventListener('click', function () { abbrechen(box); }); }
        var s = dlg.querySelector('.gal38-dlg-schliessen');
        if (s) { s.addEventListener('click', function () { if (st.lauf) { dialogSchliessen(st.lauf); } else { dlg.close(); } }); }
        var e = dlg.querySelector('.gal38-dlg-erneut');
        if (e) {
            e.addEventListener('click', function () {
                if (st.lauf) { dialogSchliessen(st.lauf); }
                hochladen(box);
            });
        }
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
        dialogEinrichten(box);
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
    window.gal34 = { init: init, einrichten: einrichten, hochladen: hochladen, dateienHinzufuegen: dateienHinzufuegen,
                     entfernen: entfernen, zustand: zustand, dauerText: dauerText, MAX_DATEIEN: MAX_DATEIEN,
                     START_BYTES_JE_S: START_BYTES_JE_S, KEIN_NETZ: KEIN_NETZ };
})();
