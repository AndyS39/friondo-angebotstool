/* v35 (PLAN_LEAD_V6 Phase 186, Agent G): Fotos je Objekt – Upload direkt an der Objektkarte der
   Kundenkartei (Makro objekt_fotos in kartei_objekte.html, Block .lk-objektfotos).
   - „Foto aufnehmen“ (input capture=environment) oder „Fotos wählen“ (multiple): die Dateien werden
     sofort nach der Auswahl hochgeladen – vorher auf dem Gerät verkleinert (bild_verkleinern.js,
     2000 px / JPEG 85 %; HEIC kann der Browser meist nicht dekodieren → unverändert senden, der
     Server wandelt nach JPG), Bilder über 10 MB werden gar nicht erst gesendet.
   - EIN Request je Auswahl: POST <data-url> (Feld dateien, Accept: application/json), Fortschritt
     über XMLHttpRequest; die Antwort liefert die komplette Fotoliste des Objekts (fotos[]), die
     Kacheln werden ohne Seitenneuladen neu gezeichnet (Lightbox v28 über pjLightbox).
   - Löschen: Klick auf ✕ (Formular der Kachel) → confirm → POST …/loeschen per fetch, Kacheln neu.
   - Ohne JavaScript bleibt das Formular mit dem Knopf „Hochladen“ nutzbar (Redirect).
   Reines Browser-Skript, DOM-Aufbau ohne innerHTML, nur Markup/Tokens aus lm_v35_g.css. */
