/* v38 (PLAN_V23 Phase 201, Agent G): Offline-Zwischenspeicher der Galerie-Sammelbox.
   Schlägt ein Upload wegen fehlendem Netz fehl (Netzfehler, Timeout, Status 0), legt galerie_v34.js die
   bereits verkleinerten Dateien (Blob) mit Ordner, Bemerkung, Sparte, Vorgangs-ID, Seitentitel und
   Zeitstempel hier ab – IndexedDB `friondo_galerie_puffer`, Store `wartend` (läuft über http, braucht kein
   HTTPS). Der Puffer liegt nur im jeweiligen Browser des Geräts; es gibt KEINEN Upload im Hintergrund
   (kein Service Worker): beim nächsten Öffnen einer Seite mit der Galerie desselben Vorgangs zeigt
   galerie_v38.js den Hinweiskasten „n Fotos warten auf Upload“ mit „Jetzt hochladen“ / „Verwerfen“, die
   Startseite der mobilen Erfassung die Zeile „Wartende Fotos: Vorgang … (n)“.
   Grenzen je Browser: MAX_ANZAHL Fotos oder MAX_BYTES [ANNAHME laut Plan: 50 Fotos / 100 MB] – darüber
   meldet hinzufuegen() den Fehler „voll“ („Zwischenspeicher voll, bitte zuerst hochladen“).
   Reines Browser-Skript (ES5, Promises), keine externen Bibliotheken; API unter window.galPuffer. */
