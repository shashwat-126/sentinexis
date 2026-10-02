#!/bin/bash
echo "🐢 Injecting Chaos: Flooding the Inference Service to spike ML inference depth and latency..."

for i in {1..75}; do
  curl -s -X POST http://localhost:8080/infer/infer \
    -H "Content-Type: application/json" \
    -d "{\"data_payload\": \"Chaos Payload $i\", \"complexity\": 10}" > /dev/null &
done

echo "🌊 Flood complete! Sent 75 maximum-complexity requests asynchronously."
echo "Watch the AIOps engine detect the resulting queue/latency ML anomaly!"
echo "Run: docker compose logs -f aiops-engine"
