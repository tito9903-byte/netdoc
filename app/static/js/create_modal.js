(() => {
    const modal = document.querySelector("[data-create-modal-root]");
    const frame = modal?.querySelector("[data-create-modal-frame]");
    const dialog = modal?.querySelector(".create-modal-dialog");
    const title = modal?.querySelector("#createModalTitle");
    const loading = modal?.querySelector("[data-create-modal-loading]");
    const closeButtons = modal?.querySelectorAll("[data-create-modal-close]") || [];
    const createPathPattern = /(?:\/actions)?\/new\/?$/;

    if (
        !(modal instanceof HTMLElement) ||
        !(frame instanceof HTMLIFrameElement) ||
        !(dialog instanceof HTMLElement)
    ) {
        return;
    }

    let opener = null;
    let initialPath = "";
    let open = false;
    let childResizeObserver = null;
    let resizeFrame = 0;

    function creationUrlFor(anchor) {
        if (!(anchor instanceof HTMLAnchorElement)) {
            return null;
        }
        if (
            anchor.target ||
            anchor.hasAttribute("download") ||
            anchor.dataset.createModal === "false"
        ) {
            return null;
        }

        let url;
        try {
            url = new URL(anchor.href, window.location.href);
        } catch (_error) {
            return null;
        }

        if (url.origin !== window.location.origin) {
            return null;
        }

        const explicitlyModal = anchor.hasAttribute("data-create-modal");
        if (!explicitlyModal && !createPathPattern.test(url.pathname)) {
            return null;
        }

        return url;
    }

    function modalSizeFor(anchor, url) {
        const explicit = anchor.dataset.modalSize;
        if (["compact", "standard", "wide"].includes(explicit)) {
            return explicit;
        }

        const path = url.pathname;
        if (
            path === "/devices/actions/new" ||
            path.startsWith("/device-types/new") ||
            path.includes("/components/")
        ) {
            return "wide";
        }

        if (
            path.startsWith("/admin/users/") ||
            path.includes("/ip-addresses/") ||
            path.includes("/interfaces/new")
        ) {
            return "compact";
        }

        return "standard";
    }

    function setLoading(visible) {
        if (!(loading instanceof HTMLElement)) {
            return;
        }
        loading.hidden = !visible;
    }

    function disconnectChildObserver() {
        if (childResizeObserver) {
            childResizeObserver.disconnect();
            childResizeObserver = null;
        }
        if (resizeFrame) {
            cancelAnimationFrame(resizeFrame);
            resizeFrame = 0;
        }
    }

    function childDocumentHeight() {
        try {
            const childDocument = frame.contentDocument;
            if (!childDocument?.documentElement || !childDocument.body) {
                return 0;
            }

            const root = childDocument.documentElement;
            const body = childDocument.body;
            const content = childDocument.querySelector(".content");

            return Math.max(
                body.scrollHeight,
                body.offsetHeight,
                root.scrollHeight,
                root.offsetHeight,
                content instanceof HTMLElement ? content.scrollHeight : 0,
            );
        } catch (_error) {
            return 0;
        }
    }

    function fitDialogToContent() {
        if (!open || window.matchMedia("(max-width: 700px)").matches) {
            return;
        }

        const contentHeight = childDocumentHeight();
        if (!contentHeight) {
            return;
        }

        const header = dialog.querySelector(".create-modal-header");
        const headerHeight = header instanceof HTMLElement ? header.offsetHeight : 64;
        const viewportLimit = Math.max(390, window.innerHeight - 40);
        const requestedHeight = Math.min(
            viewportLimit,
            Math.max(390, contentHeight + headerHeight + 2),
        );

        dialog.style.setProperty(
            "--create-modal-height",
            `${Math.round(requestedHeight)}px`,
        );
    }

    function scheduleFit() {
        if (resizeFrame) {
            cancelAnimationFrame(resizeFrame);
        }
        resizeFrame = requestAnimationFrame(() => {
            resizeFrame = 0;
            fitDialogToContent();
        });
    }

    function observeChildSize() {
        disconnectChildObserver();

        try {
            const childDocument = frame.contentDocument;
            if (!childDocument?.body || typeof ResizeObserver === "undefined") {
                return;
            }

            childResizeObserver = new ResizeObserver(scheduleFit);
            childResizeObserver.observe(childDocument.body);

            const content = childDocument.querySelector(".content");
            if (content instanceof HTMLElement) {
                childResizeObserver.observe(content);
            }
        } catch (_error) {
            // El ajuste inicial sigue funcionando aunque no se pueda observar.
        }
    }

    function closeModal({ restoreFocus = true } = {}) {
        if (!open) {
            return;
        }

        open = false;
        disconnectChildObserver();
        modal.hidden = true;
        modal.setAttribute("aria-hidden", "true");
        document.body.classList.remove("create-modal-open");
        frame.removeAttribute("src");
        frame.dataset.initialUrl = "";
        initialPath = "";
        dialog.dataset.size = "standard";
        dialog.style.removeProperty("--create-modal-height");
        setLoading(false);

        if (restoreFocus && opener instanceof HTMLElement) {
            opener.focus();
        }
        opener = null;
    }

    function openModal(anchor, url) {
        opener = anchor;
        initialPath = url.pathname.replace(/\/$/, "");

        const modalUrl = new URL(url.href);
        modalUrl.searchParams.set("modal", "1");

        const modalTitle = (
            anchor.dataset.modalTitle ||
            anchor.textContent ||
            "Crear registro"
        ).replace(/^\s*[+＋]\s*/, "").trim();

        if (title instanceof HTMLElement) {
            title.textContent = modalTitle || "Crear registro";
        }

        frame.title = modalTitle || "Formulario de creación";
        frame.dataset.initialUrl = modalUrl.href;
        dialog.dataset.size = modalSizeFor(anchor, modalUrl);
        dialog.style.removeProperty("--create-modal-height");
        setLoading(true);
        modal.hidden = false;
        modal.setAttribute("aria-hidden", "false");
        document.body.classList.add("create-modal-open");
        open = true;
        frame.src = modalUrl.href;

        const closeButton = modal.querySelector(".create-modal-close");
        if (closeButton instanceof HTMLElement) {
            closeButton.focus();
        }
    }

    function normalizeChildPage() {
        try {
            const childDocument = frame.contentDocument;
            if (!childDocument?.body) {
                return;
            }
            childDocument.body.classList.add("modal-page");
            childDocument
                .querySelectorAll("[data-create-modal-root]")
                .forEach((element) => element.remove());
            frame.contentWindow?.scrollTo({ top: 0, left: 0, behavior: "instant" });
        } catch (_error) {
            // La navegación sigue siendo funcional aunque el navegador impida
            // inspeccionar temporalmente el documento durante una carga.
        }
    }

    document.addEventListener("click", (event) => {
        if (
            event.defaultPrevented ||
            event.button !== 0 ||
            event.metaKey ||
            event.ctrlKey ||
            event.shiftKey ||
            event.altKey
        ) {
            return;
        }

        const anchor = event.target instanceof Element
            ? event.target.closest("a[href]")
            : null;
        const url = creationUrlFor(anchor);
        if (!url || !(anchor instanceof HTMLAnchorElement)) {
            return;
        }

        event.preventDefault();
        openModal(anchor, url);
    });

    closeButtons.forEach((button) => {
        button.addEventListener("click", () => closeModal());
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && open) {
            event.preventDefault();
            closeModal();
        }
    });

    window.addEventListener("resize", scheduleFit, { passive: true });

    frame.addEventListener("load", () => {
        if (!open) {
            return;
        }

        setLoading(false);
        normalizeChildPage();
        scheduleFit();
        observeChildSize();

        let currentUrl;
        try {
            currentUrl = new URL(frame.contentWindow.location.href);
        } catch (_error) {
            return;
        }

        const currentPath = currentUrl.pathname.replace(/\/$/, "");
        if (currentPath === initialPath) {
            return;
        }

        const destination = `${currentUrl.pathname}${currentUrl.search}${currentUrl.hash}`;
        closeModal({ restoreFocus: false });
        window.location.assign(destination);
    });
})();
