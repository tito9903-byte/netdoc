const sides = ["a", "b"];
const maximumRows = 50;
const interfaceChoices = {a: [], b: []};

const form = document.getElementById("connectionForm");
const rowsContainer = document.getElementById("connectionRows");
const rowTemplate = document.getElementById("connectionRowTemplate");
const addRowButton = document.getElementById("addConnectionRow");
const submitButton = document.getElementById("submitConnectionBatch");
const feedback = document.getElementById("connectionFeedback");
const batchCount = document.getElementById("batchConnectionCount");

function resetSelect(select, placeholder) {
    select.replaceChildren(new Option(placeholder, ""));
    select.disabled = true;
}

function fillSelect(select, results, valueKey, labelBuilder, placeholder) {
    select.replaceChildren(new Option(placeholder, ""));

    for (const result of results) {
        select.add(new Option(labelBuilder(result), String(result[valueKey])));
    }

    select.disabled = results.length === 0;
}

async function fetchJson(url, options = {}) {
    const response = await fetch(url, {
        ...options,
        headers: {
            Accept: "application/json",
            ...(options.headers || {}),
        },
    });
    const data = await response.json().catch(() => ({}));

    if (!response.ok || !data.ok) {
        throw new Error(
            data.error || "No fue posible cargar la información."
        );
    }

    return data;
}

function showFeedback(kind, title, message) {
    const alert = document.createElement("div");
    alert.className = `connection-alert ${kind}`;

    const strong = document.createElement("strong");
    strong.textContent = title;
    const span = document.createElement("span");
    span.textContent = message;

    alert.append(strong, span);
    feedback.replaceChildren(alert);
    alert.scrollIntoView({behavior: "smooth", block: "center"});
}

function interfaceLabel(item) {
    const description = item.description ? ` — ${item.description}` : "";
    return `${item.name} (${item.type})${description}`;
}

function selectedInterfaceIds() {
    return new Set(
        [...rowsContainer.querySelectorAll('[data-role="interface"]')]
            .map((select) => select.value)
            .filter(Boolean)
    );
}

function refreshInterfaceSelects() {
    const selected = selectedInterfaceIds();

    for (const select of rowsContainer.querySelectorAll(
        '[data-role="interface"]'
    )) {
        const current = select.value;
        const choices = interfaceChoices[select.dataset.side] || [];
        fillSelect(
            select,
            choices,
            "id",
            interfaceLabel,
            `Seleccionar interfaz ${select.dataset.side.toUpperCase()}`
        );
        select.value = current;

        for (const option of select.options) {
            option.disabled = (
                Boolean(option.value)
                && option.value !== current
                && selected.has(option.value)
            );
        }
    }
}

function updateRows() {
    const rows = [...rowsContainer.querySelectorAll(".batch-row")];

    rows.forEach((row, index) => {
        row.querySelector('[data-role="row-number"]').textContent = index + 1;
        row.querySelector('[data-action="remove-row"]').disabled =
            rows.length === 1;
    });

    batchCount.textContent = rows.length;
    addRowButton.disabled = rows.length >= maximumRows;
    refreshInterfaceSelects();
}

function addConnectionRow() {
    if (rowsContainer.children.length >= maximumRows) {
        return;
    }

    rowsContainer.append(rowTemplate.content.cloneNode(true));
    updateRows();
}

function clearInterfaces(side, placeholder = null) {
    interfaceChoices[side] = [];

    for (const select of rowsContainer.querySelectorAll(
        `[data-role="interface"][data-side="${side}"]`
    )) {
        resetSelect(
            select,
            placeholder || `Seleccionar interfaz ${side.toUpperCase()}`
        );
    }
}

async function loadDevices(side) {
    const siteSelect = document.getElementById(`site_${side}`);
    const deviceSelect = document.getElementById(`device_${side}`);
    const help = document.getElementById(`device_help_${side}`);

    resetSelect(deviceSelect, "Seleccionar equipo");
    clearInterfaces(side);

    if (!siteSelect.value) {
        help.textContent = "Selecciona un sitio para cargar sus equipos.";
        return;
    }

    resetSelect(deviceSelect, "Cargando equipos...");
    help.textContent = "Consultando equipos...";

    try {
        const data = await fetchJson(
            `/api/connections/devices?site_id=${
                encodeURIComponent(siteSelect.value)
            }`
        );
        fillSelect(
            deviceSelect,
            data.results,
            "id",
            (item) => item.status
                ? `${item.name} — ${item.status}`
                : item.name,
            "Seleccionar equipo"
        );
        help.textContent = data.results.length
            ? `${data.results.length} equipos disponibles.`
            : "El sitio no tiene equipos.";
    } catch (error) {
        resetSelect(deviceSelect, "Error al cargar equipos");
        help.textContent = error.message;
    }
}

async function loadInterfaces(side) {
    const deviceSelect = document.getElementById(`device_${side}`);
    const help = document.getElementById(`device_help_${side}`);

    clearInterfaces(side);

    if (!deviceSelect.value) {
        return;
    }

    clearInterfaces(side, "Cargando interfaces...");
    help.textContent = "Consultando puertos libres...";

    try {
        const data = await fetchJson(
            `/api/connections/interfaces?device_id=${
                encodeURIComponent(deviceSelect.value)
            }`
        );
        interfaceChoices[side] = data.results;
        refreshInterfaceSelects();
        help.textContent = data.results.length
            ? `${data.results.length} interfaces disponibles.`
            : "El equipo no tiene interfaces libres.";
    } catch (error) {
        clearInterfaces(side, "Error al cargar interfaces");
        help.textContent = error.message;
    }
}

