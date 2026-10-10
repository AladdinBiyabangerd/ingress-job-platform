/** Design-preview fixtures for pixel QA — not production data. */

export const DETAIL_STATES = [
  "company_signed_in",
  "company_guest",
  "external_signed_in",
  "external_guest",
];

export function parseDetailState(value) {
  const key = String(value || "").trim();
  return DETAIL_STATES.includes(key) ? key : "company_signed_in";
}

export function stateFlags(state) {
  const key = parseDetailState(state);
  return {
    state: key,
    listingType: key.startsWith("external") ? "external" : "company_posted",
    authState: key.endsWith("guest") ? "guest" : "signed_in",
  };
}

const NIMBUS_SECTIONS = [
  {
    id: "about",
    title: "About the role",
    type: "prose",
    paragraphs: [
      "We are looking for a Senior Frontend Developer to join our growing product team. You will be responsible for building and maintaining modern, high-performance web applications using React and TypeScript. You’ll work closely with designers and backend engineers to deliver great user experiences and scalable solutions.",
    ],
  },
  {
    id: "responsibilities",
    title: "Key responsibilities",
    type: "list",
    items: [
      "Develop new features and improve existing frontend applications.",
      "Collaborate with product and design teams to turn ideas into great user experiences.",
      "Write clean, maintainable, and well-tested code.",
      "Participate in code reviews and contribute to technical decisions.",
    ],
  },
  {
    id: "requirements",
    title: "Requirements",
    type: "list",
    items: [
      "3+ years of professional experience in frontend development.",
      "Strong proficiency in React and TypeScript.",
      "Experience with modern state management, such as Redux or Zustand.",
      "Good understanding of responsive and accessible web design.",
      "English at B2+ level, spoken and written.",
    ],
  },
  {
    id: "nice",
    title: "Nice to have",
    type: "list",
    items: [
      "Experience with Next.js or similar frameworks.",
      "Knowledge of backend technologies such as Node.js or Express.",
      "Unit and integration testing experience.",
      "Previous work in a fast-paced product environment.",
    ],
  },
];

const NIMBUS_BENEFITS = [
  { id: "hours", label: "Flexible work hours", icon: "clock" },
  { id: "health", label: "Health insurance", icon: "heart" },
  { id: "learn", label: "Learning and development", icon: "book" },
  { id: "remote", label: "Modern remote-friendly working environment", icon: "globe" },
];

const TECHGLOBAL_SECTIONS = [
  {
    id: "about",
    title: "About the role",
    type: "prose",
    paragraphs: [
      "We are looking for a Senior Frontend Developer to join TechGlobal’s remote product team. You will build and maintain modern web applications used by a global community, collaborating with designers and backend engineers across time zones.",
    ],
  },
  {
    id: "responsibilities",
    title: "Key responsibilities",
    type: "list",
    items: [
      "Ship frontend features for customer-facing products.",
      "Partner with design and product to refine UX.",
      "Write tested, maintainable React and TypeScript code.",
      "Contribute to technical decisions and code reviews.",
    ],
  },
  {
    id: "requirements",
    title: "Requirements",
    type: "list",
    items: [
      "3+ years of professional frontend experience.",
      "Strong React and TypeScript skills.",
      "Comfortable working fully remote with async collaboration.",
      "English at B2+ level.",
    ],
  },
  {
    id: "nice",
    title: "Nice to have",
    type: "list",
    items: [
      "Next.js experience.",
      "Testing with Jest or similar.",
      "Exposure to design systems.",
    ],
  },
];

export function fixtureViewModel(state) {
  const { listingType, authState } = stateFlags(state);
  const external = listingType === "external";
  const company = external ? "TechGlobal" : "NimbusTech";
  const slug = external ? "techglobal" : "nimbustech";

  return {
    preview: true,
    jobId: external ? 9002 : 9001,
    listingType,
    authState,
    title: "Senior Frontend Developer",
    intro: external
      ? "Join TechGlobal’s remote team and work on exciting projects with a global community."
      : "Build products that make a difference. Join our frontend team and work on modern web applications used by millions.",
    company: {
      name: company,
      slug,
      initial: company.charAt(0),
      about: external
        ? "TechGlobal connects engineers with remote product work across Europe and beyond. We help teams ship modern web products with clear ownership and async collaboration."
        : "NimbusTech builds cloud-native products for teams that need reliable, modern web platforms. Our frontend group ships customer-facing apps used by millions of people every month.",
      size: external ? "200–500 employees" : "500–1,000 employees",
      industry: "IT Services & Consulting",
      location: "Baku, Azerbaijan",
      cover: external ? "laptop" : "office",
      pageHref: `#company-${slug}`,
    },
    meta: {
      location: "Baku, Azerbaijan",
      remote: "Remote OK",
      relocation: "Relocation available",
      jobType: "Full-time",
      experience: "2+ years experience",
      languages: "AZ / EN / RU",
      salary: "$3,000 – $4,500 / month",
      posted: "Posted 2 days ago",
      postedDateTime: "2026-10-08T12:00:00+04:00",
    },
    skills: ["React", "TypeScript", "Next.js", "Tailwind CSS", "Git", "Jest", "REST APIs"],
    sections: external ? TECHGLOBAL_SECTIONS : NIMBUS_SECTIONS,
    benefits: NIMBUS_BENEFITS,
    hasOriginal: true,
    form: null,
    returnTo: "/design/job-detail",
    companyPageLabel: true,
  };
}
