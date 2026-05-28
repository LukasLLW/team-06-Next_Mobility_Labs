import { Header } from "../../components/common/Header.js";
import { calculateFleetResult } from "../../services/fleetCalculatorService.js";

export function FleetCalculatorPage() {
  setTimeout(initFleetCalculatorPage, 0);

  return `
    <main class="fleet-calculator-page fleet-mode">
      ${Header()}

      <section class="calculator-layout">
        <section class="calculator-card">
          <div class="section-title-row">
            <span class="step-badge">1</span>
            <div>
              <h1>Battery & Charger Setup</h1>
              <p class="section-subtitle">
                Add one or multiple vehicle types in your fleet.
              </p>
            </div>
          </div>

          <div id="vehicleRows" class="vehicle-rows"></div>

          <button id="addVehicleTypeButton" class="add-vehicle-button" type="button">
            + Add vehicle type
          </button>
        </section>

        <section class="calculator-card">
          <div class="section-title-row">
            <span class="step-badge">2</span>
            <h2>Trip / Usage Pattern</h2>
          </div>

          <div class="usage-layout">
            <div id="csvDropzone" class="csv-dropzone">
              <strong>Drop CSV Fahrtenbuch here</strong>
              <span>or click to select a file</span>
              <input id="csvInput" type="file" accept=".csv" hidden />
            </div>

            <label class="field">
              <span>Driving pattern</span>
              <select id="drivingPattern">
                <option value="delivery">Delivery fleet</option>
                <option value="corporate" selected>Corporate pool cars</option>
                <option value="municipal">Municipal vehicles</option>
                <option value="carsharing">Car sharing</option>
                <option value="logistics">Depot based logistics</option>
              </select>
            </label>

            <p id="csvFileName" class="csv-file-name"></p>
          </div>
        </section>

        <button id="calculateButton" class="calculate-button" type="button">
          Calculate
          <span>→</span>
        </button>

        <section id="resultSection" class="result-card hidden">
          <div class="result-header">
            <p>Result</p>

            <div class="period-tabs">
              <button class="period-tab" data-period="week">Per week</button>
              <button class="period-tab active" data-period="month">Per month</button>
              <button class="period-tab" data-period="quarter">Per quarter</button>
            </div>
          </div>

          <div class="result-kpi success">
            <span>Estimated revenue</span>
            <strong id="estimatedRevenue">€0</strong>
          </div>

          <div class="result-kpi warning">
            <span>Battery degradation cost</span>
            <strong id="degradationCost">€0</strong>
          </div>

          <div class="result-kpi success">
            <span>Net Profit</span>
            <strong id="netProfit">€0</strong>
          </div>

          <div class="small-result-grid">
            <div>
              <span>Aggregated capacity</span>
              <strong id="aggregatedCapacity">0 MW</strong>
            </div>

            <div>
              <span>Total vehicles</span>
              <strong id="totalVehicles">0</strong>
            </div>

            <div>
              <span>Utilization</span>
              <strong id="utilization">0%</strong>
            </div>

            <div>
              <span>Break-even</span>
              <strong id="breakEven">-</strong>
            </div>

            <div>
              <span>Risk</span>
              <strong id="risk">-</strong>
            </div>
          </div>
        </section>
      </section>
    </main>
  `;
}

