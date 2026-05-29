console.log("REAL service loaded: src/services/fleetCalculatorService.js");

const USE_PYTHON_BACKEND = true;
const PYTHON_BACKEND_URL = "http://127.0.0.1:8000/api/fleet/calculate";

const drivingPatternConfig = {
  delivery: {
    availableHoursPerDay: 10,
    utilization: 0.58,
    revenuePerKwPerHour: 0.075,
  },

  corporate: {
    availableHoursPerDay: 14,
    utilization: 0.67,
    revenuePerKwPerHour: 0.083,
  },

  municipal: {
    availableHoursPerDay: 13,
    utilization: 0.62,
    revenuePerKwPerHour: 0.078,
  },

  carsharing: {
    availableHoursPerDay: 8,
    utilization: 0.45,
    revenuePerKwPerHour: 0.07,
  },

  logistics: {
    availableHoursPerDay: 11,
    utilization: 0.6,
    revenuePerKwPerHour: 0.08,
  },
};

export async function calculateFleetResult(input) {
  console.log("calculateFleetResult called with:", input);

  if (USE_PYTHON_BACKEND) {
    return await calculateWithPythonBackend(input);
  }

  return calculateWithDemoModel(input);
}

async function calculateWithPythonBackend(input) {
  console.log("Calling Python backend:", PYTHON_BACKEND_URL);

  const vehicleTypes = Array.isArray(input.vehicleTypes)
    ? input.vehicleTypes
    : [];

  const files = [];

  const vehicleTypesForBackend = vehicleTypes.map((vehicleType) => {
    const hasValidCsv = vehicleType.csvFile instanceof File;

    const uploadIndex = hasValidCsv ? files.length : null;

    if (hasValidCsv) {
      files.push(vehicleType.csvFile);
    }

    return {
      model: vehicleType.model,
      batteryCost: vehicleType.batteryCost,
      batteryCapacity: vehicleType.batteryCapacity,
      chargerPower: vehicleType.chargerPower,
      vehicleCount: vehicleType.vehicleCount,
      drivingPattern: vehicleType.drivingPattern,
      hasCsv: hasValidCsv,
      uploadIndex,
    };
  });

  const payload = {
    vehicleTypes: vehicleTypesForBackend,
    fromDate: "2025-06-01",
    days: 14,
    useFcr: true,
    assumePoolSufficient: true,
  };

  const formData = new FormData();
  formData.append("payload", JSON.stringify(payload));

  files.forEach((file) => {
    formData.append("tripLogs", file, file.name);
  });

  console.log("Payload sent to backend:", payload);
  console.log("Files sent to backend:", files);

  const response = await fetch(PYTHON_BACKEND_URL, {
    method: "POST",
    body: formData,
  });

  console.log("Backend response status:", response.status);

  if (!response.ok) {
    const errorText = await response.text();
    console.error("Backend error response:", errorText);
    throw new Error(`Python backend failed with status ${response.status}`);
  }

  const result = await response.json();

  console.log("Backend result:", result);

  if (!result.ok) {
    throw new Error(result.error || "Python backend returned ok=false");
  }

  return {
    week: result.week,
    month: result.month,
    raw: result.raw,
  };
}

function calculateWithDemoModel(input) {
  console.log("Using frontend demo fallback model.");

  const vehicleTypes = Array.isArray(input.vehicleTypes)
    ? input.vehicleTypes
    : [];

  let dailyRevenue = 0;
  let dailyDegradationCost = 0;

  vehicleTypes.forEach((vehicleType) => {
    const config =
      drivingPatternConfig[vehicleType.drivingPattern] ||
      drivingPatternConfig.corporate;

    const vehicleCount = cleanNumber(vehicleType.vehicleCount);
    const batteryCost = cleanNumber(vehicleType.batteryCost);
    const batteryCapacity = cleanNumber(vehicleType.batteryCapacity);
    const chargerPower = cleanNumber(vehicleType.chargerPower);

    const usablePowerPerVehicle = Math.min(chargerPower, batteryCapacity * 0.35);
    const capacityKw = usablePowerPerVehicle * vehicleCount;
    const batteryValue = batteryCost * vehicleCount;

    const typeDailyRevenue =
      capacityKw *
      config.availableHoursPerDay *
      config.utilization *
      config.revenuePerKwPerHour;

    const typeDailyDegradationCost =
      batteryValue * 0.00025 * config.utilization;

    dailyRevenue += typeDailyRevenue;
    dailyDegradationCost += typeDailyDegradationCost;
  });

  return {
    week: buildPeriodResult(dailyRevenue, dailyDegradationCost, 7),
    month: buildPeriodResult(dailyRevenue, dailyDegradationCost, 365 / 12),
  };
}

function buildPeriodResult(dailyRevenue, dailyDegradationCost, days) {
  const revenue = dailyRevenue * days;
  const degradationCost = dailyDegradationCost * days;

  return {
    revenue,
    degradationCost,
    netProfit: revenue - degradationCost,
  };
}

function cleanNumber(value) {
  const number = Number(value);

  if (Number.isNaN(number) || number < 0) {
    return 0;
  }

  return number;
}