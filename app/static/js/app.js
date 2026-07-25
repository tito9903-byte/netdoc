const menuButton = document.getElementById("menuToggle");
const sidebar = document.getElementById("sidebar");

if (menuButton && sidebar) {
    const setOpen = (open) => {
        sidebar.classList.toggle("open", open);
        menuButton.setAttribute("aria-expanded", String(open));
    };

    menuButton.addEventListener("click", () => {
        setOpen(!sidebar.classList.contains("open"));
    });

    document.addEventListener("click", (event) => {
        const target = event.target;
        if (!(target instanceof Node)) {
            return;
        }
        const clickedOutside =
            !sidebar.contains(target) &&
            !menuButton.contains(target);
        if (clickedOutside) {
            setOpen(false);
        }
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && sidebar.classList.contains("open")) {
            setOpen(false);
            menuButton.focus();
        }
    });

    sidebar.addEventListener("click", (event) => {
        const target = event.target;
        if (
            window.matchMedia("(max-width: 900px)").matches &&
            target instanceof Element &&
            target.closest("a.nav-item")
        ) {
            setOpen(false);
        }
    });
}

const navGroups = document.querySelectorAll("details[data-nav-group]");

navGroups.forEach((group) => {
    const key = group.getAttribute("data-nav-group");
    const isActive = group.getAttribute("data-active") === "true";

    if (!key) {
        return;
    }

    if (isActive) {
        group.open = true;
    } else {
        const stored = window.localStorage.getItem(`netdoc-nav-${key}`);
        if (stored === "open") {
            group.open = true;
        } else if (stored === "closed") {
            group.open = false;
        }
    }

    group.addEventListener("toggle", () => {
        window.localStorage.setItem(
            `netdoc-nav-${key}`,
            group.open ? "open" : "closed",
        );
    });
});

// Progreso visual inmediato al cambiar de pantalla.
const navigationBar = document.createElement("div");
navigationBar.setAttribute("aria-hidden", "true");
navigationBar.style.cssText = [
    "position:fixed",
    "top:0",
    "left:0",
    "z-index:9999",
    "height:3px",
    "width:0",
    "opacity:0",
    "pointer-events:none",
    "background:linear-gradient(90deg,#20c8d2,#75f1f5)",
    "box-shadow:0 0 12px rgba(32,200,210,.65)",
    "transition:width 180ms ease,opacity 140ms ease",
].join(";");
document.body.appendChild(navigationBar);

let navigationTimer = 0;

function startNavigationFeedback() {
    window.clearTimeout(navigationTimer);
    navigationBar.style.opacity = "1";
    navigationBar.style.width = "18%";
    window.requestAnimationFrame(() => {
        navigationBar.style.width = "72%";
    });
    navigationTimer = window.setTimeout(() => {
        navigationBar.style.width = "88%";
    }, 500);
}

function finishNavigationFeedback() {
    window.clearTimeout(navigationTimer);
    navigationBar.style.width = "100%";
    window.setTimeout(() => {
        navigationBar.style.opacity = "0";
        navigationBar.style.width = "0";
    }, 120);
}

window.addEventListener("pageshow", finishNavigationFeedback);

// Prefetch solo cuando el usuario demuestra intención de abrir un enlace.
const prefetched = new Set();
const prefetchTimers = new WeakMap();
const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
const allowPrefetch = !(connection && connection.saveData);

function eligibleInternalLink(anchor) {
    if (!(anchor instanceof HTMLAnchorElement)) {
        return null;
    }
    if (
        anchor.target ||
        anchor.hasAttribute("download") ||
        anchor.dataset.noPrefetch === "true" ||
        anchor.getAttribute("href")?.startsWith("#")
    ) {
        return null;
    }

    let url;
    try {
        url = new URL(anchor.href, window.location.href);
    } catch (_error) {
        return null;
    }

    if (
        url.origin !== window.location.origin ||
        url.pathname === window.location.pathname && url.search === window.location.search ||
        url.pathname.endsWith(".pdf") ||
        url.pathname.startsWith("/media/") ||
        url.pathname === "/logout"
    ) {
        return null;
    }
    return url;
}

function prefetchLink(anchor) {
    if (!allowPrefetch) {
        return;
    }
    const url = eligibleInternalLink(anchor);
    if (!url || prefetched.has(url.href)) {
        return;
    }
    prefetched.add(url.href);
    const link = document.createElement("link");
    link.rel = "prefetch";
    link.href = url.href;
    link.as = "document";
    document.head.appendChild(link);
}

document.addEventListener("pointerover", (event) => {
    const anchor = event.target instanceof Element
        ? event.target.closest("a[href]")
        : null;
    if (!(anchor instanceof HTMLAnchorElement) || prefetchTimers.has(anchor)) {
        return;
    }
    const timer = window.setTimeout(() => {
        prefetchTimers.delete(anchor);
        prefetchLink(anchor);
    }, 120);
    prefetchTimers.set(anchor, timer);
});

document.addEventListener("pointerout", (event) => {
    const anchor = event.target instanceof Element
        ? event.target.closest("a[href]")
        : null;
    if (!(anchor instanceof HTMLAnchorElement)) {
        return;
    }
    const timer = prefetchTimers.get(anchor);
    if (timer) {
        window.clearTimeout(timer);
        prefetchTimers.delete(anchor);
    }
});

document.addEventListener("focusin", (event) => {
    const anchor = event.target instanceof Element
        ? event.target.closest("a[href]")
        : null;
    if (anchor instanceof HTMLAnchorElement) {
        prefetchLink(anchor);
    }
});

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
    if (eligibleInternalLink(anchor)) {
        startNavigationFeedback();
    }
});

document.addEventListener("submit", () => {
    startNavigationFeedback();
});
