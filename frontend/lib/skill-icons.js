/**
 * Skill name → Devicon SVG (jsDelivr CDN).
 * Value is "{folder}/{file}.svg" under icons/.
 * In-code map only — no runtime API; icons load lazily via <img>.
 */

const DEVICON_BASE =
  "https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons";

/** @type {Record<string, string>} */
const ICONS = {
  // —— Languages / runtimes ——
  java: "java/java-original.svg",
  openjdk: "java/java-original.svg",
  jdk: "java/java-original.svg",
  kotlin: "kotlin/kotlin-original.svg",
  scala: "scala/scala-original.svg",
  python: "python/python-original.svg",
  py: "python/python-original.svg",
  python2: "python/python-original.svg",
  python3: "python/python-original.svg",
  javascript: "javascript/javascript-original.svg",
  js: "javascript/javascript-original.svg",
  es6: "javascript/javascript-original.svg",
  ecmascript: "javascript/javascript-original.svg",
  typescript: "typescript/typescript-original.svg",
  ts: "typescript/typescript-original.svg",
  go: "go/go-original-wordmark.svg",
  golang: "go/go-original-wordmark.svg",
  rust: "rust/rust-original.svg",
  php: "php/php-original.svg",
  ruby: "ruby/ruby-original.svg",
  swift: "swift/swift-original.svg",
  swiftui: "swift/swift-original.svg",
  dart: "dart/dart-original.svg",
  "c#": "csharp/csharp-original.svg",
  csharp: "csharp/csharp-original.svg",
  ".net": "dotnetcore/dotnetcore-original.svg",
  ".net core": "dotnetcore/dotnetcore-original.svg",
  "asp.net": "dotnetcore/dotnetcore-original.svg",
  aspnet: "dotnetcore/dotnetcore-original.svg",
  dotnet: "dotnetcore/dotnetcore-original.svg",
  "c++": "cplusplus/cplusplus-original.svg",
  cpp: "cplusplus/cplusplus-original.svg",
  c: "c/c-original.svg",
  "objective-c": "objectivec/objectivec-plain.svg",
  "obj-c": "objectivec/objectivec-plain.svg",
  objc: "objectivec/objectivec-plain.svg",
  elixir: "elixir/elixir-original.svg",
  erlang: "erlang/erlang-original.svg",
  haskell: "haskell/haskell-original.svg",
  clojure: "clojure/clojure-original.svg",
  cljs: "clojure/clojure-original.svg",
  clojurescript: "clojure/clojure-original.svg",
  "f#": "fsharp/fsharp-original.svg",
  fsharp: "fsharp/fsharp-original.svg",
  r: "r/r-original.svg",
  "r programming": "r/r-original.svg",
  rstudio: "rstudio/rstudio-original.svg",
  julia: "julia/julia-original.svg",
  matlab: "matlab/matlab-original.svg",
  lua: "lua/lua-original.svg",
  perl: "perl/perl-original.svg",
  groovy: "groovy/groovy-original.svg",
  solidity: "solidity/solidity-original.svg",
  bash: "bash/bash-original.svg",
  shell: "bash/bash-original.svg",
  "shell scripting": "bash/bash-original.svg",
  powershell: "powershell/powershell-original.svg",
  pwsh: "powershell/powershell-original.svg",

  // —— Backend / frameworks ——
  spring: "spring/spring-original.svg",
  "spring boot": "spring/spring-original.svg",
  springboot: "spring/spring-original.svg",
  "spring cloud": "spring/spring-original.svg",
  "spring security": "spring/spring-original.svg",
  "spring mvc": "spring/spring-original.svg",
  hibernate: "hibernate/hibernate-original.svg",
  jpa: "hibernate/hibernate-original.svg",
  "spring data jpa": "hibernate/hibernate-original.svg",
  maven: "maven/maven-original.svg",
  gradle: "gradle/gradle-original.svg",
  tomcat: "tomcat/tomcat-original.svg",
  junit: "java/java-original.svg",
  testng: "java/java-original.svg",
  mockito: "java/java-original.svg",
  quarkus: "quarkus/quarkus-original.svg",
  micronaut: "java/java-original.svg",
  ktor: "kotlin/kotlin-original.svg",
  django: "django/django-plain.svg",
  flask: "flask/flask-original.svg",
  fastapi: "fastapi/fastapi-original.svg",
  express: "express/express-original.svg",
  "express.js": "express/express-original.svg",
  expressjs: "express/express-original.svg",
  nestjs: "nestjs/nestjs-original.svg",
  "nest.js": "nestjs/nestjs-original.svg",
  "node.js": "nodejs/nodejs-original.svg",
  nodejs: "nodejs/nodejs-original.svg",
  node: "nodejs/nodejs-original.svg",
  graphql: "graphql/graphql-plain.svg",
  grpc: "grpc/grpc-original.svg",
  "rest api": "nginx/nginx-original.svg",
  rest: "nginx/nginx-original.svg",
  openapi: "swagger/swagger-original.svg",
  swagger: "swagger/swagger-original.svg",
  microservices: "docker/docker-original.svg",
  "ruby on rails": "rails/rails-plain-wordmark.svg",
  rails: "rails/rails-plain-wordmark.svg",
  ror: "rails/rails-plain-wordmark.svg",
  laravel: "laravel/laravel-original.svg",
  symfony: "symfony/symfony-original.svg",
  phoenix: "phoenix/phoenix-original.svg",
  "phoenix framework": "phoenix/phoenix-original.svg",
  blazor: "dotnetcore/dotnetcore-original.svg",
  "entity framework": "dotnetcore/dotnetcore-original.svg",
  "ef core": "dotnetcore/dotnetcore-original.svg",
  efcore: "dotnetcore/dotnetcore-original.svg",
  celery: "python/python-original.svg",
  fastify: "nodejs/nodejs-original.svg",
  jwt: "json/json-original.svg",
  "json web token": "json/json-original.svg",

  // —— Data / messaging ——
  sql: "mysql/mysql-original.svg",
  "pl/sql": "oracle/oracle-original.svg",
  plsql: "oracle/oracle-original.svg",
  "t-sql": "microsoftsqlserver/microsoftsqlserver-plain.svg",
  mysql: "mysql/mysql-original.svg",
  mariadb: "mariadb/mariadb-original.svg",
  postgresql: "postgresql/postgresql-original.svg",
  postgres: "postgresql/postgresql-original.svg",
  psql: "postgresql/postgresql-original.svg",
  mongodb: "mongodb/mongodb-original.svg",
  mongo: "mongodb/mongodb-original.svg",
  redis: "redis/redis-original.svg",
  elasticsearch: "elasticsearch/elasticsearch-original.svg",
  "elastic search": "elasticsearch/elasticsearch-original.svg",
  opensearch: "elasticsearch/elasticsearch-original.svg",
  kibana: "kibana/kibana-original.svg",
  logstash: "logstash/logstash-original.svg",
  cassandra: "cassandra/cassandra-original.svg",
  sqlite: "sqlite/sqlite-original.svg",
  "sql server": "microsoftsqlserver/microsoftsqlserver-plain.svg",
  "microsoft sql server": "microsoftsqlserver/microsoftsqlserver-plain.svg",
  mssql: "microsoftsqlserver/microsoftsqlserver-plain.svg",
  oracle: "oracle/oracle-original.svg",
  nosql: "mongodb/mongodb-original.svg",
  dynamodb: "dynamodb/dynamodb-original.svg",
  dynamo: "dynamodb/dynamodb-original.svg",
  neo4j: "neo4j/neo4j-original.svg",
  influxdb: "influxdb/influxdb-original.svg",
  couchbase: "couchbase/couchbase-original.svg",
  kafka: "apachekafka/apachekafka-original.svg",
  "apache kafka": "apachekafka/apachekafka-original.svg",
  rabbitmq: "rabbitmq/rabbitmq-original.svg",
  spark: "apachespark/apachespark-original.svg",
  "apache spark": "apachespark/apachespark-original.svg",
  pyspark: "apachespark/apachespark-original.svg",
  hadoop: "hadoop/hadoop-original.svg",
  hive: "hadoop/hadoop-original.svg",
  "apache hive": "hadoop/hadoop-original.svg",
  hiveql: "hadoop/hadoop-original.svg",
  airflow: "apacheairflow/apacheairflow-original.svg",
  "apache airflow": "apacheairflow/apacheairflow-original.svg",
  flink: "apache/apache-original.svg",
  "apache flink": "apache/apache-original.svg",
  clickhouse: "postgresql/postgresql-original.svg",
  trino: "postgresql/postgresql-original.svg",
  bigquery: "googlecloud/googlecloud-original.svg",
  "big query": "googlecloud/googlecloud-original.svg",
  snowflake: "azuresqldatabase/azuresqldatabase-original.svg",
  databricks: "apache/apache-original.svg",
  redshift: "amazonwebservices/amazonwebservices-original-wordmark.svg",
  dbt: "sqlalchemy/sqlalchemy-original.svg",
  prisma: "prisma/prisma-original.svg",
  sequelize: "sequelize/sequelize-original.svg",
  typeorm: "typescript/typescript-original.svg",
  memcached: "memcached/memcached-original.svg",

  // —— Cloud / DevOps ——
  aws: "amazonwebservices/amazonwebservices-original-wordmark.svg",
  "amazon web services": "amazonwebservices/amazonwebservices-original-wordmark.svg",
  amazonwebservices: "amazonwebservices/amazonwebservices-original-wordmark.svg",
  "aws lambda": "amazonwebservices/amazonwebservices-original-wordmark.svg",
  lambda: "amazonwebservices/amazonwebservices-original-wordmark.svg",
  s3: "amazonwebservices/amazonwebservices-original-wordmark.svg",
  ec2: "amazonwebservices/amazonwebservices-original-wordmark.svg",
  ecs: "amazonwebservices/amazonwebservices-original-wordmark.svg",
  eks: "kubernetes/kubernetes-plain.svg",
  cloudformation: "amazonwebservices/amazonwebservices-original-wordmark.svg",
  cfn: "amazonwebservices/amazonwebservices-original-wordmark.svg",
  azure: "azure/azure-original.svg",
  aks: "kubernetes/kubernetes-plain.svg",
  gcp: "googlecloud/googlecloud-original.svg",
  "google cloud": "googlecloud/googlecloud-original.svg",
  "google cloud platform": "googlecloud/googlecloud-original.svg",
  gke: "kubernetes/kubernetes-plain.svg",
  docker: "docker/docker-original.svg",
  "docker compose": "docker/docker-original.svg",
  "docker-compose": "docker/docker-original.svg",
  kubernetes: "kubernetes/kubernetes-plain.svg",
  k8s: "kubernetes/kubernetes-plain.svg",
  helm: "helm/helm-original.svg",
  terraform: "terraform/terraform-original.svg",
  ansible: "ansible/ansible-original.svg",
  jenkins: "jenkins/jenkins-original.svg",
  "ci/cd": "githubactions/githubactions-original.svg",
  cicd: "githubactions/githubactions-original.svg",
  "continuous integration": "githubactions/githubactions-original.svg",
  "continuous delivery": "githubactions/githubactions-original.svg",
  "github actions": "githubactions/githubactions-original.svg",
  gha: "githubactions/githubactions-original.svg",
  github: "github/github-original.svg",
  gitlab: "gitlab/gitlab-original.svg",
  "gitlab ci": "gitlab/gitlab-original.svg",
  "gitlab-ci": "gitlab/gitlab-original.svg",
  circleci: "circleci/circleci-plain.svg",
  "circle ci": "circleci/circleci-plain.svg",
  "argo cd": "argocd/argocd-original.svg",
  "argo-cd": "argocd/argocd-original.svg",
  argocd: "argocd/argocd-original.svg",
  git: "git/git-original.svg",
  linux: "linux/linux-original.svg",
  nginx: "nginx/nginx-original.svg",
  haproxy: "nginx/nginx-original.svg",
  traefik: "traefikproxy/traefikproxy-original.svg",
  prometheus: "prometheus/prometheus-original.svg",
  grafana: "grafana/grafana-original.svg",
  datadog: "grafana/grafana-original.svg",
  "new relic": "grafana/grafana-original.svg",
  newrelic: "grafana/grafana-original.svg",
  sentry: "sentry/sentry-original.svg",
  splunk: "elasticsearch/elasticsearch-original.svg",
  devops: "docker/docker-original.svg",
  pulumi: "pulumi/pulumi-original.svg",
  consul: "amazonwebservices/amazonwebservices-original-wordmark.svg",
  "hashicorp vault": "amazonwebservices/amazonwebservices-original-wordmark.svg",
  vault: "amazonwebservices/amazonwebservices-original-wordmark.svg",
  istio: "kubernetes/kubernetes-plain.svg",
  openshift: "redhat/redhat-original.svg",
  digitalocean: "digitalocean/digitalocean-original.svg",
  "digital ocean": "digitalocean/digitalocean-original.svg",
  heroku: "heroku/heroku-original.svg",
  netlify: "netlify/netlify-original.svg",
  vercel: "vercel/vercel-original.svg",
  cloudflare: "cloudflare/cloudflare-original.svg",
  opentelemetry: "opentelemetry/opentelemetry-original.svg",
  otel: "opentelemetry/opentelemetry-original.svg",

  // —— Frontend / mobile ——
  react: "react/react-original.svg",
  "react.js": "react/react-original.svg",
  reactjs: "react/react-original.svg",
  "react native": "react/react-original.svg",
  rn: "react/react-original.svg",
  vue: "vuejs/vuejs-original.svg",
  "vue.js": "vuejs/vuejs-original.svg",
  vuejs: "vuejs/vuejs-original.svg",
  angular: "angularjs/angularjs-original.svg",
  angularjs: "angularjs/angularjs-original.svg",
  "next.js": "nextjs/nextjs-original.svg",
  nextjs: "nextjs/nextjs-original.svg",
  next: "nextjs/nextjs-original.svg",
  nuxt: "nuxtjs/nuxtjs-original.svg",
  "nuxt.js": "nuxtjs/nuxtjs-original.svg",
  nuxtjs: "nuxtjs/nuxtjs-original.svg",
  svelte: "svelte/svelte-original.svg",
  sveltekit: "svelte/svelte-original.svg",
  gatsby: "gatsby/gatsby-original.svg",
  astro: "astro/astro-original.svg",
  ember: "ember/ember-original-wordmark.svg",
  "ember.js": "ember/ember-original-wordmark.svg",
  emberjs: "ember/ember-original-wordmark.svg",
  remix: "react/react-original.svg",
  "remix.js": "react/react-original.svg",
  remixjs: "react/react-original.svg",
  redux: "redux/redux-original.svg",
  "redux toolkit": "redux/redux-original.svg",
  rtk: "redux/redux-original.svg",
  rxjs: "rxjs/rxjs-original.svg",
  jquery: "jquery/jquery-original.svg",
  bootstrap: "bootstrap/bootstrap-original.svg",
  "material ui": "materialui/materialui-original.svg",
  "material-ui": "materialui/materialui-original.svg",
  mui: "materialui/materialui-original.svg",
  tailwind: "tailwindcss/tailwindcss-original.svg",
  "tailwind css": "tailwindcss/tailwindcss-original.svg",
  tailwindcss: "tailwindcss/tailwindcss-original.svg",
  html: "html5/html5-original.svg",
  html5: "html5/html5-original.svg",
  css: "css3/css3-original.svg",
  css3: "css3/css3-original.svg",
  sass: "sass/sass-original.svg",
  scss: "sass/sass-original.svg",
  webpack: "webpack/webpack-original.svg",
  vite: "vitejs/vitejs-original.svg",
  storybook: "storybook/storybook-original.svg",
  "three.js": "threejs/threejs-original.svg",
  threejs: "threejs/threejs-original.svg",
  "d3.js": "d3js/d3js-original.svg",
  d3: "d3js/d3js-original.svg",
  d3js: "d3js/d3js-original.svg",
  flutter: "flutter/flutter-original.svg",
  android: "android/android-original.svg",
  ios: "apple/apple-original.svg",
  "jetpack compose": "android/android-original.svg",
  xamarin: "xamarin/xamarin-original.svg",
  ionic: "ionic/ionic-original.svg",
  capacitor: "ionic/ionic-original.svg",
  figma: "figma/figma-original.svg",

  // —— ML / AI ——
  pytorch: "pytorch/pytorch-original.svg",
  tensorflow: "tensorflow/tensorflow-original.svg",
  keras: "keras/keras-original.svg",
  "scikit-learn": "scikitlearn/scikitlearn-original.svg",
  sklearn: "scikitlearn/scikitlearn-original.svg",
  numpy: "numpy/numpy-original.svg",
  pandas: "pandas/pandas-original.svg",
  jupyter: "jupyter/jupyter-original.svg",
  anaconda: "anaconda/anaconda-original.svg",
  opencv: "opencv/opencv-original.svg",
  "computer vision": "opencv/opencv-original.svg",
  llm: "pytorch/pytorch-original.svg",
  llms: "pytorch/pytorch-original.svg",
  "large language model": "pytorch/pytorch-original.svg",
  openai: "python/python-original.svg",
  langchain: "python/python-original.svg",
  rag: "python/python-original.svg",
  "retrieval augmented generation": "python/python-original.svg",
  nlp: "python/python-original.svg",
  "natural language processing": "python/python-original.svg",
  "hugging face": "python/python-original.svg",
  huggingface: "python/python-original.svg",
  mlflow: "python/python-original.svg",
  cuda: "python/python-original.svg",

  // —— Testing ——
  jest: "jest/jest-plain.svg",
  cypress: "cypressio/cypressio-original.svg",
  playwright: "playwright/playwright-original.svg",
  selenium: "selenium/selenium-original.svg",
  mocha: "mocha/mocha-original.svg",
  cucumber: "cucumber/cucumber-plain.svg",
  gherkin: "cucumber/cucumber-plain.svg",
  pytest: "pytest/pytest-original.svg",
  vitest: "vitejs/vitejs-original.svg",
  appium: "android/android-original.svg",
  jmeter: "java/java-original.svg",
  k6: "grafana/grafana-original.svg",

  // —— Tools / platforms ——
  jira: "jira/jira-original.svg",
  confluence: "confluence/confluence-original.svg",
  slack: "slack/slack-original.svg",
  postman: "postman/postman-original.svg",
  wordpress: "wordpress/wordpress-plain.svg",
  wp: "wordpress/wordpress-plain.svg",
  shopify: "nodejs/nodejs-original.svg",
  salesforce: "salesforce/salesforce-original.svg",
  sfdc: "salesforce/salesforce-original.svg",
  odoo: "python/python-original.svg",
  "power bi": "azuresqldatabase/azuresqldatabase-original.svg",
  powerbi: "azuresqldatabase/azuresqldatabase-original.svg",
  tableau: "azuresqldatabase/azuresqldatabase-original.svg",
  looker: "googlecloud/googlecloud-original.svg",
  unity: "unity/unity-original.svg",
  unity3d: "unity/unity-original.svg",
  "unreal engine": "unrealengine/unrealengine-original.svg",
  unreal: "unrealengine/unrealengine-original.svg",
  ue4: "unrealengine/unrealengine-original.svg",
  ue5: "unrealengine/unrealengine-original.svg",
  ethereum: "solidity/solidity-original.svg",
  evm: "solidity/solidity-original.svg",
  owasp: "bash/bash-original.svg",
};