(function () {
    'use strict';
    var DB_NAME = 'friondo_galerie_puffer';
    var STORE = 'wartend';
    var VERSION = 1;
    var MAX_ANZAHL = 50;                       // [ANNAHME] höchstens 50 wartende Fotos je Browser
    var MAX_BYTES = 100 * 1024 * 1024;         // [ANNAHME] höchstens 100 MB je Browser
    var FEHLER_VORGANG = 'Vorgang nicht mehr vorhanden';

    function verfuegbar() {
        try { return typeof indexedDB !== 'undefined' && indexedDB !== null; } catch (e) { return false; }
    }

    function oeffnen() {
        return new Promise(function (ok, fehler) {
            if (!verfuegbar()) { fehler(new Error('IndexedDB nicht verfügbar')); return; }
            var anfrage;
            try { anfrage = indexedDB.open(DB_NAME, VERSION); } catch (e) { fehler(e); return; }
            anfrage.onupgradeneeded = function () {
                var db = anfrage.result;
                if (!db.objectStoreNames.contains(STORE)) {
                    var store = db.createObjectStore(STORE, { keyPath: 'id', autoIncrement: true });
                    store.createIndex('vorgang', 'vorgang_id', { unique: false });
                }
            };
            anfrage.onsuccess = function () { ok(anfrage.result); };
            anfrage.onerror = function () { fehler(anfrage.error || new Error('IndexedDB')); };
            anfrage.onblocked = function () { fehler(new Error('IndexedDB blockiert')); };
        });
    }

    /* arbeit(store, setzen) läuft in einer Transaktion; setzen(wert) legt das Ergebnis fest. */
    function transaktion(modus, arbeit) {
        return oeffnen().then(function (db) {
            return new Promise(function (ok, fehler) {
                var ergebnis;
                var tx;
                try { tx = db.transaction(STORE, modus); } catch (e) { db.close(); fehler(e); return; }
                tx.oncomplete = function () { db.close(); ok(ergebnis); };
                tx.onerror = function () { db.close(); fehler(tx.error || new Error('IndexedDB')); };
                tx.onabort = function () { db.close(); fehler(tx.error || new Error('IndexedDB abgebrochen')); };
                try {
                    arbeit(tx.objectStore(STORE), function (wert) { ergebnis = wert; });
                } catch (e) {
                    try { tx.abort(); } catch (e2) { /* egal */ }
                    fehler(e);
                }
            });
        });
    }

    function alle() {
        return transaktion('readonly', function (store, setzen) {
            var anfrage = store.getAll();
            anfrage.onsuccess = function () { setzen(anfrage.result || []); };
        });
    }

    function liste(vorgangId) {
        var nummer = Number(vorgangId);
        return alle().then(function (eintraege) {
            return eintraege.filter(function (e) { return Number(e.vorgang_id) === nummer; });
        });
    }

    function bytesVon(eintraege) {
        return eintraege.reduce(function (summe, e) { return summe + (Number(e.groesse) || 0); }, 0);
    }

    /* eintraege: [{vorgang_id, sparte, ordner, bemerkung, name, typ, blob, titel}] → Promise<ids[]>;
       Fehler „voll“ (error.name === 'voll'), wenn Anzahl oder Bytes die Grenze überschreiten. */
    function hinzufuegen(eintraege) {
        var neue = (eintraege || []).filter(function (e) { return e && e.blob; });
        if (!neue.length) { return Promise.resolve([]); }
        return alle().then(function (vorhanden) {
            var bytesNeu = neue.reduce(function (s, e) { return s + (e.blob.size || 0); }, 0);
            if (vorhanden.length + neue.length > MAX_ANZAHL || bytesVon(vorhanden) + bytesNeu > MAX_BYTES) {
                var voll = new Error('Zwischenspeicher voll, bitte zuerst hochladen');
                voll.name = 'voll';
                throw voll;
            }
            return transaktion('readwrite', function (store, setzen) {
                var ids = [];
                neue.forEach(function (e) {
                    var satz = {
                        vorgang_id: Number(e.vorgang_id) || 0,
                        sparte: e.sparte || 'WP',
                        ordner: e.ordner || '',
                        bemerkung: e.bemerkung || '',
                        name: e.name || (e.blob.name || 'foto.jpg'),
                        typ: e.typ || e.blob.type || 'application/octet-stream',
                        groesse: e.blob.size || 0,
                        blob: e.blob,
                        titel: e.titel || '',
                        zeit: e.zeit || Date.now(),
                        fehler: ''
                    };
                    var anfrage = store.add(satz);
                    anfrage.onsuccess = function () { ids.push(anfrage.result); setzen(ids.slice()); };
                });
                setzen(ids);
            });
        });
    }

    function entfernen(ids) {
        var liste_ = (ids || []).map(Number).filter(function (n) { return n > 0; });
        if (!liste_.length) { return Promise.resolve(0); }
        return transaktion('readwrite', function (store, setzen) {
            liste_.forEach(function (id) { store.delete(id); });
            setzen(liste_.length);
        });
    }

    function aktualisieren(id, felder) {
        return transaktion('readwrite', function (store, setzen) {
            var anfrage = store.get(Number(id));
            anfrage.onsuccess = function () {
                var satz = anfrage.result;
                if (!satz) { setzen(false); return; }
                Object.keys(felder || {}).forEach(function (k) { satz[k] = felder[k]; });
                store.put(satz);
                setzen(true);
            };
        });
    }

    function markierenVorgangFehlt(ids) {
        return Promise.all((ids || []).map(function (id) {
            return aktualisieren(id, { fehler: FEHLER_VORGANG });
        }));
    }

    /* Je Vorgang: {vorgang_id, titel, anzahl, bytes, aelteste, fehler} – für die Zeile auf /erfassung */
    function zusammenfassung() {
        return alle().then(function (eintraege) {
            var je = {};
            eintraege.forEach(function (e) {
                var k = String(e.vorgang_id);
                if (!je[k]) {
                    je[k] = { vorgang_id: Number(e.vorgang_id), titel: e.titel || '', anzahl: 0, bytes: 0,
                              aelteste: e.zeit, fehler: '' };
                }
                je[k].anzahl += 1;
                je[k].bytes += Number(e.groesse) || 0;
                if (e.zeit < je[k].aelteste) { je[k].aelteste = e.zeit; }
                if (e.titel && !je[k].titel) { je[k].titel = e.titel; }
                if (e.fehler) { je[k].fehler = e.fehler; }
            });
            return Object.keys(je).map(function (k) { return je[k]; }).sort(function (a, b) {
                return a.aelteste - b.aelteste;
            });
        });
    }

    function zweistellig(n) { return (n < 10 ? '0' : '') + n; }

    /* „14.10., 16:32“ für den Hinweiskasten („seit …“) */
    function zeitText(zeit) {
        var d = new Date(zeit);
        if (isNaN(d.getTime())) { return ''; }
        return zweistellig(d.getDate()) + '.' + zweistellig(d.getMonth() + 1) + '., '
            + zweistellig(d.getHours()) + ':' + zweistellig(d.getMinutes());
    }

    /* Blob + Metadaten → File für die Sammelbox (FormData braucht den Dateinamen) */
    function alsDatei(eintrag) {
        try {
            return new File([eintrag.blob], eintrag.name || 'foto.jpg',
                            { type: eintrag.typ || eintrag.blob.type || 'image/jpeg', lastModified: eintrag.zeit || Date.now() });
        } catch (e) {
            return eintrag.blob;
        }
    }

    function geaendert() {
        try {
            document.dispatchEvent(new CustomEvent('gal38:puffer-geaendert', { bubbles: true }));
        } catch (e) { /* alte Browser ohne CustomEvent-Konstruktor */ }
    }

    window.galPuffer = {
        verfuegbar: verfuegbar,
        alle: alle,
        liste: liste,
        hinzufuegen: hinzufuegen,
        entfernen: entfernen,
        aktualisieren: aktualisieren,
        markierenVorgangFehlt: markierenVorgangFehlt,
        zusammenfassung: zusammenfassung,
        zeitText: zeitText,
        alsDatei: alsDatei,
        geaendert: geaendert,
        FEHLER_VORGANG: FEHLER_VORGANG,
        MAX_ANZAHL: MAX_ANZAHL,
        MAX_BYTES: MAX_BYTES,
        DB_NAME: DB_NAME,
        STORE: STORE
    };
})();
