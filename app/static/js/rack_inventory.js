(() => {
    const root = document.querySelector("[data-rack-inventory]");
    if (!(root instanceof HTMLElement)) {
        return;
    }

    const input = root.querySelector("[data-rack-inventory-search]");
    const rows = Array.from(
        root.querySelectorAll("[data-rack-inventory-row]")
    );
    const count = root.querySelector("[data-rack-inventory-count]");
    const empty = root.querySelector("[data-rack-inventory-empty]");

    if (!(input instanceof HTMLInputElement) || rows.length === 0) {
        return;
    }

    const normalize = (value) => String(value || "")
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .toLowerCase()
        .trim();

    const update = () => {
        const query = normalize(input.value);
        let visible = 0;

        rows.forEach((row) => {
            const haystack = normalize(row.dataset.searchText);
            const matches = !query || haystack.includes(query);
            row.hidden = !matches;
            if (matches) {
                visible += 1;
            }
        });

        if (count instanceof HTMLElement) {
            count.textContent = query
                ? `${visible} de ${rows.length}`
                : `${rows.length} equipos`;
        }

        if (empty instanceof HTMLElement) {
            empty.hidden = visible !== 0;
        }
    };

    input.addEventListener("input", update);
    input.addEventListener("search", update);
})();
