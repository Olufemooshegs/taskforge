FROM node:20-slim
WORKDIR /app
EXPOSE 3000
# node_modules are bind-mounted from the host (installed once via
# `cd dashboard && npm install`). Bind-mounting sidesteps the slow/fragile
# WSL2 -> Docker -> registry.npmjs.org path on first build.
CMD ["npm", "run", "dev"]