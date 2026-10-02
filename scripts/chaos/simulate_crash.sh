#!/bin/bash
echo "💥 Injecting Chaos: Pausing the local Inference Service container to simulate a cloud crash..."
docker pause multi-regionself-healingaiopsplatformforhigh-availabilitymicroservices-inference-service-1
echo "💀 Service frozen. Watch the AIOps engine logs to see self-healing in action!"
echo "Run: docker compose logs -f aiops-engine"
