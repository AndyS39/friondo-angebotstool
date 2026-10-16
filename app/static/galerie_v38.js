/* v38 (PLAN_V23 Phase 201, Agent G): Galerie – Auswählen-Modus mit Mehrfach-Löschen, Hinweiskasten
   „n Fotos warten auf Upload“, Zeile „Wartende Fotos“ auf /erfassung und neue Vorschaukacheln ohne
   Seitenneuladen. Ergänzt galerie_v34.js (Sammelbox/Upload) – keine eigene Upload-Logik:
   - Auswählen je Ordner (Makro galerie in _galerie.html, .gal38-leiste[data-gal38-leiste=ordner]):
     Kästchen nur an Dateien mit Löschrecht (data-loeschbar – Rolle der Seite oder eigener Upload eines
     Außendienstlers), Kopfleiste „n ausgewählt · Alle · Keine“, „n Fotos löschen“ (Gefahrfarbe) mit
     Sicherheitsabfrage „3 Fotos endgültig löschen? Das lässt sich nicht rückgängig machen.“ →
     POST /vorgaenge/<id>/galerie/loeschen (datei_ids, Accept: application/json) → Kacheln verschwinden,
     Zähler/Vorschau des Ordners werden nachgezogen, abgelehnte IDs werden gemeldet.
   - Auswählen in der Sammelbox (.gal38-leiste[data-gal38-leiste=liste]): „n Fotos entfernen“ nimmt die
     Zeilen nur aus der Upload-Liste (nichts auf dem Server) [ANNAHME].
   - Hinweiskasten (.gal38-wartend): Einträge des Vorgangs aus galerie_puffer.js (IndexedDB), Sparte der
     Galerie bzw. Rückfall auf die erste Galerie der Seite [ANNAHME]; „Jetzt hochladen“ legt die Dateien
     in die Sammelbox (gal34.dateienHinzufuegen) und startet den normalen Upload mit Pop-up; „Verwerfen“
     mit Sicherheitsabfrage; Einträge mit „Vorgang nicht mehr vorhanden“ nur verwerfbar.
   - /erfassung: [data-gal38-puffer-zeile] „Wartende Fotos: Vorgang Müller (3), Vorgang Schmidt (1)“ mit
     Links auf /vorgaenge/<id>#galerie.
   - Ereignis gal34:hochgeladen (galerie_v34.js): abgelegte Dateien als Kacheln an den Ordner hängen
     (Lightbox-Link, Datum, Kästchen bei Löschrecht; Verschieben/Einzel-Löschen erst nach dem nächsten
     Laden der Seite [ANNAHME]).
   Reines Browser-Skript (ES5), keine externen Bibliotheken; Markup/CSS in _galerie.html, galerie_v38.css. */
