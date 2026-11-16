document.querySelector("#delete-contact").addEventListener("submit", (event) => {
    if (!window.confirm(event.currentTarget.dataset.confirm)) {
        event.preventDefault();
    }
});
