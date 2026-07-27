// PM2 Ecosystem Configuration - PMS Backend
// For production deployment behind IIS reverse proxy
//
// Uses uvicorn directly (no python.exe console window popup on Windows).

module.exports = {
  apps: [
    {
      name: "pms-backend",
      script: "./venv/Scripts/uvicorn.exe",
      args: "main:app --host 0.0.0.0 --port 8000",
      autorestart: true,
      watch: false,
      max_memory_restart: "500M",
      env: {
        PYTHONUNBUFFERED: "1",
        ENVIRONMENT: "production"
      },
      error_file: "./logs/backend-error.log",
      out_file: "./logs/backend-out.log",
      log_date_format: "YYYY-MM-DD HH:mm:ss Z"
    }
  ]
};