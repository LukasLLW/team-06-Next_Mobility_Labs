import { Header } from "../../components/common/Header.js";
import { calculateFleetResult } from "../../services/fleetCalculatorService.js?v=1000";

console.log("FleetCalculatorPage loaded");

export function FleetCalculatorPage() {
  return `
    <main class="fleet-calculator-page fleet-mode">
      ${Header()}

      <section class="calculator-layout">
      <section class="calculator-card simulation-settings-card">
  <div class="section-title-row">
    <div>
      <h1>Simulation Settings</h1>
      <p class="section-subtitle">
        Define the simulation start date and duration used by the backend model.
      </p>
    </div>
  </div>

  <div class="simulation-settings-grid">
    <label class="field">
      <span>Simulation start date</span>
      <input id="simulationStartDate" type="date" value="2025-06-01" />
    </label>

    <label class="field">
      <span>Simulation duration days</span>
      <input id="simulationDays" type="number" min="1" max="365" value="14" />
    </label>
  </div>
</section>
        <section class="calculator-card">
          <div class="section-title-row">
            <div>
              <h1>Battery, Charger & Usage Setup</h1>
              <p class="section-subtitle">
                Add one or multiple vehicle types. Each vehicle type can use a preset driving pattern or its own CSV Fahrtenbuch.
              </p>
            </div>
          </div>

          <div id="vehicleRows" class="vehicle-rows"></div>

          <button id="addVehicleTypeButton" class="add-vehicle-button" type="button">
            + Add vehicle type
          </button>
        </section>

        <button id="calculateButton" class="calculate-button" type="button">
          Calculate
          <span>→</span>
        </button>

        <section id="resultSection" class="result-card hidden">
          <div class="result-header">
            <p>Result</p>
          </div>

          <div class="result-period-grid">
            <div class="result-period-card">
              <h3>Per week</h3>

              <div class="result-kpi success">
                <span>Estimated revenue</span>
                <strong id="weekEstimatedRevenue">€0</strong>
              </div>

              <div class="result-kpi warning">
                <span>(Best Case) Battery degradation cost</span>
                <strong id="weekDegradationCost">€0</strong>
              </div>

              <div class="result-kpi success">
                <span>(Best Case) Net Profit</span>
                <strong id="weekNetProfit">€0</strong>
              </div>
            </div>

            <div class="result-period-card">
              <h3>Per month</h3>

              <div class="result-kpi success">
                <span>Estimated revenue</span>
                <strong id="monthEstimatedRevenue">€0</strong>
              </div>

              <div class="result-kpi warning">
                <span>(Best Case) Battery degradation cost</span>
                <strong id="monthDegradationCost">€0</strong>
              </div>

              <div class="result-kpi success">
                <span>(Best Case) Net Profit</span>
                <strong id="monthNetProfit">€0</strong>
              </div>
            </div>
          </div>
        </section>
      </section>
    </main>
  `;
}

