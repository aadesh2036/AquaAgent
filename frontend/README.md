# frontend/ — React + TS + Vite + native SVG (module 09)

Renders API values only. **No hydraulic arithmetic** (BACKBONE P1, G9). Contracts are imported from `../shared` via the `@contracts` and `@units` aliases.

```bash
cp .env.example .env        # VITE_MOCK_API=true for Day-1 mock mode
npm install && npm run dev  # http://localhost:5173
npm run check:no-hydraulics # G9 grep proof
```
Deployed by Amplify (`../amplify.yml`, `infra/scripts/15_amplify_app.sh`).
