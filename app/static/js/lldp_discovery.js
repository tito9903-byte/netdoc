(() => {
    const form = document.querySelector("[data-lldp-run-form]");
    const button = document.querySelector("[data-lldp-run-button]");

    if (!(form instanceof HTMLFormElement) || !(button instanceof HTMLButtonElement)) {
        return;
    }

    let running = false;
    const originalLabel = button.innerHTML;

    function showClientError(message) {
        let banner = document.querySelector("[data-lldp-client-error]");
        if (!(banner instanceof HTMLElement)) {
            banner = document.createElement("div");
            banner.className = "notice error-notice lldp-error";
            banner.dataset.lldpClientError = "";
            form.closest(".lldp-page")?.prepend(banner);
        }
        banner.innerHTML = [
            "<strong>No fue posible iniciar el descubrimiento.</strong>",
            `<span>${message}</span>`,
        ].join("");
    }

    async function executeDiscovery(event) {
        event?.preventDefault();

        if (running || button.disabled) {
            return;
        }

        running = true;
        button.disabled = true;
        button.setAttribute("aria-busy", "true");
        button.innerHTML = '<span aria-hidden="true">⌁</span> Consultando LLDP…';

        try {
            const response = await fetch(form.action, {
                method: "POST",
                body: new FormData(form),
                credentials: "same-origin",
                redirect: "follow",
                headers: {
                    Accept: "text/html",
                    "X-Requested-With": "NetDoc-LLDP",
                },
            });

            if (response.redirected && new URL(response.url).pathname === "/login") {
                window.location.assign(response.url);
                return;
            }

            const contentType = response.headers.get("content-type") || "";
            if (!contentType.includes("text/html")) {
                throw new Error(
                    `El servidor respondió HTTP ${response.status} sin una página HTML válida.`,
                );
            }

            const html = await response.text();
            const cleanUrl = form.action.replace(/\/run\/?$/, "");
            window.history.replaceState({}, "", cleanUrl);
            document.open();
            document.write(html);
            document.close();
        } catch (error) {
            const message = error instanceof Error
                ? error.message
                : "Ocurrió un error inesperado al enviar la solicitud POST.";
            showClientError(message);
            running = false;
            button.disabled = false;
            button.removeAttribute("aria-busy");
            button.innerHTML = originalLabel;
        }
    }

    form.addEventListener("submit", executeDiscovery);
    button.addEventListener("click", executeDiscovery);
})();
