(() => {
    const form = document.querySelector("[data-device-filters]");

    if (!form) {
        return;
    }

    form.addEventListener("submit", () => {
        form.querySelectorAll("input[name], select[name]").forEach((field) => {
            if (
                typeof field.value === "string"
                && field.value.trim() === ""
            ) {
                field.disabled = true;
            }
        });
    });
})();