function normalize(name) {
  return String(name || "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ");
}

let _aliasesSorted = null;

function aliasesLongestFirst() {
  if (!_aliasesSorted) {
    _aliasesSorted = Object.keys(ICONS)
      .filter((alias) => alias.length >= 2)
      .sort((a, b) => b.length - a.length);
  }
  return _aliasesSorted;
}

export function skillIconSrc(name) {
  const key = normalize(name);
  if (!key) return null;
  if (ICONS[key]) return `${DEVICON_BASE}/${ICONS[key]}`;

  const first = key.split(/[\s/,|+]+/)[0];
  if (first && first !== key && ICONS[first]) {
    return `${DEVICON_BASE}/${ICONS[first]}`;
  }

  for (const alias of aliasesLongestFirst()) {
    if (
      key === alias ||
      key.startsWith(`${alias} `) ||
      key.startsWith(`${alias}-`) ||
      key.endsWith(` ${alias}`) ||
      key.includes(` ${alias} `) ||
      key.includes(` ${alias}/`) ||
      key.includes(`/${alias}`)
    ) {
      return `${DEVICON_BASE}/${ICONS[alias]}`;
    }
  }
  return null;
}

/** @deprecated use skillIconSrc */
export function skillIconMeta(name) {
  const src = skillIconSrc(name);
  if (!src) return null;
  return { src };
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
