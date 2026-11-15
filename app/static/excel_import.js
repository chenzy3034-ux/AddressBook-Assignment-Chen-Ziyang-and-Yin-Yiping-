const excelFileInput = document.querySelector("#excel-file-input");
const selectedFileName = document.querySelector("#selected-file-name");

excelFileInput.addEventListener("change", () => {
    selectedFileName.textContent = excelFileInput.files.length
        ? excelFileInput.files[0].name
        : "No file selected";
});
