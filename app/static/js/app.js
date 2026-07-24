const menuButton = document.getElementById("menuToggle");
const sidebar = document.getElementById("sidebar");

if (menuButton && sidebar) {
    menuButton.addEventListener("click", () => {
        sidebar.classList.toggle("open");
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
            sidebar.classList.remove("open");
        }
    });
}
