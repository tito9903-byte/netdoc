const rackVisual = document.getElementById("rackVisual");
const zoomButtons = document.querySelectorAll("[data-rack-zoom]");
const deviceBlocks = document.querySelectorAll("[data-rack-inspector-device]");

const inspectorFields = {
    name: document.getElementById("inspectorDeviceName"),
    model: document.getElementById("inspectorDeviceModel"),
    position: document.getElementById("inspectorDevicePosition"),
    height: document.getElementById("inspectorDeviceHeight"),
    face: document.getElementById("inspectorDeviceFace"),
    status: document.getElementById("inspectorDeviceStatus"),
};

function setRackZoom(zoom) {
    if (!rackVisual) {
        return;
    }

    const allowedZooms = new Set([
        "compact",
        "normal",
        "detailed",
    ]);
    const selectedZoom = allowedZooms.has(zoom)
        ? zoom
        : "normal";

    rackVisual.dataset.zoom = selectedZoom;
    localStorage.setItem("netdocRackZoom", selectedZoom);

    zoomButtons.forEach((button) => {
        button.classList.toggle(
            "active",
            button.dataset.rackZoom === selectedZoom,
        );
    });
}

function showDeviceInformation(block) {
    if (!(block instanceof HTMLElement)) {
        return;
    }

    if (inspectorFields.name) {
        inspectorFields.name.textContent =
            block.dataset.deviceName || "Sin nombre";
    }
    if (inspectorFields.model) {
        inspectorFields.model.textContent =
            block.dataset.deviceModel || "—";
    }
    if (inspectorFields.position) {
        inspectorFields.position.textContent =
            block.dataset.devicePosition || "—";
    }
    if (inspectorFields.height) {
        inspectorFields.height.textContent =
            block.dataset.deviceHeight || "—";
    }
    if (inspectorFields.face) {
        inspectorFields.face.textContent =
            block.dataset.deviceFace || "—";
    }
    if (inspectorFields.status) {
        inspectorFields.status.textContent =
            block.dataset.deviceStatus || "—";
    }
}

zoomButtons.forEach((button) => {
    button.addEventListener("click", () => {
        setRackZoom(button.dataset.rackZoom || "normal");
    });
});

deviceBlocks.forEach((block) => {
    ["mouseenter", "focus", "click"].forEach((eventName) => {
        block.addEventListener(eventName, () => {
            showDeviceInformation(block);
        });
    });
});

const savedZoom =
    localStorage.getItem("netdocRackZoom") || "normal";
setRackZoom(savedZoom);
