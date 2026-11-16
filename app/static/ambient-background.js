const ambientScene = document.querySelector(".ambient-scene");

function syncAmbientMotion() {
    ambientScene.classList.toggle("is-paused", document.hidden);
}

document.addEventListener("visibilitychange", syncAmbientMotion);
syncAmbientMotion();
