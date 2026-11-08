function fieldNumber(id) {
  const field = document.getElementById(id);
  if (!field) return NaN;
  return Number(String(field.value).trim().replace(",", "."));
}

function setEquivalent(id, value) {
  const output = document.getElementById(id);
  if (!output) return;
  output.textContent = Number.isFinite(value) ? value.toLocaleString("pt-BR", { maximumSignificantDigits: 7 }) : "-";
}

function concentrationEquivalent() {
  const type = document.getElementById("id_tipo_concentracao")?.value || "cv";
  const value = fieldNumber("id_phi_total");
  const rhoS = fieldNumber("id_rho_s");
  const rhoL = fieldNumber("id_rho_l");
  if (!(value > 0 && value < 1) || !(rhoS > 0) || !(rhoL > 0)) return NaN;
  if (type === "cv") return value;
  if (type === "cw") return (value * rhoL) / (rhoS * (1 - value) + value * rhoL);
  return NaN;
}

function updateConcentrationField() {
  const type = document.getElementById("id_tipo_concentracao")?.value || "cv";
  const field = document.getElementById("concentration-value-field");
  if (field) {
    const label = field.querySelector("[data-concentration-label]");
    const symbol = field.querySelector("[data-concentration-symbol]");
    const help = field.querySelector("[data-concentration-help]");
    if (label) label.textContent = type === "cw" ? field.dataset.labelCw : field.dataset.labelCv;
    if (symbol) symbol.innerHTML = type === "cw" ? field.dataset.symbolCw : field.dataset.symbolCv;
    if (help) help.textContent = type === "cw" ? field.dataset.helpCw : field.dataset.helpCv;
  }
  const equivalent = document.getElementById("concentration-equivalent");
  if (equivalent) equivalent.hidden = type !== "cw";
  setEquivalent("equiv-cv", concentrationEquivalent() * 100);
}

function updateRheologyFields() {
  const mode = document.getElementById("id_entrada_reologia")?.value || "laboratorio";
  const fluidType = document.getElementById("id_tipo_fluido_homogeneo")?.value || "bingham";
  const coefficientSymbol = fluidType === "bingham" ? "η" : "K";

  document.querySelectorAll("[data-reologia-group]").forEach((group) => {
    group.hidden = group.dataset.reologiaGroup !== mode;
  });
  document.querySelectorAll("[data-coefficient-symbol]").forEach((symbol) => {
    symbol.textContent = coefficientSymbol;
  });

  const tauField = document.querySelector("[data-tau0-direto]");
  if (tauField) tauField.hidden = mode === "direta" && fluidType === "powerlaw";
  document.querySelectorAll("[data-coeficiente-direto]").forEach((field) => {
    field.hidden = mode === "direta" && (
      (field.dataset.coeficienteDireto === "bingham" && fluidType !== "bingham")
      || (field.dataset.coeficienteDireto === "nao-bingham" && fluidType === "bingham")
    );
  });

  const phi = concentrationEquivalent();
  const mu = fieldNumber("id_mu_l_cp");
  const adjustment = mu / 1.002;

  const labA = fieldNumber("id_A");
  const labB = fieldNumber("id_B");
  const labBLine = fieldNumber("id_B_linha");
  const labTauDynCm2 = labA * (phi ** labB);
  const labCoefficientReference = 10 ** ((phi / (1 - phi)) * labBLine);
  setEquivalent("lab-tau-pa", labTauDynCm2 * 0.1);
  setEquivalent("lab-tau-dyn", labTauDynCm2);
  setEquivalent("lab-coef-reference", labCoefficientReference);
  setEquivalent("lab-coef-adjusted", labCoefficientReference * adjustment);

  const tauInput = fluidType === "powerlaw" ? 0 : fieldNumber("id_tau0_direto");
  const tauUnit = document.getElementById("id_tau0_unidade")?.value;
  const coefficient = fluidType === "bingham" ? fieldNumber("id_eta_direta") : fieldNumber("id_k_direto");
  const coefficientUnit = document.getElementById(fluidType === "bingham" ? "id_eta_unidade" : "id_k_unidade")?.value;

  let tauDynCm2 = tauInput;
  if (tauUnit === "pa") tauDynCm2 *= 10;
  if (tauUnit === "kpa") tauDynCm2 *= 10000;

  let coefficientCp = coefficient;
  if (coefficientUnit === "pa_s") coefficientCp *= 1000;

  const adjustedCoefficient = coefficientCp * adjustment;
  const A = tauDynCm2 / phi;
  const BLine = Math.log10(coefficientCp) * ((1 - phi) / phi);

  setEquivalent("equiv-a", A);
  setEquivalent("equiv-b", 1);
  setEquivalent("equiv-b-linha", BLine);
  setEquivalent("equiv-coef-reference", coefficientCp);
  setEquivalent("equiv-coef-ajustado", adjustedCoefficient);
}

[
  "id_tipo_concentracao",
  "id_entrada_reologia",
  "id_tipo_fluido_homogeneo",
  "id_phi_total",
  "id_mu_l_cp",
  "id_A",
  "id_B",
  "id_B_linha",
  "id_tau0_direto",
  "id_tau0_unidade",
  "id_eta_direta",
  "id_eta_unidade",
  "id_k_direto",
  "id_k_unidade",
  "id_rho_s",
  "id_rho_l",
].forEach((id) => document.getElementById(id)?.addEventListener("input", () => {
  updateConcentrationField();
  updateRheologyFields();
}));

updateConcentrationField();
updateRheologyFields();