(function () {
    'use strict';

    function $(sel, wurzel) { return (wurzel || document).querySelector(sel); }
    function $$(sel, wurzel) { return Array.prototype.slice.call((wurzel || document).querySelectorAll(sel)); }

    function maxBytes(box) {
        var mb = parseInt(box.getAttribute('data-max-mb') || '10', 10);
        return (isNaN(mb) || mb <= 0 ? 10 : mb) * 1024 * 1024;
    }

    function status(box, text, fehler) {
        var s = $('.of-status', box);
        if (!s) { return; }
        s.textContent = text || '';
        s.hidden = !text;
        s.classList.toggle('fehler', !!fehler);
    }

    function fortschritt(box, prozent, sichtbar) {
        var p = $('progress.of-fortschritt', box);
        if (!p) { return; }
        p.hidden = !sichtbar;
        p.value = Math.max(0, Math.min(100, prozent || 0));
    }

    function knoepfeSperren(box, gesperrt) {
        $$('input[type=file]', box).forEach(function (i) { i.disabled = gesperrt; });
        $$('.of-knopf', box).forEach(function (k) { k.classList.toggle('gesperrt', gesperrt); });
    }

    function kachelBauen(box, foto, gruppe, zurueck) {
        var fig = document.createElement('figure');
        fig.className = 'of-kachel';
        fig.setAttribute('data-foto', foto.id);
        var a = document.createElement('a');
        a.href = foto.url;
        a.target = '_blank';
        a.className = 'pj-lb-link';
        a.setAttribute('data-lb-gruppe', gruppe);
        a.setAttribute('data-lb-id', foto.id);
        a.setAttribute('data-lb-ordner', foto.ordner || '');
        a.setAttribute('data-lb-name', foto.name || '');
        a.setAttribute('data-lb-datum', foto.datum || '');
        a.setAttribute('data-lb-bemerkung', foto.bemerkung || '');
        a.title = (foto.name || '') + ' · ' + (foto.datum || '');
        a.addEventListener('click', function (ev) {
            if (typeof window.pjLightbox === 'function') { return window.pjLightbox(ev, a); }
            return true;
        });
        var img = document.createElement('img');
        img.src = foto.url;
        img.alt = foto.name || '';
        img.loading = 'lazy';
        a.appendChild(img);
        fig.appendChild(a);
        var cap = document.createElement('figcaption');
        var datum = document.createElement('span');
        datum.className = 'of-datum';
        datum.textContent = foto.kurzdatum || '';
        cap.appendChild(datum);
        if (foto.loeschbar && foto.loeschen_url) {
            var form = document.createElement('form');
            form.method = 'post';
            form.action = foto.loeschen_url;
            form.className = 'of-loeschen-form';
            var versteckt = document.createElement('input');
            versteckt.type = 'hidden';
            versteckt.name = 'zurueck';
            versteckt.value = zurueck || '';
            form.appendChild(versteckt);
            var knopf = document.createElement('button');
            knopf.type = 'submit';
            knopf.className = 'of-loeschen';
            knopf.title = 'Foto löschen';
            knopf.setAttribute('aria-label', 'Foto ' + (foto.name || '') + ' löschen');
            knopf.textContent = '✕';
            form.appendChild(knopf);
            cap.appendChild(form);
        }
        fig.appendChild(cap);
        return fig;
    }

    function rendern(box, fotos) {
        var raster = $('[data-rolle="objektfotos-raster"]', box);
        if (!raster) { return; }
        var gruppe = raster.getAttribute('data-lb-gruppe') || box.getAttribute('data-gruppe') || '';
        var zurueck = box.getAttribute('data-zurueck') || '';
        while (raster.firstChild) { raster.removeChild(raster.firstChild); }
        (fotos || []).forEach(function (f) { raster.appendChild(kachelBauen(box, f, gruppe, zurueck)); });
        var zahl = $('.of-zahl', box);
        if (zahl) { zahl.textContent = (fotos || []).length; }
        var leer = $('.of-leer', box);
        if (leer) { leer.hidden = (fotos || []).length > 0; }
        raster.hidden = !(fotos || []).length;
    }

    function hochladen(box, dateien) {
        if (!dateien.length) { return; }
        var form = $('form.lk-objektfotos-form', box);
        var url = box.getAttribute('data-url') || (form ? form.action : '');
        if (!url) { return; }
        var grenze = maxBytes(box);
        var vorbereiten = (typeof window.bilderVerkleinern === 'function')
            ? window.bilderVerkleinern(dateien) : Promise.resolve(dateien);
        status(box, 'Fotos werden vorbereitet …', false);
        vorbereiten.then(function (liste) {
            var zuGross = [], ok = [];
            liste.forEach(function (d) { (d.size > grenze ? zuGross : ok).push(d); });
            var hinweis = zuGross.length
                ? zuGross.map(function (d) { return d.name; }).join(', ') + ' über ' + Math.round(grenze / 1048576) + ' MB – nicht hochgeladen.'
                : '';
            if (!ok.length) { status(box, hinweis || 'Keine Datei ausgewählt.', true); return; }
            var daten = new FormData();
            daten.append('zurueck', box.getAttribute('data-zurueck') || window.location.pathname);
            ok.forEach(function (d) { daten.append('dateien', d, d.name); });
            var xhr = new XMLHttpRequest();
            knoepfeSperren(box, true);
            fortschritt(box, 0, true);
            status(box, 'Lade ' + ok.length + ' Foto(s) hoch …', false);
            xhr.open('POST', url, true);
            xhr.setRequestHeader('Accept', 'application/json');
            xhr.withCredentials = true;
            if (xhr.upload) {
                xhr.upload.addEventListener('progress', function (ev) {
                    if (ev.lengthComputable) { fortschritt(box, ev.loaded / ev.total * 100, true); }
                });
            }
            xhr.onload = function () {
                knoepfeSperren(box, false);
                fortschritt(box, 100, false);
                var antwort = null;
                try { antwort = JSON.parse(xhr.responseText || 'null'); } catch (e) { antwort = null; }
                if (antwort && Array.isArray(antwort.fotos)) { rendern(box, antwort.fotos); }
                if (xhr.status >= 200 && xhr.status < 300 && antwort) {
                    var text = antwort.meldung || '';
                    if (hinweis) { text = (text ? text + ' ' : '') + hinweis; }
                    status(box, text, !antwort.ok || !!hinweis);
                    return;
                }
                status(box, (antwort && antwort.meldung) ? antwort.meldung
                    : 'Upload fehlgeschlagen (HTTP ' + xhr.status + ') – bitte erneut versuchen.', true);
            };
            xhr.onerror = function () {
                knoepfeSperren(box, false);
                fortschritt(box, 0, false);
                status(box, 'Keine Verbindung – bitte erneut versuchen.', true);
            };
            xhr.send(daten);
        }).catch(function () {
            status(box, 'Fotos konnten nicht vorbereitet werden.', true);
        });
    }

    function loeschen(box, form) {
        if (!window.confirm('Foto löschen?')) { return; }
        var xhr = new XMLHttpRequest();
        xhr.open('POST', form.action, true);
        xhr.setRequestHeader('Accept', 'application/json');
        xhr.withCredentials = true;
        xhr.onload = function () {
            var antwort = null;
            try { antwort = JSON.parse(xhr.responseText || 'null'); } catch (e) { antwort = null; }
            if (antwort && Array.isArray(antwort.fotos)) { rendern(box, antwort.fotos); }
            status(box, antwort && antwort.meldung ? antwort.meldung : 'Löschen fehlgeschlagen.',
                   !(antwort && antwort.ok));
        };
        xhr.onerror = function () { status(box, 'Keine Verbindung – bitte erneut versuchen.', true); };
        var daten = new FormData();
        daten.append('zurueck', box.getAttribute('data-zurueck') || window.location.pathname);
        xhr.send(daten);
    }

    function einrichten(box) {
        if (box._ofInit) { return; }
        box._ofInit = true;
        var form = $('form.lk-objektfotos-form', box);
        if (form) {
            var senden = $('.of-senden', form);
            if (senden) { senden.hidden = true; }   /* mit JavaScript lädt die Auswahl sofort hoch */
            $$('input[type=file]', form).forEach(function (input) {
                input.addEventListener('change', function () {
                    var dateien = Array.prototype.slice.call(input.files || []);
                    input.value = '';
                    hochladen(box, dateien);
                });
            });
            form.addEventListener('submit', function (ev) { ev.preventDefault(); });
        }
        box.addEventListener('submit', function (ev) {
            var f = ev.target;
            if (f && f.classList && f.classList.contains('of-loeschen-form')) {
                ev.preventDefault();
                ev.stopPropagation();
                loeschen(box, f);
            }
        }, true);
        /* Löschen: das confirm des Formulars (onsubmit) würde doppelt fragen – hier übernimmt loeschen() */
        $$('form.of-loeschen-form', box).forEach(function (f) { f.removeAttribute('onsubmit'); });
        new MutationObserver(function () {
            $$('form.of-loeschen-form[onsubmit]', box).forEach(function (f) { f.removeAttribute('onsubmit'); });
        }).observe(box, { childList: true, subtree: true });
    }

    function init() { $$('.lk-objektfotos').forEach(einrichten); }

    if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', init); } else { init(); }
    window.objektfotosV35 = { init: init, einrichten: einrichten, rendern: rendern };
})();
