import { bucket, defineRailway, group, postgres, project, service } from "railway/iac";

// Three services from this repo. There is no GitHub remote yet, so source is
// not pinned to a github() repo. root selects the directory Railway builds.
// A push builds whichever service is connected to that directory.
// Do not add railway.toml beside this file: new projects use this IaC file,
// and a service cannot be managed by both.
export default defineRailway(() => {
  const media = bucket("cvs", { region: "ams" });
  const db = postgres("postgres");

  const storageEnv = {
    BUCKET_NAME: media.env.BUCKET,
    BUCKET_ACCESS_KEY: media.env.ACCESS_KEY_ID,
    BUCKET_SECRET_KEY: media.env.SECRET_ACCESS_KEY,
    BUCKET_REGION: media.env.REGION,
    BUCKET_ENDPOINT: media.env.ENDPOINT,
  };

  const api = service("api", {
    root: "api",
    start: "sh -c 'exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8010}'",
    healthcheck: "/health",
    healthcheckTimeout: 30,
    env: {
      ...storageEnv,
      DEBUG: "False",
      DATABASE_URL: db.env.DATABASE_URL,
    },
  });

  const web = service("web", {
    root: "frontend",
    build: "npm ci && npm run build",
    start: "sh -c 'exec npx next start --hostname 0.0.0.0 --port ${PORT:-3010}'",
    healthcheck: "/",
    healthcheckTimeout: 60,
    env: {
      NODE_ENV: "production",
      API_PRIVATE_HOST: api.env.RAILWAY_PRIVATE_DOMAIN,
      API_PORT: api.env.PORT,
    },
  });

  const worker = service("worker", {
    root: "worker",
    start: "python -m worker",
    deploy: {
      cronSchedule: "0 * * * *",
      restartPolicyType: "NEVER",
    },
    env: {
      ...storageEnv,
      DATABASE_URL: db.env.DATABASE_URL,
    },
  });

  return project("ingress-job", {
    resources: group("ingress-job", [api, web, worker, media, db]),
  });
});
