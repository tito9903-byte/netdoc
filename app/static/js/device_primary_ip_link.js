(() => {
    const normalizedPath = window.location.pathname.replace(/\/$/, "");

    function ensureManagementStyles() {
        if (document.querySelector('link[data-device-management-styles]')) {
            return;
        }
        const stylesheet = document.createElement("link");
        stylesheet.rel = "stylesheet";
        stylesheet.href = "/static/css/device_management.css?v=20260727-1";
        stylesheet.dataset.deviceManagementStyles = "";
        document.head.appendChild(stylesheet);
    }

    function showQueryMessage() {
        const parameters = new URLSearchParams(window.location.search);
        const notice = parameters.get("notice");
        const error = parameters.get("error");
        const main = document.getElementById("main-content");

        if (main && (notice || error)) {
            const banner = document.createElement("div");
            banner.className = error ? "notice error-notice" : "notice success-notice";
            banner.innerHTML = error
                ? `<strong>No fue posible completar la operación.</strong><span>${error}</span>`
                : `<strong>Operación completada.</strong><span>${notice}</span>`;
            main.prepend(banner);
            parameters.delete("notice");
            parameters.delete("error");
        }

        return parameters;
    }

    async function loadJson(url) {
        const response = await fetch(url, {
            headers: { Accept: "application/json" },
            credentials: "same-origin",
        });
        if (!response.ok) {
            return null;
        }
        const payload = await response.json();
        return payload && payload.ok ? payload : null;
    }

    async function configureDevicePage(deviceId) {
        ensureManagementStyles();

        const terms = Array.from(document.querySelectorAll(".information-list dt"));
        const primaryTerm = terms.find((item) => item.textContent.trim() === "IP principal");

        if (primaryTerm) {
            const row = primaryTerm.closest("div");
            const value = row?.querySelector("dd");
            if (value && !value.querySelector("[data-primary-ip-action]")) {
                const action = document.createElement("a");
                action.href = `/devices/${deviceId}/primary-ip/new`;
                action.className = "primary-ip-config-link";
                action.dataset.createModal = "";
                action.dataset.modalTitle = "Configurar IP principal";
                action.dataset.primaryIpAction = "";
                action.textContent = "Configurar";
                value.append(action);
            }
        }

        const interfaceActions = document.querySelector(".interface-panel-actions");
        if (
            interfaceActions instanceof HTMLElement &&
            !interfaceActions.querySelector("[data-lldp-discovery-action]")
        ) {
            const lldpAction = document.createElement("a");
            lldpAction.href = `/devices/${deviceId}/lldp-discovery`;
            lldpAction.className = "interface-sync-link";
            lldpAction.dataset.createModal = "";
            lldpAction.dataset.modalTitle = "Descubrir conexiones LLDP";
            lldpAction.dataset.lldpDiscoveryAction = "";
            lldpAction.innerHTML = '<span aria-hidden="true">⌁</span> Descubrir LLDP';
            interfaceActions.prepend(lldpAction);
        }

        const payload = await loadJson(`/api/netdoc/devices/${deviceId}/interfaces`);
        if (!payload || !payload.can_manage) {
            return;
        }

        const header = document.querySelector(".device-detail-header");
        if (header && !header.querySelector("[data-device-edit-action]")) {
            const actionGroup = document.createElement("div");
            actionGroup.className = "interface-row-actions";
            const edit = document.createElement("a");
            edit.href = `/devices/${deviceId}/edit`;
            edit.className = "button secondary";
            edit.dataset.deviceEditAction = "";
            edit.textContent = "Editar dispositivo";
            actionGroup.appendChild(edit);
            const status = header.querySelector(".device-status");
            if (status) {
                actionGroup.prepend(status);
            }
            header.appendChild(actionGroup);
        }

        if (interfaceActions && !interfaceActions.querySelector("[data-interface-create-action]")) {
            const create = document.createElement("a");
            create.href = `/devices/${deviceId}/interfaces/new`;
            create.className = "interface-sync-link";
            create.dataset.interfaceCreateAction = "";
            create.innerHTML = '<span aria-hidden="true">＋</span> Crear interfaz';
            interfaceActions.prepend(create);
        }

        const table = document.querySelector(".interfaces-table");
        if (!(table instanceof HTMLTableElement)) {
            return;
        }
        const headRow = table.querySelector("thead tr");
        if (headRow && !headRow.querySelector("[data-interface-actions-column]")) {
            const heading = document.createElement("th");
            heading.dataset.interfaceActionsColumn = "";
            heading.textContent = "Acciones";
            headRow.appendChild(heading);
        }

        const byName = new Map(
            payload.interfaces.map((item) => [String(item.name || "").trim(), item.id]),
        );
        table.querySelectorAll("tbody tr").forEach((row) => {
            if (row.querySelector("[data-interface-row-actions]")) {
                return;
            }
            const name = row.querySelector("td:first-child strong")?.textContent.trim() || "";
            const interfaceId = byName.get(name);
            const cell = document.createElement("td");
            cell.dataset.interfaceRowActions = "";
            if (interfaceId) {
                const actions = document.createElement("div");
                actions.className = "interface-row-actions";
                actions.innerHTML = [
                    `<a class="button secondary" href="/devices/${deviceId}/interfaces/${interfaceId}/edit">Editar</a>`,
                    `<a class="button danger" href="/devices/${deviceId}/interfaces/${interfaceId}/delete">Eliminar</a>`,
                ].join("");
                cell.appendChild(actions);
            }
            row.appendChild(cell);
        });
    }

    async function configureModelPage(deviceTypeId) {
        ensureManagementStyles();
        const payload = await loadJson(
            `/api/netdoc/device-types/${deviceTypeId}/interfaces`,
        );
        if (!payload || !payload.can_manage) {
            return;
        }

        const groups = Array.from(document.querySelectorAll(".component-inventory-group"));
        const interfaceGroup = groups.find((group) => (
            group.querySelector("h3")?.textContent.trim() === "Interfaces de red"
        ));
        if (!interfaceGroup) {
            return;
        }

        const byName = new Map(
            payload.interfaces.map((item) => [String(item.name || "").trim(), item.id]),
        );
        interfaceGroup.querySelectorAll(".component-item").forEach((item) => {
            if (item.querySelector("[data-model-interface-edit]")) {
                return;
            }
            const name = item.querySelector("strong")?.textContent.trim() || "";
            const interfaceId = byName.get(name);
            if (!interfaceId) {
                return;
            }
            const edit = document.createElement("a");
            edit.href = `/device-types/${deviceTypeId}/interfaces/${interfaceId}/edit`;
            edit.className = "button secondary";
            edit.dataset.modelInterfaceEdit = "";
            edit.textContent = "Editar / Eliminar";
            item.appendChild(edit);
        });
    }

    const parameters = showQueryMessage();
    const main = document.getElementById("main-content");

    const deviceMatch = normalizedPath.match(/^\/devices\/(\d+)$/);
    if (deviceMatch) {
        const deviceId = deviceMatch[1];
        configureDevicePage(deviceId).catch(() => {});

        if (parameters.get("primary_ip_saved") === "1") {
            if (main && !main.querySelector("[data-primary-ip-success]")) {
                const banner = document.createElement("div");
                banner.className = "primary-ip-success-banner";
                banner.dataset.primaryIpSuccess = "";
                banner.innerHTML = "<strong>IP principal actualizada.</strong><span>El rack y los listados usarán esta selección.</span>";
                main.prepend(banner);
            }
            parameters.delete("primary_ip_saved");
        }

        if (parameters.get("lldp_documented") === "1") {
            if (main && !main.querySelector("[data-lldp-success]")) {
                const banner = document.createElement("div");
                banner.className = "primary-ip-success-banner";
                banner.dataset.lldpSuccess = "";
                banner.innerHTML = "<strong>Conexión LLDP documentada.</strong><span>NetBox ya contiene el cable en ambos extremos.</span>";
                main.prepend(banner);
            }
            parameters.delete("lldp_documented");
            parameters.delete("cable_id");
        }
    }

    const modelMatch = normalizedPath.match(/^\/device-types\/(\d+)$/);
    if (modelMatch) {
        configureModelPage(modelMatch[1]).catch(() => {});
    }

    const cleanQuery = parameters.toString();
    const cleanUrl = `${window.location.pathname}${cleanQuery ? `?${cleanQuery}` : ""}${window.location.hash}`;
    if (cleanUrl !== `${window.location.pathname}${window.location.search}${window.location.hash}`) {
        window.history.replaceState({}, "", cleanUrl);
    }
})();
