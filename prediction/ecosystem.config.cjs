const path = require('path');
const repoRoot = path.resolve(__dirname, '..');

module.exports = {
  apps: [{
    name: 'heavyequip-price-prediction',
    script: 'prediction/service.py',
    cwd: repoRoot,
    interpreter: process.env.PREDICTION_PYTHON_BIN || path.join(__dirname, '.venv', 'bin', 'python'),
    instances: 1,
    exec_mode: 'fork',
    watch: false,
    autorestart: true,
    restart_delay: 5000,
    kill_timeout: 15000,
    max_memory_restart: '1G',
    time: true,
    filter_env: ['PREDICTION_SOURCE_', 'PREDICTION_WAREHOUSE_'],
    env: {
      PYTHONUNBUFFERED: '1',
      PYTHONPATH: repoRoot,
      PREDICTION_API_HOST: '127.0.0.1',
      PREDICTION_API_PORT: '5060',
      PREDICTION_ARTIFACT_ROOT: path.join(__dirname, 'artifacts'),
      OMP_NUM_THREADS: '2',
      OPENBLAS_NUM_THREADS: '2',
    },
  }],
};
