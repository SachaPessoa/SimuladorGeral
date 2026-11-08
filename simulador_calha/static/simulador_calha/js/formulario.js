const geometry = document.getElementById("id_geometria");
const rheology = document.getElementById("id_entrada_reologia");
function updateGeometry() {
  document.querySelectorAll("[data-geometry]").forEach((group) => {
    group.hidden = group.dataset.geometry !== geometry.value;
  });
}
function updateRheology() {
  document.querySelectorAll("[data-reologia-group]").forEach((group) => {
    group.hidden = group.dataset.reologiaGroup !== rheology.value;
  });
}
if (geometry) { geometry.addEventListener("change", updateGeometry); updateGeometry(); }
if (rheology) { rheology.addEventListener("change", updateRheology); updateRheology(); }
