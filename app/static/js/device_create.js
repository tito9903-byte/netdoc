const manufacturerSelect = document.getElementById("manufacturer_id");
const deviceTypeSelect = document.getElementById("device_type_id");
const siteSelect = document.getElementById("site_id");
const rackSelect = document.getElementById("rack_id");

function filterOptions(selectElement, predicate) {
    if (!selectElement) {
        return;
    }

    const selectedValue = selectElement.value;
    let selectedVisible = false;

    for (const option of selectElement.options) {
        if (!option.value) {
            option.hidden = false;
            continue;
        }

        const visible = predicate(option);
        option.hidden = !visible;

        if (visible && option.value === selectedValue) {
            selectedVisible = true;
        }
    }

    if (selectedValue && !selectedVisible) {
        selectElement.value = "";
    }
}

function filterDeviceTypes() {
    if (!manufacturerSelect || !deviceTypeSelect) {
        return;
    }

    const manufacturerId = manufacturerSelect.value;

    filterOptions(
        deviceTypeSelect,
        (option) => {
            return (
                !manufacturerId
                || option.dataset.manufacturerId === manufacturerId
            );
        },
    );
}

function filterRacks() {
    if (!siteSelect || !rackSelect) {
        return;
    }

    const siteId = siteSelect.value;

    filterOptions(
        rackSelect,
        (option) => {
            return (
                !siteId
                || option.dataset.siteId === siteId
            );
        },
    );
}

manufacturerSelect?.addEventListener(
    "change",
    filterDeviceTypes,
);

siteSelect?.addEventListener(
    "change",
    filterRacks,
);

filterDeviceTypes();
filterRacks();
