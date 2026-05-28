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

export function calculateFleetResult(input) {
  const config = drivingPatternConfig[input.drivingPattern];

  const vehicleTypes = Array.isArray(input.vehicleTypes)
    ? input.vehicleTypes
    : [];

  let totalVehicles = 0;
  let aggregatedCapacityKw = 0;
  let totalBatteryValue = 0;

  vehicleTypes.forEach((vehicleType) => {
    const vehicleCount = cleanNumber(vehicleType.vehicleCount);
    const batteryCost = cleanNumber(vehicleType.batteryCost);
    const batteryCapacity = cleanNumber(vehicleType.batteryCapacity);
    const chargerPower = cleanNumber(vehicleType.chargerPower);

    const usablePowerPerVehicle = Math.min(chargerPower, batteryCapacity * 0.35);

    totalVehicles += vehicleCount;
    aggregatedCapacityKw += usablePowerPerVehicle * vehicleCount;
    totalBatteryValue += batteryCost * vehicleCount;
  });

  const aggregatedCapacityMW = aggregatedCapacityKw / 1000;

  const dailyRevenue =
    aggregatedCapacityKw *
    config.availableHoursPerDay *
    config.utilization *
    config.revenuePerKwPerHour;

  const dailyDegradationCost =
    totalBatteryValue * 0.00025 * config.utilization;

  const week = buildPeriodResult(dailyRevenue, dailyDegradationCost, 7);
  const month = buildPeriodResult(dailyRevenue, dailyDegradationCost, 30);
  const quarter = buildPeriodResult(dailyRevenue, dailyDegradationCost, 90);

  return {
    week,
    month,
    quarter,

    meta: {
      aggregatedCapacityMW,
      totalVehicles,
      utilization: Math.round(config.utilization * 100),
      breakEven: month.netProfit > 0 ? "Profitable" : "Not profitable",
      risk: config.risk,
    },
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