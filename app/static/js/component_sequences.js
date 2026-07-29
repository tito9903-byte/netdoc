(() => {
    const form = document.querySelector("[data-component-sequence-form]");
    const list = form?.querySelector("[data-sequence-list]");
    const template = document.getElementById("component-sequence-template");
    const addButton = form?.querySelector("[data-add-sequence]");
    const total = form?.querySelector("[data-sequence-total]");

    if (
        !(form instanceof HTMLFormElement) ||
        !(list instanceof HTMLElement) ||
        !(template instanceof HTMLTemplateElement) ||
        !(addButton instanceof HTMLButtonElement)
    ) {
        return;
    }

    const maximumSequences = 24;
    const maximumComponents = 256;

    function rows() {
        return Array.from(list.querySelectorAll("[data-sequence-row]"));
    }

    function numericValue(row, selector, fallback) {
        const input = row.querySelector(selector);
        if (!(input instanceof HTMLInputElement)) {
            return fallback;
        }
        const value = Number.parseInt(input.value, 10);
        return Number.isFinite(value) ? value : fallback;
    }

    function updateSummary() {
        const currentRows = rows();
        currentRows.forEach((row, index) => {
            row.dataset.sequenceIndex = String(index + 1);
            const heading = row.querySelector("[data-sequence-heading]");
            if (heading instanceof HTMLElement) {
                heading.textContent = `Secuencia ${index + 1}`;
            }
            const removeButton = row.querySelector("[data-remove-sequence]");
            if (removeButton instanceof HTMLButtonElement) {
                removeButton.disabled = currentRows.length === 1;
                removeButton.hidden = currentRows.length === 1;
            }
        });

        const componentTotal = currentRows.reduce(
            (sum, row) => sum + Math.max(0, numericValue(row, "[name='sequence_count']", 0)),
            0,
        );
        if (total instanceof HTMLElement) {
            total.textContent = `${componentTotal} registro${componentTotal === 1 ? "" : "s"}`;
            total.dataset.invalid = componentTotal > maximumComponents ? "true" : "false";
        }
        addButton.disabled = currentRows.length >= maximumSequences;
    }

    function addSequence() {
        if (rows().length >= maximumSequences) {
            return;
        }
        const fragment = template.content.cloneNode(true);
        list.append(fragment);
        updateSummary();
        const newRow = rows().at(-1);
        const pattern = newRow?.querySelector("[name='sequence_pattern']");
        if (pattern instanceof HTMLInputElement) {
            pattern.focus();
            pattern.select();
        }
    }

    addButton.addEventListener("click", addSequence);

    list.addEventListener("click", (event) => {
        const target = event.target instanceof Element
            ? event.target.closest("[data-remove-sequence]")
            : null;
        if (!(target instanceof HTMLButtonElement)) {
            return;
        }
        const currentRows = rows();
        if (currentRows.length <= 1) {
            return;
        }
        target.closest("[data-sequence-row]")?.remove();
        updateSummary();
    });

    list.addEventListener("input", updateSummary);

    form.addEventListener("submit", (event) => {
        const componentTotal = rows().reduce(
            (sum, row) => sum + Math.max(0, numericValue(row, "[name='sequence_count']", 0)),
            0,
        );
        if (componentTotal > maximumComponents) {
            event.preventDefault();
            window.alert(`El total no puede superar ${maximumComponents} registros.`);
        }
    });

    updateSummary();
})();
