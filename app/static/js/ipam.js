(() => {
    const summary = document.querySelector("[data-ipam-summary]");
    const status = document.querySelector("[data-ipam-inventory-status]");

    if (!summary || !status || summary.dataset.inventoryReady === "true") {
        return;
    }

    const healthLabels = {
        full: "Lleno",
        critical: "Crítico",
        warning: "Advertencia",
        healthy: "Con espacio",
        unknown: "No calculado",
    };
    const healthClasses = [
        "full",
        "critical",
        "warning",
        "healthy",
        "unknown",
    ];

    const setStatus = (state, title, copy) => {
        status.classList.remove("loading", "ready", "warning", "error");
        status.classList.add(state);
        const titleNode = status.querySelector("[data-ipam-status-title]");
        const copyNode = status.querySelector("[data-ipam-status-copy]");

        if (titleNode) {
            titleNode.textContent = title;
        }
        if (copyNode) {
            copyNode.textContent = copy;
        }
    };

    const updateSummary = (data) => {
        const available = summary.querySelector("[data-summary-available]");
        const availableCopy = summary.querySelector(
            "[data-summary-available-copy]"
        );
        const critical = summary.querySelector("[data-summary-critical]");
        const criticalCopy = summary.querySelector(
            "[data-summary-critical-copy]"
        );

        if (available) {
            available.textContent = String(data.available_pools ?? "—");
        }
        if (availableCopy) {
            availableCopy.textContent = "Disponibilidad calculada";
        }
        if (critical) {
            critical.textContent = String(data.critical_pools ?? "—");
            const card = critical.closest(".summary-card");
            if (card) {
                card.classList.toggle(
                    "attention",
                    Number(data.critical_pools || 0) > 0
                );
            }
        }
        if (criticalCopy) {
            criticalCopy.textContent =
                `${data.full_pools || 0} completamente agotados`;
        }
    };

    const updatePool = (pool) => {
        const row = document.querySelector(
            `[data-pool-id="${String(pool.id)}"]`
        );

        if (!row) {
            return;
        }

        const used = row.querySelector("[data-pool-used]");
        const available = row.querySelector("[data-pool-available]");
        const availabilityCopy = row.querySelector(
            "[data-pool-availability-copy]"
        );
        const utilization = row.querySelector("[data-pool-utilization]");
        const bar = utilization?.querySelector(".progress-fill");
        const percentage = utilization?.querySelector("strong");
        const health = row.querySelector("[data-pool-health-label]");
        const healthName = String(pool._health || "unknown");

        if (used) {
            used.textContent = String(pool._used_compact ?? "—");
            used.parentElement.title = String(pool._used_exact ?? "—");
        }
        if (available) {
            available.textContent = String(pool._available_compact ?? "—");
            available.parentElement.title = String(
                pool._available_exact ?? "—"
            );
        }
        if (availabilityCopy) {
            availabilityCopy.textContent = pool._availability_error
                ? "No calculado"
                : "Estimadas desde IPAM";
            availabilityCopy.title = String(
                pool._availability_error || ""
            );
        }
        if (utilization) {
            utilization.classList.remove("is-loading");
        }
        if (bar) {
            bar.style.width = pool._utilization == null
                ? "0%"
                : `${pool._utilization}%`;
            bar.classList.remove(...healthClasses);
            bar.classList.add(healthName);
        }
        if (percentage) {
            percentage.textContent = pool._utilization == null
                ? "—"
                : `${pool._utilization}%`;
        }
        if (health) {
            health.textContent = healthLabels[healthName] || "No calculado";
            health.classList.remove(...healthClasses);
            health.classList.add(healthName);
        }
        row.dataset.poolHealth = healthName;
    };

    fetch(status.dataset.endpoint, {
        credentials: "same-origin",
        headers: { Accept: "application/json" },
    })
        .then(async (response) => {
            const payload = await response.json();
            if (!response.ok || !payload.ok) {
                throw new Error(
                    payload.error || "No se pudo calcular la ocupación."
                );
            }
            return payload;
        })
        .then((payload) => {
            updateSummary(payload.summary || {});
            (payload.pools || []).forEach(updatePool);
            summary.dataset.inventoryReady = "true";

            if (payload.inventory_warning) {
                setStatus(
                    "warning",
                    "La ocupación quedó incompleta.",
                    payload.inventory_warning
                );
                return;
            }
            setStatus(
                "ready",
                "Ocupación calculada.",
                "La ventana abrió primero y el inventario se completó en segundo plano."
            );
        })
        .catch((error) => {
            setStatus(
                "error",
                "No se pudo calcular la ocupación.",
                error.message
            );
        });
})();
