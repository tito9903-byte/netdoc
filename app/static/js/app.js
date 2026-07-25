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
