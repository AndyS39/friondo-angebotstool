/* v35 (PLAN_LEAD_V6 Phase 185, Agent R): „Mein Profil“ – quadratischer Zuschnitt des
   Profilbilds im Browser (Canvas, Mitte des Bildes, 512 px Kante, JPEG 0,9) mit Vorschau,
   bevor das Formular abgeschickt wird. Der Server (app/profilbild.py) prüft und schneidet
   noch einmal – das Skript ist Komfort (kleinere Übertragung, sofortige Vorschau).
   Reines Browser-Skript ohne Framework; ohne DataTransfer/Canvas bleibt die Originaldatei. */
(function () {
    'use strict';

    var form = document.getElementById('profil-bild-form');
    var feld = document.getElementById('profil-bild-datei');
    var vorschau = document.getElementById('profil-vorschau');
    var wrap = document.getElementById('profil-bild-wrap');
    var hinweis = document.getElementById('profil-zuschnitt-hinweis');
    if (!form || !feld) { return; }
    var KANTE = parseInt(form.getAttribute('data-kante'), 10) || 512;
    var MAX_BYTES = parseInt(form.getAttribute('data-max-bytes'), 10) || (2 * 1024 * 1024);
    var QUALITAET = 0.9;

    function sagen(text, fehler) {
        if (!hinweis) { return; }
        hinweis.textContent = text || '';
        hinweis.hidden = !text;
        hinweis.classList.toggle('lm-rot', !!fehler);
    }

    function istBild(datei) {
        return !!datei && (datei.type === 'image/jpeg' || datei.type === 'image/png');
    }

    function bitmapLaden(datei) {
        if (typeof createImageBitmap === 'function') {
            return createImageBitmap(datei, { imageOrientation: 'from-image' }).catch(function () {
                return createImageBitmap(datei);
            });
        }
        return new Promise(function (ok, nein) {
            var bild = new Image();
            var url = URL.createObjectURL(datei);
            bild.onload = function () { URL.revokeObjectURL(url); ok(bild); };
            bild.onerror = function () { URL.revokeObjectURL(url); nein(new Error('Bild nicht lesbar')); };
            bild.src = url;
        });
    }

    function zuschneiden(datei) {
        return bitmapLaden(datei).then(function (bitmap) {
            var b = bitmap.width, h = bitmap.height;
            var kante = Math.min(b, h);
            var links = Math.floor((b - kante) / 2), oben = Math.floor((h - kante) / 2);
            var ziel = document.createElement('canvas');
            var groesse = Math.min(KANTE, kante);
            ziel.width = groesse;
            ziel.height = groesse;
            var ctx = ziel.getContext('2d');
            ctx.drawImage(bitmap, links, oben, kante, kante, 0, 0, groesse, groesse);
            if (bitmap.close) { bitmap.close(); }
            return new Promise(function (ok) {
                ziel.toBlob(function (blob) {
                    if (!blob) { ok(null); return; }
                    var name = (datei.name || 'profil').replace(/\.[^.]+$/, '') + '.jpg';
                    ok({ datei: new File([blob], name, { type: 'image/jpeg', lastModified: Date.now() }),
                         url: ziel.toDataURL('image/jpeg', QUALITAET), kante: kante, quelle: [b, h] });
                }, 'image/jpeg', QUALITAET);
            });
        });
    }

    function vorschauZeigen(url) {
        if (!vorschau) { return; }
        vorschau.src = url;
        vorschau.hidden = false;
        if (wrap) {
            var initialen = wrap.querySelector('.profil-avatar');
            if (initialen) { initialen.hidden = true; }
            wrap.setAttribute('data-hat-bild', '1');
        }
    }

    feld.addEventListener('change', function () {
        var datei = feld.files && feld.files[0];
        if (!datei) { sagen(''); return; }
        if (!istBild(datei)) { sagen('Bitte eine JPG- oder PNG-Datei wählen.', true); return; }
        if (datei.size > MAX_BYTES * 4) {
            // sehr große Originale werden zwar verkleinert, aber der Hinweis bleibt ehrlich
            sagen('Die Datei ist sehr groß – sie wird vor dem Hochladen verkleinert.', false);
        }
        if (typeof DataTransfer === 'undefined' || !document.createElement('canvas').getContext) {
            sagen('Das Bild wird auf dem Server quadratisch zugeschnitten.', false);
            return;
        }
        zuschneiden(datei).then(function (ergebnis) {
            if (!ergebnis) { sagen('Das Bild wird auf dem Server quadratisch zugeschnitten.', false); return; }
            try {
                var dt = new DataTransfer();
                dt.items.add(ergebnis.datei);
                feld.files = dt.files;
            } catch (e) { /* Browser ohne Zuweisung: Original bleibt, Server schneidet zu */ }
            vorschauZeigen(ergebnis.url);
            if (ergebnis.datei.size > MAX_BYTES) {
                sagen('Auch verkleinert ist das Bild größer als erlaubt – bitte ein kleineres Bild wählen.', true);
            } else {
                sagen('Vorschau: quadratischer Ausschnitt aus der Mitte (' + ergebnis.kante + ' × ' + ergebnis.kante
                      + ' px des Originals ' + ergebnis.quelle[0] + ' × ' + ergebnis.quelle[1] + ' px). Mit „Bild speichern“ übernehmen.', false);
            }
        }).catch(function () {
            sagen('Bild konnte nicht gelesen werden – bitte eine andere Datei wählen.', true);
        });
    });
})();
