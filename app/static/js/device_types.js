(() => {
    const patternInput = document.querySelector("[data-preview-pattern]");
    const startInput = document.querySelector("[data-preview-start]");
    const countInput = document.querySelector("[data-preview-count]");
    const preview = document.querySelector("[data-interface-preview]");
    const countLabel = document.querySelector("[data-preview-count-label]");
    const errorBox = document.querySelector("[data-preview-error]");

    if (!patternInput || !startInput || !countInput || !preview) {
        return;
    }

    let requestId = 0;
    let timer = null;

    const renderNames = (names) => {
        preview.replaceChildren();

        names.slice(0, 24).forEach((name) => {
            const chip = document.createElement("span");
            chip.textContent = name;
            preview.appendChild(chip);
        });

        if (countLabel) {
            countLabel.textContent = `${names.length} nombres generados`;
        }
    };

    const refresh = async () => {
        const currentRequest = ++requestId;
        const params = new URLSearchParams({
            pattern: patternInput.value,
            start: startInput.value || "0",
            count: countInput.value || "1",
        });

        try {
            const response = await fetch(
                `/api/device-types/interface-preview?${params.toString()}`,
                { headers: { Accept: "application/json" } },
            );
            const payload = await response.json();

            if (currentRequest !== requestId) {
                return;
            }

            if (!response.ok || payload.ok !== true) {
                throw new Error(payload.error || "No se pudo generar la vista previa.");
            }

            renderNames(payload.names || []);
            if (errorBox) {
                errorBox.textContent = "";
            }
        } catch (error) {
            if (currentRequest !== requestId) {
                return;
            }

            preview.replaceChildren();
            if (countLabel) {
                countLabel.textContent = "Vista previa no disponible";
            }
            if (errorBox) {
                errorBox.textContent = error.message;
            }
        }
    };

    const scheduleRefresh = () => {
        window.clearTimeout(timer);
        timer = window.setTimeout(refresh, 220);
    };

    [patternInput, startInput, countInput].forEach((input) => {
        input.addEventListener("input", scheduleRefresh);
        input.addEventListener("change", scheduleRefresh);
    });
})();