export function initFleetCalculatorPage() {
  const vehicleRows = document.querySelector("#vehicleRows");
  const addVehicleTypeButton = document.querySelector("#addVehicleTypeButton");
 const simulationStartDate = document.querySelector("#simulationStartDate");
const simulationDays = document.querySelector("#simulationDays");
  const calculateButton = document.querySelector("#calculateButton");
  const resultSection = document.querySelector("#resultSection");

  const weekEstimatedRevenue = document.querySelector("#weekEstimatedRevenue");
  const weekDegradationCost = document.querySelector("#weekDegradationCost");
  const weekNetProfit = document.querySelector("#weekNetProfit");

  const monthEstimatedRevenue = document.querySelector("#monthEstimatedRevenue");
  const monthDegradationCost = document.querySelector("#monthDegradationCost");
  const monthNetProfit = document.querySelector("#monthNetProfit");

  if (!vehicleRows || !addVehicleTypeButton || !calculateButton) {
    return;
  }

const vehiclePresets = {
  custom: {
    label: "Custom",
    batteryCost: 12000,
    batteryCapacity: 77,
    chargerPower: 21,
    eolLossPct: 20,
  },

  "hyundai-ioniq-5": {
    label: "Hyundai IONIQ 5",
    batteryCost: 11500,
    batteryCapacity: 77,
    chargerPower: 11,
    eolLossPct: 20,
  },

  "kia-ev6": {
    label: "Kia EV6",
    batteryCost: 11500,
    batteryCapacity: 77,
    chargerPower: 11,
    eolLossPct: 20,
  },

  "nissan-leaf": {
    label: "Nissan Leaf",
    batteryCost: 7500,
    batteryCapacity: 40,
    chargerPower: 6.6,
    eolLossPct: 20,
  },

  "mitsubishi-outlander-phev": {
    label: "Mitsubishi Outlander PHEV",
    batteryCost: 3500,
    batteryCapacity: 13.8,
    chargerPower: 3.7,
    eolLossPct: 20,
  },

  "byd-atto-3": {
    label: "BYD Atto 3",
    batteryCost: 9000,
    batteryCapacity: 60,
    chargerPower: 11,
    eolLossPct: 20,
  },

  "byd-han": {
    label: "BYD Han",
    batteryCost: 12500,
    batteryCapacity: 85,
    chargerPower: 11,
    eolLossPct: 20,
  },

  "byd-tang": {
    label: "BYD Tang",
    batteryCost: 12500,
    batteryCapacity: 86,
    chargerPower: 11,
    eolLossPct: 20,
  },

  "vw-id3": {
    label: "Volkswagen ID.3",
    batteryCost: 9000,
    batteryCapacity: 58,
    chargerPower: 11,
    eolLossPct: 20,
  },

  "vw-id4": {
    label: "Volkswagen ID.4",
    batteryCost: 12000,
    batteryCapacity: 77,
    chargerPower: 11,
    eolLossPct: 20,
  },

  "vw-id7": {
    label: "Volkswagen ID.7",
    batteryCost: 13000,
    batteryCapacity: 77,
    chargerPower: 11,
    eolLossPct: 20,
  },

  "bmw-ix": {
    label: "BMW iX",
    batteryCost: 16000,
    batteryCapacity: 105,
    chargerPower: 11,
    eolLossPct: 20,
  },

  "bmw-i4": {
    label: "BMW i4",
    batteryCost: 12500,
    batteryCapacity: 84,
    chargerPower: 11,
    eolLossPct: 20,
  },

  "bmw-i5": {
    label: "BMW i5",
    batteryCost: 12500,
    batteryCapacity: 81,
    chargerPower: 11,
    eolLossPct: 20,
  },
};

  function createVehicleRow(values = {}) {
    const row = document.createElement("div");
    row.className = "vehicle-row";
    row.csvFile = null;

    row.innerHTML = `
      <div class="vehicle-row-header">
        <h3>Vehicle type</h3>
        <button class="remove-vehicle-button" type="button">Remove</button>
      </div>

      <div class="vehicle-form-grid">
        <label class="field">
          <span>Vehicle model</span>
          <select class="vehicle-model">
  ${Object.entries(vehiclePresets)
    .map(([value, preset]) => {
      return `<option value="${value}">${preset.label}</option>`;
    })
    .join("")}
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
  <span>Max. accepted battery wear (%)</span>
  <input class="eol-loss-pct" type="number" min="1" max="100" value="${values.eolLossPct ?? 20}" />
</label>

        <label class="field">
          <span>Number of vehicles</span>
          <input class="vehicle-count" type="number" min="1" value="${values.vehicleCount ?? 50}" />
        </label>
      </div>

      <div class="vehicle-usage-box">
        <div class="vehicle-usage-header">
          <h4>Trip / Usage Pattern</h4>
          <p>Choose a preset driving pattern or upload a CSV Fahrtenbuch for this vehicle type.</p>
        </div>

        <div class="usage-choice-grid">
          <label class="field">
            <span>Driving pattern</span>
            <select class="driving-pattern">
              <option value="delivery">Delivery fleet</option>
              <option value="corporate" selected>Corporate pool cars</option>
              <option value="municipal">Municipal vehicles</option>
              <option value="carsharing">Car sharing</option>
              <option value="logistics">Depot based logistics</option>
            </select>
          </label>

          <div class="or-divider">
            <span>OR</span>
          </div>

          <div class="csv-dropzone vehicle-csv-dropzone">
            <strong>Drop CSV Fahrtenbuch</strong>
            <span>or click to select</span>
            <input class="csv-input" type="file" accept=".csv" hidden />
            <p class="csv-file-name"></p>
          </div>
        </div>
      </div>
    `;

const modelSelect = row.querySelector(".vehicle-model");
const batteryCostInput = row.querySelector(".battery-cost");
const batteryCapacityInput = row.querySelector(".battery-capacity");
const chargerPowerInput = row.querySelector(".charger-power");
const eolLossPctInput = row.querySelector(".eol-loss-pct");
const removeButton = row.querySelector(".remove-vehicle-button");

const csvDropzone = row.querySelector(".vehicle-csv-dropzone");
const csvInput = row.querySelector(".csv-input");
const csvFileName = row.querySelector(".csv-file-name");

modelSelect.value = values.model ?? "custom";

modelSelect.addEventListener("change", () => {
  const preset = vehiclePresets[modelSelect.value];

  if (!preset || modelSelect.value === "custom") {
    return;
  }

  batteryCostInput.value = preset.batteryCost;
  batteryCapacityInput.value = preset.batteryCapacity;
  chargerPowerInput.value = preset.chargerPower;
  eolLossPctInput.value = preset.eolLossPct;
});

    removeButton.addEventListener("click", () => {
      const rows = vehicleRows.querySelectorAll(".vehicle-row");

      if (rows.length <= 1) {
        return;
      }

      row.remove();
      updateVehicleTitles();
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
      handleVehicleCsvFile(file, row, csvFileName);
    });

    csvInput.addEventListener("change", () => {
      const file = csvInput.files[0];
      handleVehicleCsvFile(file, row, csvFileName);
    });

    vehicleRows.appendChild(row);
    updateVehicleTitles();
  }

  function handleVehicleCsvFile(file, row, csvFileNameElement) {
    if (!file) return;

    if (!file.name.toLowerCase().endsWith(".csv")) {
      row.csvFile = null;
      csvFileNameElement.textContent = "Only CSV files are supported.";
      csvFileNameElement.classList.add("error");
      return;
    }

    row.csvFile = file;
    csvFileNameElement.textContent = `Selected file: ${file.name}`;
    csvFileNameElement.classList.remove("error");
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
        eolLossPct: Number(row.querySelector(".eol-loss-pct").value),
        vehicleCount: Number(row.querySelector(".vehicle-count").value),
        drivingPattern: row.querySelector(".driving-pattern").value,
        hasCsv: row.csvFile instanceof File,
        csvFile: row.csvFile,
      };
    });
  }

  addVehicleTypeButton.addEventListener("click", () => {
  createVehicleRow({
    model: "custom",
    batteryCost: 12000,
    batteryCapacity: 77,
    chargerPower: 21,
    eolLossPct: 20,
    vehicleCount: 10,
  });
});

  calculateButton.addEventListener("click", async () => {
    console.log("Calculate button clicked");
    console.log("Vehicle types:", getVehicleTypes());

    calculateButton.disabled = true;
    calculateButton.innerHTML = "Calculating...";

    try {
      const result = await calculateFleetResult({
  vehicleTypes: getVehicleTypes(),
  fromDate: simulationStartDate.value,
  days: Number(simulationDays.value),
});

      renderResult(result);
      resultSection.classList.remove("hidden");
    } catch (error) {
      console.error(error);
      alert("Calculation failed. Check the console for details.");
    } finally {
      calculateButton.disabled = false;
      calculateButton.innerHTML = `Calculate <span>→</span>`;
    }
  });

  function renderResult(result) {
    weekEstimatedRevenue.textContent = formatEuro(result.week.revenue);
    weekDegradationCost.textContent = formatEuro(result.week.degradationCost);
    weekNetProfit.textContent = formatEuro(result.week.netProfit);

    monthEstimatedRevenue.textContent = formatEuro(result.month.revenue);
    monthDegradationCost.textContent = formatEuro(result.month.degradationCost);
    monthNetProfit.textContent = formatEuro(result.month.netProfit);
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