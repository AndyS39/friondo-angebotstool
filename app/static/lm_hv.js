/* Lead-Management V2 (v23) – Phase 109 Handelsvertreter (vanilla, kein
   Framework). 1) Dropdown „Vertreter“: Rückfrage vor der Umverteilung, dann
   Absenden; 2) Gruppen je Vertreter auf-/zuklappen, Zustand je Gruppe im
   Browser merken; 3) Rückfrage vor „Standard nachziehen“. */
(function () {
    "use strict";
    var SPEICHER = "lm_hv_gruppen";

    function gespeichert() {
        try { return JSON.parse(localStorage.getItem(SPEICHER) || "{}"); } catch (e) { return {}; }
    }
    function merken(key, offen) {
        try {
            var alle = gespeichert();
            alle[key] = offen ? 1 : 0;
            localStorage.setItem(SPEICHER, JSON.stringify(alle));
        } catch (e) { /* privater Modus – egal */ }
    }

    // v35 (PLAN_LEAD_V6 Phase 186, Agent B): init() läuft beim Laden und erneut nach der
    // Sofortsuche bzw. nach einer ersetzten Zeile (document „lm-sofort:geladen“) – jedes
    // Element wird nur einmal verdrahtet (data-lm-hv-init)
    function init() {
        // Zuweisungs-Dropdown: Rückfrage + Absenden
        document.querySelectorAll("form.hv-zuweisung select[name=ad_id]").forEach(function (select) {
            if (select.dataset.lmHvInit === "1") { return; }
            select.dataset.lmHvInit = "1";
            select.addEventListener("change", function () {
                var neu = select.options[select.selectedIndex];
                var text = neu.value
                    ? "Lead an " + neu.text + " geben? (Aktivität + Glocke an den Vertreter)"
                    : "Zuweisung entfernen?";
                if (window.confirm(text)) {
                    select.form.submit();
                } else {
                    select.value = select.getAttribute("data-aktuell") || "";
                }
            });
        });

        // Gruppen: gemerkten Zustand anwenden + Änderungen merken
        var zustand = gespeichert();
        document.querySelectorAll("details.hv-gruppe").forEach(function (gruppe) {
            if (gruppe.dataset.lmHvInit === "1") { return; }
            gruppe.dataset.lmHvInit = "1";
            var key = gruppe.getAttribute("data-hv") || "";
            if (key in zustand) { gruppe.open = !!zustand[key]; }
            gruppe.addEventListener("toggle", function () { merken(key, gruppe.open); });
        });
        document.querySelectorAll("[data-hv-klappen]").forEach(function (knopf) {
            if (knopf.dataset.lmHvInit === "1") { return; }
            knopf.dataset.lmHvInit = "1";
            knopf.addEventListener("click", function () {
                var offen = knopf.getAttribute("data-hv-klappen") === "auf";
                document.querySelectorAll("details.hv-gruppe").forEach(function (gruppe) {
                    gruppe.open = offen;
                    merken(gruppe.getAttribute("data-hv") || "", offen);
                });
            });
        });

        // Rückfragen (Standard nachziehen)
        document.querySelectorAll("form[data-bestaetigen]").forEach(function (form) {
            if (form.dataset.lmHvInit === "1") { return; }
            form.dataset.lmHvInit = "1";
            form.addEventListener("submit", function (ereignis) {
                if (!window.confirm(form.getAttribute("data-bestaetigen"))) { ereignis.preventDefault(); }
            });
        });
    }
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
    document.addEventListener("lm-sofort:geladen", init);
})();
