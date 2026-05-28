const USE_PYTHON_BACKEND = false;

const PYTHON_BACKEND_URL = "http://localhost:8000/api/fleet/calculate";

const drivingPatternConfig = {
  delivery: {
    availableHoursPerDay: 10,
    utilization: 0.58,
    revenuePerKwPerHour: 0.075,
    risk: "Medium",
  },

  corporate: {
    availableHoursPerDay: 14,
    utilization: 0.67,
    revenuePerKwPerHour: 0.083,
    risk: "Low",
  },

  municipal: {
    availableHoursPerDay: 13,
    utilization: 0.62,
    revenuePerKwPerHour: 0.078,
    risk: "Low",
  },

  carsharing: {
    availableHoursPerDay: 8,
    utilization: 0.45,
    revenuePerKwPerHour: 0.07,
    risk: "Medium",
  },

  logistics: {
    availableHoursPerDay: 11,
    utilization: 0.6,
    revenuePerKwPerHour: 0.08,
    risk: "Medium",
  },
};

export async function calculateFleetResult(input) {
  if (USE_PYTHON_BACKEND) {
    return calculateWithPythonBackend(input);
  }

  return calculateWithDemoModel(input);
}

async function calculateWithPythonBackend(input) {
  const response = await fetch(PYTHON_BACKEND_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(input),
  });

  if (!response.ok) {
    throw new Error(`Python backend failed with status ${response.status}`);
  }

  return response.json();
}

function calculateWithDemoModel(input) {
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
    month: buildPeriodResult(dailyRevenue, dailyDegradationCost, 30),
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