// PM2 Ecosystem Configuration - PMS Frontend
// For production deployment behind IIS reverse proxy
//
// IMPORTANT: NEXT_PUBLIC_* env vars are baked into the build at compile time.
// They must be set in frontend/.env BEFORE running 'npm run build'.
// PM2 env vars only affect runtime, not the already-built bundle.

module.exports = {
  apps: [{
    name: 'pms-frontend',
    script: 'node_modules/next/dist/bin/next',
    // Bind to localhost only — IIS reverse proxy handles external traffic
    args: 'start -p 3000 -H 127.0.0.1',
    interpreter: 'node',
    windowsHide: true,
    env: {
      NODE_ENV: 'production',
      NEXT_PUBLIC_API_URL: 'https://pms.nigcomsat.gov.ng',
      NEXT_PUBLIC_WS_URL: 'wss://pms.nigcomsat.gov.ng'
    },
    autorestart: true,
    watch: false,
    max_memory_restart: '500M',
    error_file: './logs/frontend-error.log',
    out_file: './logs/frontend-out.log',
    log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
  }]
};