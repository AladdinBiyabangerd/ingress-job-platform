/** Map canonical / common skill names → Simple Icons slug + brand hex (no #). */

const ICONS = {
  kubernetes: "326ce5",
  k8s: "326ce5",
  docker: "2496ed",
  java: "437291",
  spring: "6db33f",
  "spring boot": "6db33f",
  kafka: "231f20",
  "apache kafka": "231f20",
  redis: "dc382d",
  postgresql: "4169e1",
  postgres: "4169e1",
  mysql: "4479a1",
  mongodb: "47a248",
  grpc: "244c5a",
  git: "f05032",
  github: "181717",
  gitlab: "fc6d26",
  python: "3776ab",
  javascript: "f7df1e",
  typescript: "3178c6",
  react: "61dafb",
  "node.js": "5fa04e",
  node: "5fa04e",
  nodejs: "5fa04e",
  go: "00add8",
  golang: "00add8",
  rust: "000000",
  aws: "232f3e",
  "amazon web services": "232f3e",
  azure: "0078d4",
  gcp: "4285f4",
  "google cloud": "4285f4",
  terraform: "7b42bc",
  ansible: "ee0000",
  linux: "fcc624",
  nginx: "009639",
  elasticsearch: "005571",
  rabbitmq: "ff6600",
  graphql: "e10098",
  "c#": "512bd4",
  csharp: "512bd4",
  ".net": "512bd4",
  php: "777bb4",
  ruby: "cc342d",
  kotlin: "7f52ff",
  swift: "f05138",
  flutter: "02569b",
  dart: "0175c2",
  vue: "4fc08d",
  angular: "dd0031",
  nextjs: "000000",
  "next.js": "000000",
  django: "092e20",
  flask: "000000",
  fastapi: "009688",
  jenkins: "d24939",
  prometheus: "e6522c",
  grafana: "f46800",
  helm: "0f1689",
  "ci/cd": "2088ff",
  sql: "4479a1",
  nosql: "4db33d",
  html: "e34f26",
  css: "1572b6",
  sass: "cc6699",
  webpack: "8dd6f9",
  jira: "0052cc",
  confluence: "172b4d",
  slack: "4a154b",
  figma: "f24e1e",
  spark: "e25a1c",
  "apache spark": "e25a1c",
  airflow: "017cee",
  "apache airflow": "017cee",
  hadoop: "66ccff",
  cassandra: "1287b1",
  kibana: "005571",
  logstash: "005571",
  memcached: "002630",
  celery: "37814a",
  "rest api": "0096d6",
  rest: "0096d6",
  microservices: "001fff",
  devops: "001fff",
};

const SLUG_ALIASES = {
  "spring boot": "spring",
  "apache kafka": "apachekafka",
  "node.js": "nodedotjs",
  nodejs: "nodedotjs",
  node: "nodedotjs",
  golang: "go",
  "amazon web services": "amazonaws",
  aws: "amazonaws",
  "google cloud": "googlecloud",
  gcp: "googlecloud",
  "c#": "csharp",
  ".net": "dotnet",
  "next.js": "nextdotjs",
  nextjs: "nextdotjs",
  "apache spark": "apachespark",
  "apache airflow": "apacheairflow",
  "ci/cd": "githubactions",
  "rest api": "fastapi",
  rest: "fastapi",
  k8s: "kubernetes",
  postgres: "postgresql",
  kafka: "apachekafka",
};

function normalize(name) {
  return String(name || "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ");
}

export function skillIconMeta(name) {
  const key = normalize(name);
  if (!key) return null;
  if (ICONS[key] || SLUG_ALIASES[key]) {
    const slug = SLUG_ALIASES[key] || key.replace(/[^a-z0-9]/g, "");
    return {
      slug,
      color: (ICONS[key] || "001fff").replace(/^#/, ""),
    };
  }
  const first = key.split(/[\s/,|+]+/)[0];
  if (first && first !== key && (ICONS[first] || SLUG_ALIASES[first])) {
    return skillIconMeta(first);
  }
  return null;
}

export function skillInitials(name) {
  const parts = String(name || "")
    .trim()
    .split(/[\s/_-]+/)
    .filter(Boolean);
  if (!parts.length) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}
