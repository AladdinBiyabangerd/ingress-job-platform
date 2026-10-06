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

  // Fixed listen port so web can reference it. Railway's runtime PORT injection
  // is not readable via ${{api.PORT}} unless this service variable exists.
  const apiListenPort = "8080";

  const api = service("api", {
    // rootDirectory = api (matches live Railway). Dockerfile installs worker via git.
    root: "api",
    // :: for Railway private IPv6; see docs/railway.md
    // Do not put $PORT on the uvicorn CLI — Railway start is not a shell.
    start: "python start.py",
    env: {
      ...storageEnv,
      DEBUG: "False",
      PORT: apiListenPort,
      DATABASE_URL: db.env.DATABASE_URL,
      CV_OCR_ENABLED: "1",
      CV_OCR_LANG: "eng",
    },
  });

  const web = service("web", {
    root: "frontend",
    build: "npm ci && npm run build",
    start: "sh -c 'exec npx next start --hostname 0.0.0.0 --port ${PORT:-3010}'",
    env: {
      NODE_ENV: "production",
      NODE_OPTIONS: "--dns-result-order=ipv6first",
      // Next server/BFF only (browser never hits private DNS).
      // api.js → http://$API_PRIVATE_HOST:$API_PORT
      API_PRIVATE_HOST: api.env.RAILWAY_PRIVATE_DOMAIN,
      API_PORT: apiListenPort,
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