async function loadBootstrap() {
    try {
        const data = await fetchJson("/api/connections/bootstrap");

        for (const side of sides) {
            fillSelect(
                document.getElementById(`site_${side}`),
                data.sites,
                "id",
                (item) => item.name,
                "Seleccionar sitio"
            );
        }

        fillSelect(
            document.getElementById("cable_type"),
            data.cable_types,
            "value",
            (item) => item.label,
            "Seleccionar tipo"
        );
        fillSelect(
            document.getElementById("status"),
            data.cable_statuses,
            "value",
            (item) => item.label,
            "Seleccionar estado"
        );
        fillSelect(
            document.getElementById("length_unit"),
            data.length_units,
            "value",
            (item) => item.label,
            "Seleccionar unidad"
        );

        const status = document.getElementById("status");
        const lengthUnit = document.getElementById("length_unit");
        status.value = [...status.options].some(
            (option) => option.value === "connected"
        ) ? "connected" : "";
        lengthUnit.value = [...lengthUnit.options].some(
            (option) => option.value === "m"
        ) ? "m" : "";
    } catch (error) {
        showFeedback(
            "error",
            "No fue posible preparar el formulario.",
            error.message
        );
    }
}

function textCell(value, className = "") {
    const cell = document.createElement("td");
    cell.textContent = value || "—";
    if (className) {
        cell.className = className;
    }
    return cell;
}

async function loadRecentConnections() {
    const loading = document.getElementById("recentConnectionsLoading");
    const table = document.getElementById("recentConnectionsTable");
    const empty = document.getElementById("recentConnectionsEmpty");
    const body = document.getElementById("recentConnectionsBody");
    const count = document.getElementById("recentConnectionCount");

    try {
        const data = await fetchJson("/api/connections/recent?limit=20");
        body.replaceChildren();

        for (const cable of data.results) {
            const row = document.createElement("tr");
            row.append(
                textCell(cable.id, "mono-value"),
                textCell(cable._a_label),
                textCell(cable._b_label),
                textCell(cable._type_label),
                textCell(cable.label),
                textCell(cable._status_label),
                textCell(cable._length_label)
            );
            row.children[5].classList.add("cable-status-cell");
            body.append(row);
        }

        count.textContent = `${data.count} mostrados`;
        table.hidden = data.count === 0;
        empty.hidden = data.count !== 0;
    } catch (error) {
        count.textContent = "No disponible";
        empty.querySelector("h3").textContent =
            "No fue posible cargar las conexiones";
        empty.querySelector("p").textContent = error.message;
        empty.hidden = false;
    } finally {
        loading.hidden = true;
    }
}

function batchPayload() {
    const rows = [...rowsContainer.querySelectorAll(".batch-row")];
    const connections = rows.map((row) => ({
        interface_a_id: Number(
            row.querySelector(
                '[data-role="interface"][data-side="a"]'
            ).value
        ),
        interface_b_id: Number(
            row.querySelector(
                '[data-role="interface"][data-side="b"]'
            ).value
        ),
        label: row.querySelector('[data-role="label"]').value.trim(),
    }));

    if (connections.some(
        (item) => !item.interface_a_id || !item.interface_b_id
    )) {
        throw new Error("Completa ambos extremos en todas las filas.");
    }

    const identifiers = connections.flatMap(
        (item) => [item.interface_a_id, item.interface_b_id]
    );
    if (new Set(identifiers).size !== identifiers.length) {
        throw new Error(
            "Una interfaz no puede repetirse dentro del mismo lote."
        );
    }

    const cableType = document.getElementById("cable_type").value;
    const status = document.getElementById("status").value;
    if (!cableType || !status) {
        throw new Error("Selecciona el tipo y el estado del cable.");
    }

    return {
        csrf: document.getElementById("connectionCsrf").value,
        connections,
        cable_type: cableType,
        status,
        color: document.getElementById("color").value,
        length: document.getElementById("length").value,
        length_unit: document.getElementById("length_unit").value,
        description: document.getElementById("description").value.trim(),
    };
}

async function submitBatch(event) {
    event.preventDefault();

    try {
        const payload = batchPayload();
        submitButton.disabled = true;
        submitButton.textContent = "Creando...";
        const result = await fetchJson("/api/connections/bulk", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(payload),
        });
        showFeedback(
            "success",
            "Conexiones creadas correctamente.",
            `${result.created_count} conexiones fueron registradas en NetBox.`
        );
        setTimeout(() => window.location.reload(), 900);
    } catch (error) {
        showFeedback(
            "error",
            "No fue posible completar el lote.",
            error.message
        );
        submitButton.disabled = form.dataset.writeEnabled !== "true";
        submitButton.textContent = "Crear conexiones";
    }
}

for (const side of sides) {
    document.getElementById(`site_${side}`).addEventListener(
        "change",
        () => loadDevices(side)
    );
    document.getElementById(`device_${side}`).addEventListener(
        "change",
        () => loadInterfaces(side)
    );
}

addRowButton.addEventListener("click", addConnectionRow);
rowsContainer.addEventListener("click", (event) => {
    const button = event.target.closest('[data-action="remove-row"]');
    if (button) {
        button.closest(".batch-row").remove();
        updateRows();
    }
});
rowsContainer.addEventListener("change", (event) => {
    if (event.target.matches('[data-role="interface"]')) {
        refreshInterfaceSelects();
    }
});
form.addEventListener("submit", submitBatch);

addConnectionRow();
void loadBootstrap();
void loadRecentConnections();
