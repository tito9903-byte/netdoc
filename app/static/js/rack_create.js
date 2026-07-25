(() => {
    const siteSelect = document.querySelector("[data-rack-site]");
    const locationSelect = document.querySelector("[data-rack-location]");

    if (!siteSelect || !locationSelect) {
        return;
    }

    const allOptions = Array.from(locationSelect.options).map((option) => ({
        value: option.value,
        label: option.textContent,
        siteId: option.dataset.siteId || "",
        selected: option.selected,
    }));

    const renderLocations = () => {
        const selectedSite = siteSelect.value;
        const previousValue = locationSelect.value;
        locationSelect.replaceChildren();

        const emptyOption = document.createElement("option");
        emptyOption.value = "";
        emptyOption.textContent = "Sin ubicación específica";
        locationSelect.appendChild(emptyOption);

        allOptions
            .filter((item) => item.value && item.siteId === selectedSite)
            .forEach((item) => {
                const option = document.createElement("option");
                option.value = item.value;
                option.textContent = item.label;
                option.dataset.siteId = item.siteId;
                option.selected = item.value === previousValue || item.selected;
                locationSelect.appendChild(option);
            });

        locationSelect.disabled = !selectedSite;

        if (
            previousValue &&
            !Array.from(locationSelect.options).some(
                (option) => option.value === previousValue,
            )
        ) {
            locationSelect.value = "";
        }
    };

    siteSelect.addEventListener("change", renderLocations);
    renderLocations();
})();
