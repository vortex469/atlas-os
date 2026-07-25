# Mission Control

Mission Control is the Atlas OS operational interface. It is a React,
TypeScript, and Vite application backed by Atlas Core API v1.

## Current capabilities

- Unified infrastructure and ACE summary
- Live Atlas and inventory service health
- Provider catalog and provider details
- Service details drawer
- Provider-advertised actions
- Confirmation for guarded operations
- Schema-driven action parameters
- Health refresh after successful operations
- Filterable provider action history
- Request ID and execution timing visibility
- Forge deployment analysis workspace

## Development

Install dependencies and start the development server:

```bash
npm install
npm run dev
```

The development server proxies `/api/v1` to Atlas Core at
`http://127.0.0.1:8643`.

## Validation

Run the component tests, lint checks, and production build:

```bash
npm test
npm run lint
npm run build
```
