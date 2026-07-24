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
