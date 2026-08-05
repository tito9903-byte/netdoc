(() => {
    const root = document.querySelector("[data-topology-root]");
    if (!root) {
        return;
    }

    const viewButtons = document.querySelectorAll("[data-topology-view]");
    const faceButtons = document.querySelectorAll("[data-topology-face]");
    const scaleButtons = document.querySelectorAll("[data-topology-scale]");
    const searchInput = document.querySelector("[data-topology-search]");
    const racks = Array.from(root.querySelectorAll("[data-topology-rack]"));
    const sites = Array.from(root.querySelectorAll("[data-topology-site]"));

    const setActive = (buttons, dataKey, value) => {
        buttons.forEach((button) => {
            button.classList.toggle(
                "active",
                button.dataset[dataKey] === value,
            );
        });
    };

    const applyView = (view) => {
        const selected = view === "front" ? "front" : "isometric";
        root.dataset.view = selected;
        setActive(viewButtons, "topologyView", selected);
        window.localStorage.setItem("netdocTopologyView", selected);
    };

    const applyScale = (scale) => {
        const selected = scale === "detail" ? "detail" : "fit";
        root.dataset.scale = selected;
        setActive(scaleButtons, "topologyScale", selected);
        window.localStorage.setItem("netdocRack3dScale", selected);
    };

    const imageForFace = (device, face) => {
        if (!(device instanceof HTMLElement)) {
            return "";
        }
        return (
            (face === "rear"
                ? device.dataset.rearImage
                : device.dataset.frontImage)
            || device.dataset.frontImage
            || device.dataset.rearImage
            || ""
        );
    };

    const applyFace = (face) => {
        const selected = face === "rear" ? "rear" : "front";
        root.dataset.face = selected;
        setActive(faceButtons, "topologyFace", selected);

        root.querySelectorAll("[data-topology-device]").forEach((device) => {
            if (!(device instanceof HTMLElement)) {
                return;
            }
            const deviceFace = device.dataset.deviceFace || "sin definir";
            const fullDepth = device.dataset.fullDepth === "true";
            device.hidden = !(
                fullDepth
                || deviceFace === selected
                || deviceFace === "sin definir"
            );

            const image = device.querySelector("[data-topology-device-image]");
            if (image instanceof HTMLImageElement) {
                const source = imageForFace(device, selected);
                if (source) {
                    image.src = source;
                    image.alt = `${selected === "rear" ? "Parte trasera" : "Frente"} del modelo`;
                    image.hidden = false;
                } else {
                    image.hidden = true;
                }
            }
        });

        window.localStorage.setItem("netdocTopologyFace", selected);
    };

    const applySearch = () => {
        const query = (searchInput?.value || "").trim().toLocaleLowerCase("es");
        racks.forEach((rack) => {
            const haystack = (rack.dataset.searchText || "").toLocaleLowerCase("es");
            rack.hidden = Boolean(query) && !haystack.includes(query);
        });
        sites.forEach((site) => {
            const visibleRack = Array.from(
                site.querySelectorAll("[data-topology-rack]"),
            ).some((rack) => !rack.hidden);
            const siteMatch = (site.dataset.searchText || "")
                .toLocaleLowerCase("es")
                .includes(query);
            site.hidden = Boolean(query) && !visibleRack && !siteMatch;
        });
    };

    viewButtons.forEach((button) => {
        button.addEventListener("click", () => {
            applyView(button.dataset.topologyView || "isometric");
        });
    });

    faceButtons.forEach((button) => {
        button.addEventListener("click", () => {
            applyFace(button.dataset.topologyFace || "front");
        });
    });

    scaleButtons.forEach((button) => {
        button.addEventListener("click", () => {
            applyScale(button.dataset.topologyScale || "fit");
        });
    });

    searchInput?.addEventListener("input", applySearch);

    applyView(window.localStorage.getItem("netdocTopologyView") || "isometric");
    applyFace(window.localStorage.getItem("netdocTopologyFace") || "front");
    applyScale(window.localStorage.getItem("netdocRack3dScale") || "fit");
})();
