import { defineRailway, github, project, service } from "railway/iac";

export default defineRailway(() => {
  const supplyChainSimulator = service("supply-chain-simulator", {
    source: github("marcoduetsch-oc/supply-chain-simulator", { branch: "main", checkSuites: false }),
    build: { buildEnvironment: "V3", builder: "RAILPACK" },
    replicas: { "europe-west4-drams3a": 1 },
    domains: ["biergame.duetsch.net"],
  });

  return project("dynamic-fascination", {
    variables: { managed: false },
    resources: [supplyChainSimulator],
  });
});
