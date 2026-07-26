(() => {
    const normalizedPath = window.location.pathname.replace(/\/$/, "");
    const match = normalizedPath.match(/^\/devices\/(\d+)$/);
    if (!match) {
        return;
    }

    const deviceId = match[1];
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

    const parameters = new URLSearchParams(window.location.search);
    if (parameters.get("primary_ip_saved") === "1") {
        const main = document.getElementById("main-content");
        if (main && !main.querySelector("[data-primary-ip-success]")) {
            const banner = document.createElement("div");
            banner.className = "primary-ip-success-banner";
            banner.dataset.primaryIpSuccess = "";
            banner.innerHTML = "<strong>IP principal actualizada.</strong><span>El rack y los listados usarán esta selección.</span>";
            main.prepend(banner);
        }
        parameters.delete("primary_ip_saved");
        const cleanQuery = parameters.toString();
        const cleanUrl = `${window.location.pathname}${cleanQuery ? `?${cleanQuery}` : ""}${window.location.hash}`;
        window.history.replaceState({}, "", cleanUrl);
    }
})();
