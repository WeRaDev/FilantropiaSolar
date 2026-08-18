/**
 * Filantropia public stations Leaflet map.
 * Expects window.FS_STATIONS (array) and #fs-stations-map.
 * Optional: .fs-station-list-item[data-station-id|data-lat|data-lng] for list->map focus.
 */
(function () {
    function esc(t) {
        return String(t == null ? "" : t)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function absUrl(raw) {
        var w = String(raw || "").trim();
        if (!w) {
            return "";
        }
        if (!/^https?:\/\//i.test(w)) {
            w = "https://" + w;
        }
        return w;
    }

    function stationKey(s) {
        if (!s) {
            return "";
        }
        return String(
            s.id ||
                s.installation_id ||
                s.installationId ||
                ((s.latitude != null ? s.latitude : "") +
                    "," +
                    (s.longitude != null ? s.longitude : ""))
        );
    }

    function statusInfo(s) {
        var cat = String(
            (s && (s.public_category || s.lifecycle_state)) || ""
        ).toLowerCase();
        if (cat === "planned") {
            return { cat: "planned", label: "Planeada", color: "#E8A020" };
        }
        if (cat === "existing" || cat === "running") {
            return {
                cat: "running",
                label: "Em opera\u00e7\u00e3o",
                color: "#2E7D32",
            };
        }
        if (cat) {
            return { cat: "other", label: cat, color: "#757575" };
        }
        return { cat: "other", label: "", color: "#A89D3F" };
    }

    function statusMarkerIcon(L, color) {
        var html =
            '<span class="fs-map-pin" style="background:' +
            color +
            ";border-color:" +
            color +
            ';"></span>';
        return L.divIcon({
            className: "fs-map-marker",
            html: html,
            iconSize: [22, 22],
            iconAnchor: [11, 22],
            popupAnchor: [0, -18],
        });
    }

    function normalizeCoord(v) {
        if (v == null || v === "") {
            return NaN;
        }
        return parseFloat(String(v).replace(",", "."));
    }

    function indexKeyLatLng(lat, lng) {
        return Number(lat).toFixed(5) + "," + Number(lng).toFixed(5);
    }

    function cleanMapHost(mapEl) {
        // Website builder COWs sometimes serialize a previously initialized
        // Leaflet DOM tree into the map div; wipe it before L.map().
        if (!mapEl) {
            return null;
        }
        if (mapEl._leaflet_id) {
            try {
                mapEl._leaflet_id = null;
            } catch (e) {
                // ignore
            }
        }
        mapEl.className = "fs-map";
        mapEl.innerHTML = "";
        mapEl.removeAttribute("tabindex");
        mapEl.style.cssText = "";
        return mapEl;
    }


    function ensureStationList(stations) {
        var ul = document.querySelector("#fs-stations-expand .fs-station-list, ul.fs-station-list");
        if (!ul) {
            var expand = document.getElementById("fs-stations-expand");
            if (!expand) {
                return;
            }
            ul = document.createElement("ul");
            ul.className = "list-unstyled fs-station-list mb-0";
            expand.appendChild(ul);
        }
        // Rebuild list from live FS_STATIONS so COW pages without list markup still work
        if (!stations || !stations.length) {
            return;
        }
        ul.innerHTML = "";
        stations.forEach(function (s) {
            var st = statusInfo(s);
            var li = document.createElement("li");
            li.className = "fs-station-list-item fs-station-item";
            var sid = stationKey(s);
            if (sid) li.setAttribute("data-station-id", sid);
            var lat = normalizeCoord(s.latitude);
            var lng = normalizeCoord(s.longitude);
            if (isFinite(lat)) li.setAttribute("data-lat", String(lat));
            if (isFinite(lng)) li.setAttribute("data-lng", String(lng));
            if (st.cat) li.setAttribute("data-status", st.cat);
            var title = document.createElement("div");
            title.className = "fs-station-title-row";
            var strong = document.createElement("strong");
            strong.textContent = s.name || "Station";
            title.appendChild(strong);
            if (st.label) {
                var badge = document.createElement("span");
                badge.className = "fs-status-badge fs-status-" + st.cat;
                badge.textContent = st.label;
                title.appendChild(badge);
            }
            li.appendChild(title);
            var meta = document.createElement("div");
            meta.className = "fs-station-meta text-muted small";
            meta.textContent =
                (s.location || "") +
                " | " +
                (s.capacity_kwp != null ? s.capacity_kwp : 0) +
                " kWp";
            li.appendChild(meta);
            ul.appendChild(li);
        });
    }

    function bindListClicks(focusStation) {
        document.querySelectorAll(".fs-station-list-item").forEach(function (el) {
            if (el.getAttribute("data-fs-map-bound") === "1") {
                return;
            }
            el.setAttribute("data-fs-map-bound", "1");
            el.style.cursor = "pointer";
            el.setAttribute("role", "button");
            el.setAttribute("tabindex", "0");
            el.addEventListener("click", function (ev) {
                if (ev.target && ev.target.closest && ev.target.closest("a")) {
                    return;
                }
                ev.preventDefault();
                focusStation(el);
            });
            el.addEventListener("keydown", function (ev) {
                if (ev.key === "Enter" || ev.key === " ") {
                    ev.preventDefault();
                    focusStation(el);
                }
            });
        });
    }

    function init() {
        if (typeof L === "undefined") {
            return false;
        }
        var mapEl = document.getElementById("fs-stations-map");
        if (!mapEl) {
            return false;
        }
        if (window.FS_MAP && window.FS_MAP_READY) {
            ensureStationList(window.FS_STATIONS || []);
            bindListClicks(window.FS_FOCUS_STATION);
            return true;
        }

        mapEl = cleanMapHost(mapEl);
        var stations = window.FS_STATIONS || [];
        ensureStationList(stations);
        var map = L.map(mapEl, { scrollWheelZoom: true });
        // Cap zoom: public markers are intentionally approximate (~1 km).
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            maxZoom: 14,
            attribution: "&copy; OpenStreetMap contributors",
        }).addTo(map);
        if (typeof map.setMaxZoom === "function") {
            map.setMaxZoom(14);
        }

        var markers = [];
        var byId = {};

        function remember(key, entry) {
            if (!key) {
                return;
            }
            byId[String(key)] = entry;
        }

        stations.forEach(function (s) {
            var lat = normalizeCoord(s.latitude);
            var lng = normalizeCoord(s.longitude);
            if (!isFinite(lat) || !isFinite(lng)) {
                return;
            }
            var st = statusInfo(s);
            var m = L.marker([lat, lng], {
                icon: statusMarkerIcon(L, st.color),
                title:
                    (s.name || "Station") +
                    (st.label ? " (" + st.label + ")" : ""),
            }).addTo(map);

            var saved =
                s.money_saved_display != null && s.money_saved_display !== ""
                    ? s.money_saved_display
                    : s.money_saved_eur != null
                      ? Math.round(Number(s.money_saved_eur))
                      : "\u2014";
            var info = s.info || s.description || s.short_description || "";
            var html = "<strong>" + esc(s.name || "Station") + "</strong>";
            if (st.label) {
                html +=
                    ' <span class="fs-status-badge fs-status-' +
                    st.cat +
                    '">' +
                    esc(st.label) +
                    "</span>";
            }
            html +=
                "<br/>" +
                esc(s.location || "") +
                "<br/>" +
                esc(s.capacity_kwp || 0) +
                " kWp<br/>" +
                "<strong>Poupan\u00e7a estimada:</strong> " +
                esc(saved) +
                " EUR/ano";
            if (s.savings_is_indicative) {
                html += " <em>(indicativa)</em>";
            }
            if (info) {
                html +=
                    "<br/><strong>Descri\u00e7\u00e3o:</strong> " + esc(info);
            }
            html +=
                "<br/><em class=\"text-muted\">Localiza\u00e7\u00e3o aproximada (at\u00e9 ~1 km)</em>";
            var w = absUrl(s.website_href || s.website);
            if (w) {
                html +=
                    '<br/><a href="' +
                    esc(w) +
                    '" target="_blank" rel="noopener">Website</a>';
            }
            m.bindPopup(html, { autoPan: false, maxWidth: 280 });
            m.on("click", function () {
                map.invalidateSize(false);
                map.setView([lat, lng], Math.min(Math.max(map.getZoom() || 0, 12), 14), {
                    animate: false,
                });
                m.openPopup();
                map.panTo([lat, lng], { animate: true });
            });
            markers.push(m);

            var entry = { marker: m, lat: lat, lng: lng, status: st };
            remember(stationKey(s), entry);
            remember(s.installation_id, entry);
            remember(s.installationId, entry);
            remember(indexKeyLatLng(lat, lng), entry);
            remember(String(lat) + "," + String(lng), entry);
        });

        if (markers.length) {
            map.fitBounds(L.featureGroup(markers).getBounds().pad(0.15));
        } else {
            map.setView([38.7223, -9.1393], 5);
        }

        setTimeout(function () {
            try {
                map.invalidateSize(false);
            } catch (e) {
                // ignore
            }
        }, 150);

        function focusStation(el) {
            if (!el) {
                return;
            }
            var id = el.getAttribute("data-station-id") || "";
            var lat = normalizeCoord(el.getAttribute("data-lat"));
            var lng = normalizeCoord(el.getAttribute("data-lng"));
            var entry = null;
            if (id && byId[id]) {
                entry = byId[id];
            } else if (isFinite(lat) && isFinite(lng)) {
                entry =
                    byId[indexKeyLatLng(lat, lng)] ||
                    byId[String(lat) + "," + String(lng)] || {
                        marker: null,
                        lat: lat,
                        lng: lng,
                    };
            }
            if (!entry || !isFinite(entry.lat) || !isFinite(entry.lng)) {
                return;
            }
            var body = document.getElementById("fs-stations-expand");
            var btn = document.getElementById("fs-stations-toggle");
            if (body && !body.classList.contains("show")) {
                body.classList.add("show");
                if (btn) {
                    btn.setAttribute("aria-expanded", "true");
                }
            }
            map.invalidateSize(false);
            // Center the station in the map box. Disable popup autoPan so the
            // marker stays geometrically centered after openPopup().
            var targetZoom = Math.min(Math.max(map.getZoom() || 0, 12), 14);
            map.setView([entry.lat, entry.lng], targetZoom, { animate: false });
            if (entry.marker) {
                entry.marker.openPopup();
            }
            // Second pan after layout/popup to keep the pin in the visual center.
            map.panTo([entry.lat, entry.lng], { animate: true });
            setTimeout(function () {
                try {
                    map.invalidateSize(false);
                    map.panTo([entry.lat, entry.lng], { animate: false });
                } catch (e) {
                    // ignore
                }
            }, 120);
            document
                .querySelectorAll(".fs-station-list-item.is-active")
                .forEach(function (n) {
                    n.classList.remove("is-active");
                });
            el.classList.add("is-active");
            try {
                el.scrollIntoView({ block: "nearest", behavior: "smooth" });
            } catch (e) {
                // ignore
            }
        }

        bindListClicks(focusStation);

        if (!window.FS_MAP_DELEGATE) {
            window.FS_MAP_DELEGATE = true;
            document.addEventListener(
                "click",
                function (ev) {
                    var el =
                        ev.target &&
                        ev.target.closest &&
                        ev.target.closest(".fs-station-list-item");
                    if (!el) {
                        return;
                    }
                    if (ev.target.closest && ev.target.closest("a")) {
                        return;
                    }
                    if (typeof window.FS_FOCUS_STATION === "function") {
                        window.FS_FOCUS_STATION(el);
                    }
                },
                true
            );
        }

        var toggle = document.getElementById("fs-stations-toggle");
        if (toggle && !toggle.getAttribute("data-fs-map-resize")) {
            toggle.setAttribute("data-fs-map-resize", "1");
            toggle.addEventListener("click", function () {
                setTimeout(function () {
                    try {
                        map.invalidateSize(false);
                    } catch (e) {
                        // ignore
                    }
                }, 200);
            });
        }

        window.FS_MAP = map;
        window.FS_FOCUS_STATION = focusStation;
        window.FS_MAP_READY = true;
        return true;
    }

    function boot() {
        if (init()) {
            return;
        }
        var tries = 0;
        var t = setInterval(function () {
            tries += 1;
            if (init() || tries > 40) {
                clearInterval(t);
            }
        }, 100);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", boot);
    } else {
        boot();
    }
})();