(function () {
    'use strict';

    function qsa(wurzel, selektor) {
        return Array.prototype.slice.call((wurzel || document).querySelectorAll(selektor));
    }

    function fotosText(anzahl, nurBilder) {
        if (nurBilder) { return anzahl + (anzahl === 1 ? ' Foto' : ' Fotos'); }
        return anzahl + (anzahl === 1 ? ' Datei' : ' Dateien');
    }

    /* ---- Auswählen-Modus ------------------------------------------------------------------------ */

    function bereichVon(leiste) {
        /* Ordner: der Ordnerinhalt (.pj-gal-inhalt); Liste: die Sammelbox */
        if (leiste.getAttribute('data-gal38-leiste') === 'liste') { return leiste.closest('.pj-gal-sammel'); }
        return leiste.closest('.pj-gal-inhalt');
    }

    function kaesten(bereich) {
        return qsa(bereich, '.gal38-kasten');
    }

    function gewaehlt(bereich) {
        return qsa(bereich, '.gal38-kasten input.gal38-wahl').filter(function (k) { return k.checked; });
    }

    function istBildKachel(input) {
        var el = input.closest('figure, .f, .gal34-zeile');
        if (!el) { return true; }
        if (el.classList.contains('gal34-zeile')) {
            var img = el.querySelector('img.gal34-bild');
            return !!img && !img.hidden;
        }
        return el.tagName.toLowerCase() === 'figure';
    }

    function zaehlerAktualisieren(leiste) {
        var bereich = bereichVon(leiste);
        var wahl = gewaehlt(bereich);
        var nurBilder = wahl.every(istBildKachel);
        var zahl = leiste.querySelector('.gal38-auswahl-zahl');
        if (zahl) { zahl.textContent = wahl.length + ' ausgewählt'; }
        var knopf = leiste.querySelector('.gal38-loeschen, .gal38-entfernen');
        if (knopf) {
            knopf.disabled = !wahl.length;
            knopf.textContent = fotosText(wahl.length, nurBilder)
                + (knopf.classList.contains('gal38-entfernen') ? ' entfernen' : ' löschen');
        }
        qsa(bereich, '[data-loeschbar], .gal34-zeile').forEach(function (el) {
            var k = el.querySelector('input.gal38-wahl');
            el.classList.toggle('gal38-gewaehlt', !!(k && k.checked));
        });
    }

    function modusSetzen(leiste, an) {
        var bereich = bereichVon(leiste);
        if (!bereich) { return; }
        var auswahl = leiste.querySelector('.gal38-auswahl-leiste') || bereich.querySelector('.gal38-auswahl-leiste');
        var start = leiste.querySelector('.gal38-auswaehlen') || bereich.querySelector('.gal38-auswaehlen');
        bereich.classList.toggle('gal38-auswahl', !!an);
        kaesten(bereich).forEach(function (k) {
            k.hidden = !an;
            var input = k.querySelector('input');
            if (input && !an) { input.checked = false; }
        });
        if (auswahl) { auswahl.hidden = !an; }
        if (start) { start.hidden = !!an || !kaesten(bereich).length; }
        zaehlerAktualisieren(leiste);
    }

    function alleSetzen(leiste, wert) {
        qsa(bereichVon(leiste), '.gal38-kasten input.gal38-wahl').forEach(function (k) { k.checked = wert; });
        zaehlerAktualisieren(leiste);
    }

    function meldung(leiste, text, fehler) {
        var m = leiste.querySelector('.gal38-meldung');
        if (!m) {
            m = document.createElement('span');
            m.className = 'gal38-meldung dezent';
            leiste.appendChild(m);
        }
        m.textContent = text || '';
        m.hidden = !text;
        m.classList.toggle('fehler', !!fehler);
    }

    function ordnerZaehlen(details) {
        if (!details) { return; }
        var anzahl = qsa(details, '.pj-gal-raster figure[data-datei], .pj-tree .f[data-datei]').length;
        var n = details.querySelector('summary .n');
        if (n) { n.textContent = anzahl; }
        /* Vorschaubild der Ordnerzeile nachziehen */
        var summary = details.querySelector('summary');
        var erstesBild = details.querySelector('.pj-gal-raster figure img');
        var vorschau = summary ? summary.querySelector('img') : null;
        var leer = summary ? summary.querySelector('.pj-gal-leer') : null;
        if (erstesBild) {
            if (vorschau) {
                vorschau.src = erstesBild.getAttribute('src');
            } else if (leer) {
                var img = document.createElement('img');
                img.src = erstesBild.getAttribute('src');
                img.alt = '';
                img.loading = 'lazy';
                leer.parentNode.replaceChild(img, leer);
            }
        } else if (vorschau) {
            var ersatz = document.createElement('span');
            ersatz.className = 'pj-gal-leer';
            ersatz.textContent = '📁';
            vorschau.parentNode.replaceChild(ersatz, vorschau);
        }
        var start = details.querySelector('.gal38-auswaehlen');
        if (start && !details.querySelector('.gal38-auswahl')) {
            start.hidden = !kaesten(details).length;
        }
    }

    function listeEntfernen(leiste) {
        var bereich = bereichVon(leiste);
        var wahl = gewaehlt(bereich);
        if (!wahl.length) { return; }
        if (!window.confirm(fotosText(wahl.length, wahl.every(istBildKachel)) + ' aus der Liste entfernen?')) { return; }
        wahl.forEach(function (k) {
            var zeile = k.closest('.gal34-zeile');
            var weg = zeile && zeile.querySelector('.gal34-weg');
            if (weg) { weg.click(); }
        });
        modusSetzen(leiste, false);
    }

    function galerieLoeschen(leiste) {
        var bereich = bereichVon(leiste);
        var galerie = leiste.closest('[data-gal38]');
        var details = leiste.closest('details.pj-gal-ordner');
        var wahl = gewaehlt(bereich);
        if (!wahl.length || !galerie) { return; }
        var nurBilder = wahl.every(istBildKachel);
        var frage = fotosText(wahl.length, nurBilder) + ' endgültig löschen? Das lässt sich nicht rückgängig machen.';
        if (!window.confirm(frage)) { return; }
        var ids = wahl.map(function (k) { return k.value; });
        var daten = new FormData();
        ids.forEach(function (id) { daten.append('datei_ids', id); });
        daten.append('zurueck', galerie.getAttribute('data-zurueck') || window.location.pathname);
        var knopf = leiste.querySelector('.gal38-loeschen');
        if (knopf) { knopf.disabled = true; }
        meldung(leiste, 'Wird gelöscht …', false);
        var url = galerie.getAttribute('data-loeschen-url') || ('/vorgaenge/' + galerie.getAttribute('data-vorgang') + '/galerie/loeschen');
        fetch(url, { method: 'POST', body: daten, credentials: 'same-origin',
                     headers: { 'Accept': 'application/json' } })
            .then(function (antwort) {
                return antwort.json().then(function (daten_) { return { status: antwort.status, daten: daten_ }; });
            })
            .then(function (ergebnis) {
                var daten_ = ergebnis.daten || {};
                (daten_.geloescht || []).forEach(function (id) {
                    qsa(bereich, '[data-datei="' + id + '"]').forEach(function (el) { el.remove(); });
                });
                ordnerZaehlen(details);
                var abgelehnt = daten_.abgelehnt || [];
                if (abgelehnt.length || ergebnis.status >= 400) {
                    meldung(leiste, daten_.meldung || 'Löschen fehlgeschlagen (HTTP ' + ergebnis.status + ').', true);
                    zaehlerAktualisieren(leiste);
                } else {
                    meldung(leiste, daten_.meldung || '', false);
                    modusSetzen(leiste, false);
                }
                try {
                    document.dispatchEvent(new CustomEvent('gal38:geloescht', { bubbles: true, detail: daten_ }));
                } catch (e) { /* egal */ }
            })
            .catch(function () {
                meldung(leiste, 'Löschen nicht möglich – keine Verbindung.', true);
                zaehlerAktualisieren(leiste);
            });
    }

    function leisteEinrichten(leiste) {
        if (leiste._gal38init) { return; }
        leiste._gal38init = true;
        var art = leiste.getAttribute('data-gal38-leiste');
        var bereich = bereichVon(leiste);
        if (!bereich) { return; }
        var start = leiste.querySelector('.gal38-auswaehlen') || bereich.querySelector('.gal38-auswaehlen');
        if (start) { start.addEventListener('click', function () { modusSetzen(leiste, true); }); }
        var ende = leiste.querySelector('.gal38-auswahl-ende');
        if (ende) { ende.addEventListener('click', function () { modusSetzen(leiste, false); }); }
        var alle = leiste.querySelector('.gal38-alle');
        if (alle) { alle.addEventListener('click', function () { alleSetzen(leiste, true); }); }
        var keine = leiste.querySelector('.gal38-keine');
        if (keine) { keine.addEventListener('click', function () { alleSetzen(leiste, false); }); }
        var loeschen = leiste.querySelector('.gal38-loeschen');
        if (loeschen) { loeschen.addEventListener('click', function () { galerieLoeschen(leiste); }); }
        var entfernen = leiste.querySelector('.gal38-entfernen');
        if (entfernen) { entfernen.addEventListener('click', function () { listeEntfernen(leiste); }); }
        bereich.addEventListener('change', function (ev) {
            if (ev.target && ev.target.classList && ev.target.classList.contains('gal38-wahl')) {
                zaehlerAktualisieren(leiste);
            }
        });
        if (art === 'liste') {
            /* Sammelbox: Knopf nur, wenn Zeilen da sind; leere Liste beendet den Modus */
            bereich.addEventListener('gal34:liste', function (ev) {
                var n = ev.detail ? ev.detail.anzahl : 0;
                if (!n) { modusSetzen(leiste, false); }
                if (start) { start.hidden = !n || bereich.classList.contains('gal38-auswahl'); }
            });
        }
    }

    /* ---- Neue Kacheln nach dem Upload (Ereignis gal34:hochgeladen) ------------------------------ */

    function kachelBauen(galerie, eintrag, gruppe, ordner) {
        var datum = eintrag.datum || '';
        var kannLoeschen = galerie.getAttribute('data-loeschen-alle') === '1'
            || galerie.getAttribute('data-loeschen-eigene') === '1';
        var figure = document.createElement('figure');
        figure.setAttribute('data-datei', eintrag.id);
        figure.setAttribute('data-name', eintrag.name || '');
        figure.classList.add('gal38-neu');
        if (kannLoeschen) {
            figure.setAttribute('data-loeschbar', '1');
            var label = document.createElement('label');
            label.className = 'gal38-kasten';
            label.hidden = true;
            var input = document.createElement('input');
            input.type = 'checkbox';
            input.className = 'gal38-wahl';
            input.value = eintrag.id;
            input.setAttribute('aria-label', (eintrag.name || 'Datei') + ' auswählen');
            label.appendChild(input);
            figure.appendChild(label);
        }
        var a = document.createElement('a');
        a.href = '/vorgaenge/galerie/datei/' + eintrag.id;
        a.target = '_blank';
        a.className = 'pj-lb-link';
        a.setAttribute('data-lb-gruppe', gruppe);
        a.setAttribute('data-lb-id', eintrag.id);
        a.setAttribute('data-lb-ordner', ordner);
        a.setAttribute('data-lb-name', eintrag.name || '');
        a.setAttribute('data-lb-datum', eintrag.datum_lang || '');
        a.setAttribute('data-lb-bemerkung', '');
        a.addEventListener('click', function (ev) {
            if (typeof window.pjLightbox === 'function') { return window.pjLightbox(ev, a); }
            return true;
        });
        var img = document.createElement('img');
        img.src = '/vorgaenge/galerie/datei/' + eintrag.id;
        img.alt = eintrag.name || '';
        img.loading = 'lazy';
        a.appendChild(img);
        figure.appendChild(a);
        var cap = document.createElement('figcaption');
        cap.textContent = datum + ' · neu';
        figure.appendChild(cap);
        return figure;
    }

    function dokumentZeileBauen(galerie, eintrag) {
        var kannLoeschen = galerie.getAttribute('data-loeschen-alle') === '1'
            || galerie.getAttribute('data-loeschen-eigene') === '1';
        var zeile = document.createElement('div');
        zeile.className = 'f gal38-neu';
        zeile.setAttribute('data-datei', eintrag.id);
        zeile.setAttribute('data-name', eintrag.name || '');
        if (kannLoeschen) {
            zeile.setAttribute('data-loeschbar', '1');
            var label = document.createElement('label');
            label.className = 'gal38-kasten gal38-kasten-zeile';
            label.hidden = true;
            var input = document.createElement('input');
            input.type = 'checkbox';
            input.className = 'gal38-wahl';
            input.value = eintrag.id;
            label.appendChild(input);
            zeile.appendChild(label);
        }
        var a = document.createElement('a');
        a.href = '/vorgaenge/galerie/datei/' + eintrag.id;
        a.target = '_blank';
        a.textContent = eintrag.name || 'Datei';
        zeile.appendChild(a);
        var klein = document.createElement('small');
        klein.textContent = (eintrag.datum || '') + ' · neu';
        zeile.appendChild(klein);
        return zeile;
    }

    function kachelnAnhaengen(box, abgelegt) {
        var galerie = box.closest('[data-gal38]');
        if (!galerie || !abgelegt || !abgelegt.length) { return; }
        var vorgang = galerie.getAttribute('data-vorgang') || '';
        var sparte = galerie.getAttribute('data-sparte') || 'WP';
        abgelegt.forEach(function (eintrag) {
            var ordner = eintrag.ordner || 'Allgemein';
            var details = null;
            qsa(galerie, 'details.pj-gal-ordner').forEach(function (d) {
                if (d.getAttribute('data-ordner') === ordner) { details = d; }
            });
            if (!details) { return; }
            var inhalt = details.querySelector('.pj-gal-inhalt');
            var gruppe = details.getAttribute('data-gruppe') || (vorgang + '/' + sparte + '/' + ordner);
            if (eintrag.bild) {
                var raster = inhalt.querySelector('.pj-gal-raster');
                if (!raster) {
                    raster = document.createElement('div');
                    raster.className = 'pj-gal-raster';
                    raster.setAttribute('data-lb-gruppe', gruppe);
                    var leiste = inhalt.querySelector('.gal38-leiste');
                    if (leiste && leiste.nextSibling) { inhalt.insertBefore(raster, leiste.nextSibling); }
                    else { inhalt.insertBefore(raster, inhalt.firstChild); }
                }
                raster.insertBefore(kachelBauen(galerie, eintrag, gruppe, ordner), raster.firstChild);
            } else {
                var baum = inhalt.querySelector('.pj-tree');
                if (!baum) {
                    baum = document.createElement('div');
                    baum.className = 'pj-tree';
                    var upload = inhalt.querySelector('form.pj-gal-upload');
                    if (upload) { inhalt.insertBefore(baum, upload); } else { inhalt.appendChild(baum); }
                }
                baum.insertBefore(dokumentZeileBauen(galerie, eintrag), baum.firstChild);
            }
            details.open = true;
            ordnerZaehlen(details);
        });
    }

    /* ---- Hinweiskasten „n Fotos warten auf Upload“ ---------------------------------------------- */

    function galerien() { return qsa(document, '[data-gal38]'); }

    function kastenFuellen(galerie, eintraege) {
        var kasten = galerie.querySelector('[data-gal38-wartend]');
        if (!kasten) { return; }
        kasten._eintraege = eintraege;
        if (!eintraege.length) { kasten.hidden = true; return; }
        var aelteste = eintraege.reduce(function (min, e) { return e.zeit < min ? e.zeit : min; }, eintraege[0].zeit);
        var fehlerhaft = eintraege.filter(function (e) { return e.fehler; });
        var nurBilder = eintraege.every(function (e) { return (e.typ || '').indexOf('image/') === 0; });
        var text = kasten.querySelector('.gal38-wartend-text');
        var zeit = window.galPuffer ? window.galPuffer.zeitText(aelteste) : '';
        var satz = fotosText(eintraege.length, nurBilder) + ' warten auf Upload' + (zeit ? ' (seit ' + zeit + ')' : '');
        if (fehlerhaft.length === eintraege.length) {
            satz = fotosText(eintraege.length, nurBilder) + ' im Zwischenspeicher – ' + fehlerhaft[0].fehler;
        } else if (fehlerhaft.length) {
            satz += ' – ' + fehlerhaft.length + ' davon: ' + fehlerhaft[0].fehler;
        }
        if (text) { text.textContent = satz; }
        var hoch = kasten.querySelector('.gal38-wartend-hochladen');
        if (hoch) { hoch.hidden = fehlerhaft.length === eintraege.length; }
        kasten.hidden = false;
    }

    function kaestenLaden() {
        if (!window.galPuffer || !window.galPuffer.verfuegbar()) { return Promise.resolve(); }
        var liste = galerien();
        if (!liste.length) { return Promise.resolve(); }
        var vorgaenge = {};
        liste.forEach(function (g) {
            var v = Number(g.getAttribute('data-vorgang')) || 0;
            if (v) { vorgaenge[v] = true; }
        });
        return window.galPuffer.alle().then(function (eintraege) {
            liste.forEach(function (g) {
                var v = Number(g.getAttribute('data-vorgang')) || 0;
                var sparte = g.getAttribute('data-sparte') || 'WP';
                var sparten = liste.filter(function (x) { return Number(x.getAttribute('data-vorgang')) === v; })
                    .map(function (x) { return x.getAttribute('data-sparte') || 'WP'; });
                var erste = liste.filter(function (x) { return Number(x.getAttribute('data-vorgang')) === v; })[0] === g;
                var eigene = eintraege.filter(function (e) {
                    if (Number(e.vorgang_id) !== v) { return false; }
                    if ((e.sparte || 'WP') === sparte) { return true; }
                    /* Sparte ohne Galerie auf dieser Seite → in der ersten Galerie des Vorgangs [ANNAHME] */
                    return erste && sparten.indexOf(e.sparte || 'WP') < 0;
                });
                kastenFuellen(g, eigene);
            });
        }).catch(function () { /* ohne Puffer kein Kasten */ });
    }

    function jetztHochladen(galerie) {
        var kasten = galerie.querySelector('[data-gal38-wartend]');
        var box = galerie.querySelector('.pj-gal-sammel.gal34');
        if (!kasten || !box || !window.gal34 || !window.galPuffer) { return; }
        var eintraege = (kasten._eintraege || []).filter(function (e) { return !e.fehler; });
        if (!eintraege.length) { return; }
        var st = window.gal34.zustand(box);
        var schon = {};
        st.dateien.forEach(function (e) { if (e.puffer_id) { schon[e.puffer_id] = true; } });
        var neu = eintraege.filter(function (e) { return !schon[e.id]; }).map(function (e) {
            return { datei: window.galPuffer.alsDatei(e), ordner: e.ordner, bemerkung: e.bemerkung,
                     name: e.name, puffer_id: e.id };
        });
        window.gal34.dateienHinzufuegen(box, neu);
        /* Ordner-Dropdown je Zeile kennt nur die Ordner dieser Sparte – unbekannte landen serverseitig in „Allgemein“ */
        var hoch = kasten.querySelector('.gal38-wartend-hochladen');
        if (hoch) { hoch.disabled = true; }
        var fertig = function () {
            if (hoch) { hoch.disabled = false; }
            box.removeEventListener('gal34:hochgeladen', fertig);
            box.removeEventListener('gal34:kein-netz', fertig);
        };
        box.addEventListener('gal34:hochgeladen', fertig);
        box.addEventListener('gal34:kein-netz', fertig);
        kasten.hidden = true;
        window.gal34.hochladen(box);
    }

    function verwerfen(galerie) {
        var kasten = galerie.querySelector('[data-gal38-wartend]');
        if (!kasten || !window.galPuffer) { return; }
        var eintraege = kasten._eintraege || [];
        if (!eintraege.length) { return; }
        var nurBilder = eintraege.every(function (e) { return (e.typ || '').indexOf('image/') === 0; });
        if (!window.confirm(fotosText(eintraege.length, nurBilder) + ' aus dem Zwischenspeicher verwerfen? Sie werden nicht hochgeladen.')) { return; }
        window.galPuffer.entfernen(eintraege.map(function (e) { return e.id; })).then(function () {
            window.galPuffer.geaendert();
        }).catch(function () { /* egal */ });
    }

    function kastenEinrichten(galerie) {
        var kasten = galerie.querySelector('[data-gal38-wartend]');
        if (!kasten || kasten._gal38init) { return; }
        kasten._gal38init = true;
        var hoch = kasten.querySelector('.gal38-wartend-hochladen');
        if (hoch) { hoch.addEventListener('click', function () { jetztHochladen(galerie); }); }
        var weg = kasten.querySelector('.gal38-wartend-verwerfen');
        if (weg) { weg.addEventListener('click', function () { verwerfen(galerie); }); }
    }

    /* ---- Zeile „Wartende Fotos“ auf /erfassung ------------------------------------------------- */

    function pufferZeileFuellen() {
        var zeile = document.querySelector('[data-gal38-puffer-zeile]');
        if (!zeile || !window.galPuffer || !window.galPuffer.verfuegbar()) { return Promise.resolve(); }
        return window.galPuffer.zusammenfassung().then(function (gruppen) {
            var liste = zeile.querySelector('.gal38-puffer-liste');
            if (!liste) { return; }
            liste.textContent = '';
            if (!gruppen.length) { zeile.hidden = true; return; }
            gruppen.forEach(function (g, i) {
                if (i) { liste.appendChild(document.createTextNode(', ')); }
                var a = document.createElement('a');
                a.href = '/vorgaenge/' + g.vorgang_id + '#galerie';
                var name = g.titel && g.titel.indexOf('Vorgang') === 0 ? g.titel : 'Vorgang ' + (g.titel || ('#' + g.vorgang_id));
                a.textContent = name + ' (' + g.anzahl + ')';
                liste.appendChild(a);
                if (g.fehler) {
                    var s = document.createElement('span');
                    s.className = 'gal38-puffer-fehler';
                    s.textContent = ' – ' + g.fehler;
                    liste.appendChild(s);
                }
            });
            zeile.hidden = false;
        }).catch(function () { /* ohne Puffer keine Zeile */ });
    }

    /* ---- Start ---------------------------------------------------------------------------------- */

    function init() {
        qsa(document, '[data-gal38-leiste]').forEach(leisteEinrichten);
        galerien().forEach(kastenEinrichten);
        kaestenLaden();
        pufferZeileFuellen();
    }

    document.addEventListener('gal34:hochgeladen', function (ev) {
        var box = ev.target;
        if (!box || !box.classList || !box.classList.contains('pj-gal-sammel')) { return; }
        kachelnAnhaengen(box, ev.detail && ev.detail.abgelegt);
    });
    document.addEventListener('gal38:puffer-geaendert', function () {
        kaestenLaden();
        pufferZeileFuellen();
    });

    if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', init); } else { init(); }
    window.gal38 = { init: init, kaestenLaden: kaestenLaden, pufferZeileFuellen: pufferZeileFuellen,
                     kachelnAnhaengen: kachelnAnhaengen, modusSetzen: modusSetzen };
})();