function initFleetCalculatorPage() {
  const vehicleRows = document.querySelector("#vehicleRows");
  const addVehicleTypeButton = document.querySelector("#addVehicleTypeButton");

  const drivingPattern = document.querySelector("#drivingPattern");

  const csvDropzone = document.querySelector("#csvDropzone");
  const csvInput = document.querySelector("#csvInput");
  const csvFileName = document.querySelector("#csvFileName");

  const calculateButton = document.querySelector("#calculateButton");
  const resultSection = document.querySelector("#resultSection");

  const estimatedRevenue = document.querySelector("#estimatedRevenue");
  const degradationCost = document.querySelector("#degradationCost");
  const netProfit = document.querySelector("#netProfit");
  const aggregatedCapacity = document.querySelector("#aggregatedCapacity");
  const totalVehicles = document.querySelector("#totalVehicles");
  const utilization = document.querySelector("#utilization");
  const breakEven = document.querySelector("#breakEven");
  const risk = document.querySelector("#risk");

  if (!vehicleRows || !addVehicleTypeButton || !calculateButton) {
    return;
  }

  const vehiclePresets = {
    custom: {
      label: "Custom",
      batteryCost: 12000,
      batteryCapacity: 77,
      chargerPower: 21,
    },

    "vw-id4": {
      label: "VW ID.4",
      batteryCost: 12000,
      batteryCapacity: 77,
      chargerPower: 21,
    },

    "tesla-model-y": {
      label: "Tesla Model Y",
      batteryCost: 13500,
      batteryCapacity: 75,
      chargerPower: 22,
    },

    "renault-kangoo-e-tech": {
      label: "Renault Kangoo E-Tech",
      batteryCost: 8500,
      batteryCapacity: 45,
      chargerPower: 11,
    },

    "mercedes-e-vito": {
      label: "Mercedes eVito",
      batteryCost: 11000,
      batteryCapacity: 60,
      chargerPower: 11,
    },
  };

  let activePeriod = "month";
  let latestResult = null;

  function createVehicleRow(values = {}) {
    const row = document.createElement("div");
    row.className = "vehicle-row";

    row.innerHTML = `
      <div class="vehicle-row-header">
        <h3>Vehicle type</h3>
        <button class="remove-vehicle-button" type="button">Remove</button>
      </div>

      <div class="vehicle-form-grid">
        <label class="field">
          <span>Vehicle model</span>
          <select class="vehicle-model">
            <option value="custom">Custom</option>
            <option value="vw-id4">VW ID.4</option>
            <option value="tesla-model-y">Tesla Model Y</option>
            <option value="renault-kangoo-e-tech">Renault Kangoo E-Tech</option>
            <option value="mercedes-e-vito">Mercedes eVito</option>
          </select>
        </label>

        <label class="field">
          <span>Battery cost (€)</span>
          <input class="battery-cost" type="number" min="0" value="${values.batteryCost ?? 12000}" />
        </label>

        <label class="field">
          <span>Battery capacity (kWh)</span>
          <input class="battery-capacity" type="number" min="0" value="${values.batteryCapacity ?? 77}" />
        </label>

        <label class="field">
          <span>Charger power (kW)</span>
          <input class="charger-power" type="number" min="0" value="${values.chargerPower ?? 21}" />
        </label>

        <label class="field">
          <span>Number of vehicles</span>
          <input class="vehicle-count" type="number" min="1" value="${values.vehicleCount ?? 50}" />
        </label>
      </div>
    `;

    const modelSelect = row.querySelector(".vehicle-model");
    const batteryCostInput = row.querySelector(".battery-cost");
    const batteryCapacityInput = row.querySelector(".battery-capacity");
    const chargerPowerInput = row.querySelector(".charger-power");
    const removeButton = row.querySelector(".remove-vehicle-button");

    modelSelect.value = values.model ?? "custom";

    modelSelect.addEventListener("change", () => {
      const preset = vehiclePresets[modelSelect.value];

      if (!preset || modelSelect.value === "custom") {
        return;
      }

      batteryCostInput.value = preset.batteryCost;
      batteryCapacityInput.value = preset.batteryCapacity;
      chargerPowerInput.value = preset.chargerPower;
    });

    removeButton.addEventListener("click", () => {
      const rows = vehicleRows.querySelectorAll(".vehicle-row");

      if (rows.length <= 1) {
        return;
      }

      row.remove();
      updateVehicleTitles();
    });

    vehicleRows.appendChild(row);
    updateVehicleTitles();
  }

  function updateVehicleTitles() {
    const rows = vehicleRows.querySelectorAll(".vehicle-row");

    rows.forEach((row, index) => {
      const title = row.querySelector("h3");
      const removeButton = row.querySelector(".remove-vehicle-button");

      title.textContent = `Vehicle type ${index + 1}`;

      removeButton.disabled = rows.length <= 1;
    });
  }

  function getVehicleTypes() {
    return [...vehicleRows.querySelectorAll(".vehicle-row")].map((row) => {
      return {
        model: row.querySelector(".vehicle-model").value,
        batteryCost: Number(row.querySelector(".battery-cost").value),
        batteryCapacity: Number(row.querySelector(".battery-capacity").value),
        chargerPower: Number(row.querySelector(".charger-power").value),
        vehicleCount: Number(row.querySelector(".vehicle-count").value),
      };
    });
  }

  addVehicleTypeButton.addEventListener("click", () => {
    createVehicleRow({
      model: "custom",
      batteryCost: 12000,
      batteryCapacity: 77,
      chargerPower: 21,
      vehicleCount: 10,
    });
  });

  csvDropzone.addEventListener("click", () => {
    csvInput.click();
  });

  csvDropzone.addEventListener("dragover", (event) => {
    event.preventDefault();
    csvDropzone.classList.add("drag-over");
  });

  csvDropzone.addEventListener("dragleave", () => {
    csvDropzone.classList.remove("drag-over");
  });

  csvDropzone.addEventListener("drop", (event) => {
    event.preventDefault();
    csvDropzone.classList.remove("drag-over");

    const file = event.dataTransfer.files[0];
    handleCsvFile(file);
  });

  csvInput.addEventListener("change", () => {
    const file = csvInput.files[0];
    handleCsvFile(file);
  });

  function handleCsvFile(file) {
    if (!file) return;

    if (!file.name.toLowerCase().endsWith(".csv")) {
      csvFileName.textContent = "Only CSV files are supported.";
      csvFileName.classList.add("error");
      return;
    }

    csvFileName.textContent = `Selected file: ${file.name}`;
    csvFileName.classList.remove("error");
  }

  calculateButton.addEventListener("click", () => {
    latestResult = calculateFleetResult({
      vehicleTypes: getVehicleTypes(),
      drivingPattern: drivingPattern.value,
    });

    resultSection.classList.remove("hidden");
    setPeriod(activePeriod);
  });

  document.querySelectorAll(".period-tab").forEach((button) => {
    button.addEventListener("click", () => {
      activePeriod = button.dataset.period;

      document.querySelectorAll(".period-tab").forEach((tab) => {
        tab.classList.remove("active");
      });

      button.classList.add("active");

      if (latestResult) {
        setPeriod(activePeriod);
      }
    });
  });

  function setPeriod(period) {
    const periodResult = latestResult[period];

    estimatedRevenue.textContent = formatEuro(periodResult.revenue);
    degradationCost.textContent = formatEuro(periodResult.degradationCost);
    netProfit.textContent = formatEuro(periodResult.netProfit);

    aggregatedCapacity.textContent = `${latestResult.meta.aggregatedCapacityMW.toFixed(2)} MW`;
    totalVehicles.textContent = latestResult.meta.totalVehicles;
    utilization.textContent = `${latestResult.meta.utilization}%`;
    breakEven.textContent = latestResult.meta.breakEven;
    risk.textContent = latestResult.meta.risk;
  }

  createVehicleRow({
    model: "custom",
    batteryCost: 12000,
    batteryCapacity: 77,
    chargerPower: 21,
    vehicleCount: 50,
  });
}

function formatEuro(value) {
  return new Intl.NumberFormat("de-DE", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  }).format(value);
}