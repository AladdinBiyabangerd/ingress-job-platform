// Real nümunələrə əsaslanan sintetik LinkedIn düzənləri (EN və TR, Easy Apply və xarici Apply).
const NOISE_TOP = `<div><p>Your profile and resume are missing some required qualifications</p><button>Show match details</button><p>BETA • Is this information helpful?</p></div>`;
const PREMIUM = `<div><p>Job search faster with Premium</p><p>Get hired faster</p><button>Retry Premium</button></div>`;

function page({ title, company, companyPath, id, line, chips, action, saved = "Save", body, noise = NOISE_TOP, aboutJob = "About the job", aboutCompany = "About the company" }) {
  return `<!doctype html><html><head><title>${title} | ${company} | LinkedIn</title></head><body>
  <ul><li><a href="/jobs/view/999999999/">Başka ilan</a><span>Diğer</span></li></ul>
  <main class="x1"><div class="y2">
    <div><a href="${companyPath}"><img alt=""></a><a href="${companyPath}">${company}</a></div>
    <div><a href="/jobs/view/${id}/?trackingId=abc"><span>${title}</span></a></div>
    <p>${line}</p>
    <div>${chips.map((c) => `<a href="/jobs/search-results/?currentJobId=${id}&f=1"><span>${c}</span></a>`).join("")}</div>
    <div>${action}<button>${saved}</button></div>
    ${noise}
    <section><h2>${aboutJob}</h2><div>${body}</div></section>
    ${PREMIUM}
    <section><h2>${aboutCompany}</h2><p>Company blurb must not appear.</p></section>
  </div></main></body></html>`;
}

const CASES = [
  {
    name: "EN easy apply (Sparkrock)",
    url: "https://www.linkedin.com/jobs/search-results/?currentJobId=4450707960&origin=JOBS_HOME",
    html: page({
      title: "AI-Enabled .NET Chief Architect (OTE $100,000/year USD), @Sparkrock", company: "Sparkrock", companyPath: "/company/sparkrock/life/",
      id: "4450707960", line: "Greater Istanbul · 2 months ago · Over 100 applicants", chips: ["Remote", "Full-time"],
      action: "<button>Easy Apply</button>",
      body: "<p>Lead architecture for our .NET platform.</p><p><strong>Requirements</strong></p><p>10+ years with C# and Azure.</p>",
    }),
    expect: {
      linkedin_id: "4450707960", title: "AI-Enabled .NET Chief Architect (OTE $100,000/year USD), @Sparkrock", company: "Sparkrock",
      location: "Greater Istanbul", posted: "2 months ago", remote: true, employment_type: "Full-time",
      apply_url: "https://www.linkedin.com/jobs/view/4450707960/", has: [/Lead architecture/, /10\+ years with C#/, /Requirements/],
    },
  },
  {
    name: "EN easy apply (Digital Zone, inner headings kept)",
    url: "https://www.linkedin.com/jobs/search-results/?currentJobId=4455278542",
    html: page({
      title: "Senior Site Reliability Engineer (Performance and Scalability)", company: "Digital Zone", companyPath: "/company/digitalzoneapp/life/",
      id: "4455278542", line: "Türkiye · 1 month ago · Over 100 applicants", chips: ["Remote", "Full-time"],
      action: "<button>Easy Apply</button>",
      body: "<p><strong>What you'll do</strong></p><p>Own performance.</p><p><strong>Requirements</strong></p><p>Kubernetes.</p><p><strong>What you'll bring</strong></p><p>Curiosity.</p><p><strong>Benefits</strong></p><p>Remote work.</p><p>See how you compare to other applicants</p>",
    }),
    expect: {
      linkedin_id: "4455278542", title: "Senior Site Reliability Engineer (Performance and Scalability)", company: "Digital Zone",
      location: "Türkiye", posted: "1 month ago", remote: true, employment_type: "Full-time",
      apply_url: "https://www.linkedin.com/jobs/view/4455278542/", has: [/What you'll do/, /Requirements/, /What you'll bring/, /Benefits/, /Remote work\./],
    },
  },
  {
    name: "EN external apply (The Flex)",
    url: "https://www.linkedin.com/jobs/search-results/?currentJobId=4470636955",
    html: page({
      title: "Founder in Residence", company: "The Flex", companyPath: "/company/theflexglobal/life/",
      id: "4470636955", line: "Türkiye · 2 weeks ago · Over 100 people clicked apply", chips: ["Remote", "Full-time"],
      action: `<a href="https://www.linkedin.com/safety/go/?url=https%3A%2F%2Fjobs%2Eashbyhq%2Ecom%2FThe-Flex%2F179c07be-aaaa-bbbb&amp;urlhash=x"><span>Apply</span></a>`,
      saved: "Saved",
      noise: `<div><p>Responses managed off LinkedIn</p><p>Job match summary not available</p><p>This job post doesn't have enough information to show a match.</p></div>`,
      body: "<p>Base360.ai is hiring.</p><p><strong>The Role</strong></p><p>Build things.</p><p><strong>You Should NOT Apply If</strong></p><p>You dislike ambiguity.</p><p>See how you compare to over 100 others who clicked apply</p>",
    }),
    expect: {
      linkedin_id: "4470636955", title: "Founder in Residence", company: "The Flex",
      location: "Türkiye", posted: "2 weeks ago", remote: true, employment_type: "Full-time",
      apply_url: "https://jobs.ashbyhq.com/The-Flex/179c07be-aaaa-bbbb", has: [/Base360\.ai is hiring/, /The Role/, /You Should NOT Apply If/, /dislike ambiguity/],
    },
  },
];

module.exports = { CASES };
