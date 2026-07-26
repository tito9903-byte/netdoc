(() => {
    const modal = document.querySelector("[data-create-modal-root]");
    const frame = modal?.querySelector("[data-create-modal-frame]");
    const title = modal?.querySelector("#createModalTitle");
    const loading = modal?.querySelector("[data-create-modal-loading]");
    const closeButtons = modal?.querySelectorAll("[data-create-modal-close]") || [];
    const createPathPattern = /(?:\/actions)?\/new\/?$/;

    if (!(modal instanceof HTMLElement) || !(frame instanceof HTMLIFrameElement)) {
        return;
    }

    let opener = null;
    let initialPath = "";
    let open = false;

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

    function setLoading(visible) {
        if (!(loading instanceof HTMLElement)) {
            return;
        }
        loading.hidden = !visible;
    }

    function closeModal({ restoreFocus = true } = {}) {
        if (!open) {
            return;
        }

        open = false;
        modal.hidden = true;
        modal.setAttribute("aria-hidden", "true");
        document.body.classList.remove("create-modal-open");
        frame.removeAttribute("src");
        frame.dataset.initialUrl = "";
        initialPath = "";
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

    frame.addEventListener("load", () => {
        if (!open) {
            return;
        }

        setLoading(false);
        normalizeChildPage();

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
