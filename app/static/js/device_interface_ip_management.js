(() => {
    const host = document.querySelector("[data-interface-ip-management]");
    if (!(host instanceof HTMLElement)) {
        return;
    }

    const deviceId = host.dataset.deviceId;
    const interfaceId = host.dataset.interfaceId;
    if (!deviceId || !interfaceId) {
        return;
    }

    function text(value) {
        return String(value || "").trim();
    }

    function renderError(message) {
        host.innerHTML = [
            '<section class="panel interface-ip-management">',
            '<div class="notice error-notice">',
            '<strong>No fue posible cargar las direcciones IP.</strong>',
            `<span>${text(message) || "La API de NetDoc no respondió correctamente."}</span>`,
            "</div>",
            "</section>",
        ].join("");
    }

    function render(payload) {
        const canManage = Boolean(payload.can_manage);
        const addresses = Array.isArray(payload.addresses) ? payload.addresses : [];
        const rows = addresses.map((item) => {
            const meta = [];
            if (text(item.dns_name)) {
                meta.push(`<span>DNS: ${text(item.dns_name)}</span>`);
            }
            if (text(item.description)) {
                meta.push(`<span>${text(item.description)}</span>`);
            }
            const role = text(item.role)
                ? `<span class="interface-ip-role">${text(item.role)}</span>`
                : "";
            const primary = item.is_primary
                ? '<span class="interface-ip-primary">Principal</span>'
                : "";
            const action = canManage
                ? `<a class="button secondary" href="${item.edit_url}">Editar IP</a>`
                : "";

            return [
                '<article class="interface-ip-row">',
                '<div class="interface-ip-main">',
                '<div class="interface-ip-address-line">',
                `<strong class="interface-ip-address">${text(item.address)}</strong>`,
                primary,
                `<span class="interface-ip-status">${text(item.status)}</span>`,
                role,
                "</div>",
                meta.length ? `<div class="interface-ip-meta">${meta.join("")}</div>` : "",
                "</div>",
                action,
                "</article>",
            ].join("");
        }).join("");

        host.innerHTML = [
            '<section class="panel interface-ip-management">',
            '<div class="interface-ip-management-header">',
            "<div>",
            '<span class="eyebrow">Direccionamiento de la interfaz</span>',
            "<h3>Direcciones IP</h3>",
            `<p>${addresses.length} dirección${addresses.length === 1 ? "" : "es"} asignada${addresses.length === 1 ? "" : "s"} a ${text(payload.interface_name)}.</p>`,
            "</div>",
            canManage
                ? `<a class="button primary" href="${payload.create_url}">＋ Agregar IP</a>`
                : "",
            "</div>",
            addresses.length
                ? `<div class="interface-ip-list">${rows}</div>`
                : '<div class="interface-ip-empty">Esta interfaz todavía no tiene direcciones IP asignadas.</div>',
            "</section>",
        ].join("");
    }

    fetch(`/api/netdoc/devices/${deviceId}/interfaces/${interfaceId}/ip-addresses`, {
        credentials: "same-origin",
        headers: { Accept: "application/json" },
    })
        .then(async (response) => {
            const payload = await response.json();
            if (!response.ok || !payload?.ok) {
                throw new Error(payload?.error || `HTTP ${response.status}`);
            }
            return payload;
        })
        .then(render)
        .catch((error) => renderError(error instanceof Error ? error.message : String(error)));
})();
