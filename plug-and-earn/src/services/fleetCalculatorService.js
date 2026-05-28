import { callPythonModel } from "./pythonApiAdapter.js";

export function calculateFleetEconomics(input) {
  // TODO: Replace mock calculation with Python backend call.
  // return callPythonModel("/fleet-calculate", input);

  const grossRevenue = input.numberOfVehicles * input.chargerPowerKw * 4.2;
  const degradationCost = grossRevenue * 0.22;
  const netProfit = grossRevenue - degradationCost;

  return {
    monthlyRevenue: grossRevenue,
    degradationCost,
    netProfit,
    availableCapacityMw: (input.numberOfVehicles * input.chargerPowerKw) / 1000,
    risk: netProfit > 0 ? "Low" : "High",
  };
}