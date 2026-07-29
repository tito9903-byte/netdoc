(() => {
    const container = document.querySelector("[data-netbox-model-fields]");
    const status = document.querySelector("[data-netbox-model-status]");

    if (!(container instanceof HTMLElement)) {
        return;
    }

    function setStatus(message, state = "neutral") {
        if (!(status instanceof HTMLElement)) {
            return;
        }
        status.textContent = message;
        status.dataset.state = state;
    }

    function createHelp(field) {
        if (!field.help_text) {
            return null;
        }
        const help = document.createElement("small");
        help.textContent = field.help_text;
        return help;
    }

    function defaultValues(field) {
        if (Array.isArray(field.default)) {
            return new Set(field.default.map((value) => String(value)));
        }
        if (field.default === null || field.default === undefined) {
            return new Set();
        }
        return new Set([String(field.default)]);
    }

    function createField(field) {
        const wrapper = document.createElement("div");
        wrapper.className = "field netbox-dynamic-field";
        wrapper.dataset.fieldName = field.name;

        if (field.input_type === "checkbox") {
            const checkboxLabel = document.createElement("label");
            checkboxLabel.className = "checkbox-field netbox-dynamic-checkbox";

            const input = document.createElement("input");
            input.type = "checkbox";
            input.name = field.name;
            input.value = "true";
            input.checked = field.default === true;

            const copy = document.createElement("span");
            const strong = document.createElement("strong");
            strong.textContent = field.label;
            copy.appendChild(strong);
            const help = createHelp(field);
            if (help) {
                copy.appendChild(help);
            }

            checkboxLabel.append(input, copy);
            wrapper.appendChild(checkboxLabel);
            return wrapper;
        }

        const label = document.createElement("label");
        label.htmlFor = `netbox-model-${field.name}`;
        label.textContent = field.label;
        if (field.required) {
            const required = document.createElement("span");
            required.textContent = " *";
            label.appendChild(required);
        }
        wrapper.appendChild(label);

        let input;
        if (field.input_type === "select") {
            input = document.createElement("select");
            input.multiple = Boolean(field.multiple);
            const selectedDefaults = defaultValues(field);

            if (!input.multiple) {
                const empty = document.createElement("option");
                empty.value = "";
                empty.textContent = field.required ? "Seleccionar" : "Sin definir";
                input.appendChild(empty);
            }

            for (const choice of field.choices || []) {
                const option = document.createElement("option");
                option.value = choice.value;
                option.textContent = choice.label;
                option.selected = selectedDefaults.has(String(choice.value));
                input.appendChild(option);
            }
        } else if (field.input_type === "textarea") {
            input = document.createElement("textarea");
            input.rows = 3;
            input.value = field.default ?? "";
        } else {
            input = document.createElement("input");
            input.type = field.input_type === "number" || field.input_type === "decimal"
                ? "number"
                : "text";
            if (field.input_type === "decimal") {
                input.step = "any";
            }
            input.value = field.default ?? "";
        }

        input.id = `netbox-model-${field.name}`;
        input.name = field.name;
        input.required = Boolean(field.required);
        wrapper.appendChild(input);

        const help = createHelp(field);
        if (help) {
            wrapper.appendChild(help);
        }
        return wrapper;
    }

    async function loadFields() {
        setStatus("Consultando capacidades de NetBox…");
        try {
            const response = await fetch("/api/device-types/model-fields", {
                headers: { Accept: "application/json" },
                credentials: "same-origin",
            });
            const payload = await response.json();
            if (!response.ok || payload.ok !== true) {
                throw new Error(payload.error || "No se pudieron consultar los campos.");
            }

            const fields = Array.isArray(payload.fields) ? payload.fields : [];
            container.replaceChildren(...fields.map(createField));
            if (fields.length) {
                setStatus(`${fields.length} campos avanzados publicados por NetBox`, "success");
            } else {
                setStatus("NetBox no publicó campos avanzados adicionales", "neutral");
            }
        } catch (error) {
            container.innerHTML = "";
            const alert = document.createElement("div");
            alert.className = "netbox-schema-error";
            alert.textContent = error instanceof Error
                ? error.message
                : "No se pudieron cargar los campos avanzados.";
            container.appendChild(alert);
            setStatus("Capacidades avanzadas no disponibles", "error");
        }
    }

    loadFields();
})();
