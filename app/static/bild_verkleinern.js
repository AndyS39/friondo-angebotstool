/* v33-Nachtrag (15.10.2026, Entscheidung zur Meldung der Vertriebler „Foto-Upload dauert extrem lange“):
   Fotos werden VOR dem Upload auf dem Gerät verkleinert – längste Kante 2000 px, JPEG 0,85 (dieselbe
   Grenze wie galerie.MAX_KANTE auf dem Server, also kein Qualitätsverlust gegenüber heute), typisch
   300–600 KB statt 3–12 MB je Foto über LTE/VPN. Dateien unter 400 KB, Nicht-Bilder und nicht
   dekodierbare Formate (z. B. HEIC ohne Browser-Unterstützung) bleiben unverändert.
   Wirkung: (1) jedes Formular mit Datei-Feldern (Galerie-Upload, Montage-Foto, Formular-Fotos) wird beim
   Absenden abgefangen, die Bilder werden ersetzt (DataTransfer), dann wird das Formular normal gesendet;
   (2) die Foto-Sammelbox (_galerie.html) ruft bildVerkleinern() beim Hinzufügen und lädt Foto für Foto
   mit Fortschrittsanzeige hoch. Reines Browser-Skript, ohne Server-Änderung. */
(function () {
    'use strict';
    var MAX_KANTE = 2000;
    var QUALITAET = 0.85;
    var SCHWELLE_BYTES = 400 * 1024;

    function istBild(datei) {
        return !!datei && typeof datei.type === 'string' && datei.type.indexOf('image/') === 0
            && datei.type !== 'image/svg+xml' && datei.type !== 'image/gif';
    }

    function neuerName(name) {
        var punkt = name.lastIndexOf('.');
        return (punkt > 0 ? name.slice(0, punkt) : name) + '.jpg';
    }

    function bitmapLaden(datei) {
        if (typeof createImageBitmap === 'function') {
            return createImageBitmap(datei, { imageOrientation: 'from-image' }).catch(function () {
                return createImageBitmap(datei);
            });
        }
        return new Promise(function (ok, fehler) {
            var bild = new Image();
            var url = URL.createObjectURL(datei);
            bild.onload = function () { URL.revokeObjectURL(url); ok(bild); };
            bild.onerror = function () { URL.revokeObjectURL(url); fehler(new Error('Bild nicht lesbar')); };
            bild.src = url;
        });
    }

    function bildVerkleinern(datei) {
        if (!istBild(datei)) { return Promise.resolve(datei); }
        return bitmapLaden(datei).then(function (bitmap) {
            var breite = bitmap.width, hoehe = bitmap.height;
            var faktor = Math.min(1, MAX_KANTE / Math.max(breite, hoehe));
            if (faktor >= 1 && datei.size <= SCHWELLE_BYTES) {
                if (bitmap.close) { bitmap.close(); }
                return datei;
            }
            var ziel = document.createElement('canvas');
            ziel.width = Math.max(1, Math.round(breite * faktor));
            ziel.height = Math.max(1, Math.round(hoehe * faktor));
            var ctx = ziel.getContext('2d');
            ctx.drawImage(bitmap, 0, 0, ziel.width, ziel.height);
            if (bitmap.close) { bitmap.close(); }
            return new Promise(function (ok) {
                ziel.toBlob(function (blob) {
                    if (!blob || blob.size >= datei.size) { ok(datei); return; }
                    ok(new File([blob], neuerName(datei.name), { type: 'image/jpeg', lastModified: datei.lastModified || Date.now() }));
                }, 'image/jpeg', QUALITAET);
            });
        }).catch(function () { return datei; });
    }

    function bilderVerkleinern(dateien) {
        var liste = Array.prototype.slice.call(dateien || []);
        return Promise.all(liste.map(bildVerkleinern));
    }

    function formularVerkleinern(form) {
        var felder = Array.prototype.slice.call(form.querySelectorAll('input[type=file]'))
            .filter(function (f) { return f.files && f.files.length && Array.prototype.some.call(f.files, istBild); });
        if (!felder.length || typeof DataTransfer === 'undefined') { return Promise.resolve(false); }
        return Promise.all(felder.map(function (feld) {
            return bilderVerkleinern(feld.files).then(function (neu) {
                var dt = new DataTransfer();
                neu.forEach(function (d) { dt.items.add(d); });
                try { feld.files = dt.files; } catch (e) { /* Browser ohne Zuweisung: Original bleibt */ }
            });
        })).then(function () { return true; });
    }

    document.addEventListener('submit', function (ev) {
        var form = ev.target;
        if (!(form instanceof HTMLFormElement) || form.dataset.bilderVerkleinert === '1') { return; }
        if (!form.querySelector('input[type=file]')) { return; }
        var hatBild = Array.prototype.some.call(form.querySelectorAll('input[type=file]'), function (f) {
            return f.files && Array.prototype.some.call(f.files, istBild);
        });
        if (!hatBild) { return; }
        ev.preventDefault();
        var knopf = ev.submitter || form.querySelector('button[type=submit], input[type=submit]');
        if (knopf) { knopf.disabled = true; }
        formularVerkleinern(form).then(function () {
            form.dataset.bilderVerkleinert = '1';
            if (knopf) { knopf.disabled = false; }
            if (typeof form.requestSubmit === 'function') { form.requestSubmit(knopf || undefined); }
            else { form.submit(); }
        });
    }, true);

    window.bildVerkleinern = bildVerkleinern;
    window.bilderVerkleinern = bilderVerkleinern;
    window.formularBilderVerkleinern = formularVerkleinern;
})();
