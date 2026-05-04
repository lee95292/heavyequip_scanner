module.exports = {
  apps: [
    {
      name: "heavyequip-dashboard",
      script: "server/index.js",
      cwd: __dirname,
      instances: 1,
      exec_mode: "fork",
      watch: false,
      autorestart: true,
      max_memory_restart: "300M",
      env: {
        NODE_ENV: "production",
        PORT: "5050"
      }
    }
  ]
};
