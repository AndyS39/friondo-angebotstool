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

    document.addEventListener("DOMContentLoaded", function () {
        // Zuweisungs-Dropdown: Rückfrage + Absenden
        document.querySelectorAll("form.hv-zuweisung select[name=ad_id]").forEach(function (select) {
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
            var key = gruppe.getAttribute("data-hv") || "";
            if (key in zustand) { gruppe.open = !!zustand[key]; }
            gruppe.addEventListener("toggle", function () { merken(key, gruppe.open); });
        });
        document.querySelectorAll("[data-hv-klappen]").forEach(function (knopf) {
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
            form.addEventListener("submit", function (ereignis) {
                if (!window.confirm(form.getAttribute("data-bestaetigen"))) { ereignis.preventDefault(); }
            });
        });
    });
})();
