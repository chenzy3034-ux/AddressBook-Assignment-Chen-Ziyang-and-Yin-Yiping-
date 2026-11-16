document.querySelector("#delete-contact").addEventListener("submit", (event) => {
    if (!window.confirm("Delete this contact?")) {
        event.preventDefault();
    }
});
