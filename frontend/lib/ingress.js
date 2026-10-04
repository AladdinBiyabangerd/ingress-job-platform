/** Shared Ingress ecosystem identity — Job is one product in this family. */
export const INGRESS = {
  name: "Ingress",
  academyName: "Ingress Academy",
  url: "https://ingress.academy",
};

export function ingressUrl(locale = "az") {
  if (locale === "en") return `${INGRESS.url}/en`;
  if (locale === "ru") return `${INGRESS.url}/ru`;
  return INGRESS.url;
}
