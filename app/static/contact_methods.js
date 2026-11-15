const methodList = document.querySelector("#contact-methods");
const methodTemplate = document.querySelector("#contact-method-template");
const addMethodButton = document.querySelector("#add-method");

function removeMethod(event) {
    event.currentTarget.closest(".method-row").remove();
}

function bindRemoveButton(button) {
    button.addEventListener("click", removeMethod);
}

methodList.querySelectorAll(".remove-method").forEach(bindRemoveButton);

addMethodButton.addEventListener("click", () => {
    const methodRow = methodTemplate.content.cloneNode(true);
    const removeButton = methodRow.querySelector(".remove-method");
    bindRemoveButton(removeButton);
    methodList.appendChild(methodRow);
    methodList.lastElementChild.querySelector("select").focus();
});
