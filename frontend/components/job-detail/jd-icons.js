/** Thin outline icons for Job Detail metadata / benefits. */

export function JdIcon({ name, size = 18, className = "" }) {
  const common = {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.6,
    strokeLinecap: "round",
    strokeLinejoin: "round",
    "aria-hidden": "true",
    focusable: "false",
    className: className || undefined,
  };

  switch (name) {
    case "pin":
      return (
        <svg {...common}>
          <path d="M12 21s7-5.2 7-11a7 7 0 10-14 0c0 5.8 7 11 7 11z" />
          <circle cx="12" cy="10" r="2.2" />
        </svg>
      );
    case "cloud":
      return (
        <svg {...common}>
          <path d="M7.5 18h9.2A4.3 4.3 0 0018 9.6 5.5 5.5 0 007.2 11 3.7 3.7 0 007.5 18z" />
        </svg>
      );
    case "swap":
      return (
        <svg {...common}>
          <path d="M7 7h11M15 4l3 3-3 3M17 17H6M9 14l-3 3 3 3" />
        </svg>
      );
    case "briefcase":
      return (
        <svg {...common}>
          <rect x="3.5" y="7" width="17" height="12.5" rx="2" />
          <path d="M9 7V5.8A1.8 1.8 0 0110.8 4h2.4A1.8 1.8 0 0115 5.8V7M3.5 12h17" />
        </svg>
      );
    case "shield":
      return (
        <svg {...common}>
          <path d="M12 3.5l7 2.5v5.8c0 4.2-2.8 7.2-7 8.7-4.2-1.5-7-4.5-7-8.7V6L12 3.5z" />
        </svg>
      );
    case "globe":
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="8.5" />
          <path d="M3.5 12h17M12 3.5c2.4 2.6 3.6 5.4 3.6 8.5S14.4 17.9 12 20.5C9.6 17.9 8.4 15.1 8.4 12S9.6 6.1 12 3.5z" />
        </svg>
      );
    case "wallet":
      return (
        <svg {...common}>
          <rect x="3.5" y="6.5" width="17" height="11.5" rx="2" />
          <path d="M3.5 10h17M16 13.5h2" />
        </svg>
      );
    case "clock":
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="8.5" />
          <path d="M12 7.5V12l3 2" />
        </svg>
      );
    case "heart":
      return (
        <svg {...common}>
          <path d="M12 20s-6.5-4.2-8.5-8A4.6 4.6 0 0112 7.2 4.6 4.6 0 0120.5 12c-2 3.8-8.5 8-8.5 8z" />
        </svg>
      );
    case "book":
      return (
        <svg {...common}>
          <path d="M5 5.5A2.5 2.5 0 017.5 3H19v15.5H7.5A2.5 2.5 0 005 21V5.5z" />
          <path d="M5 18.5h12" />
        </svg>
      );
    case "users":
      return (
        <svg {...common}>
          <circle cx="9" cy="9" r="3" />
          <path d="M3.5 18.5c.6-2.8 2.7-4 5.5-4s4.9 1.2 5.5 4" />
          <circle cx="17" cy="9.5" r="2.4" />
          <path d="M14.2 18.5c.4-1.8 1.7-2.8 3.6-2.8" />
        </svg>
      );
    case "building":
      return (
        <svg {...common}>
          <path d="M4.5 20.5h15M6.5 20.5V5.5l11 3v12" />
          <path d="M9 9.5h1.5M9 13h1.5M9 16.5h1.5M13.5 11h1.5M13.5 14.5h1.5" />
        </svg>
      );
    case "lock":
      return (
        <svg {...common}>
          <rect x="5.5" y="10.5" width="13" height="9.5" rx="2" />
          <path d="M8.5 10.5V7.8a3.5 3.5 0 017 0v2.7" />
        </svg>
      );
    case "share":
      return (
        <svg {...common}>
          <circle cx="18" cy="6" r="2.4" />
          <circle cx="6" cy="12" r="2.4" />
          <circle cx="18" cy="18" r="2.4" />
          <path d="M8.2 10.8l7.5-3.6M8.2 13.2l7.5 3.6" />
        </svg>
      );
    case "star":
      return (
        <svg {...common}>
          <path d="M12 3.8l2.2 4.5 5 .7-3.6 3.5.9 5L12 15.6 7.5 17.5l.9-5L4.8 9l5-.7L12 3.8z" />
        </svg>
      );
    case "external":
      return (
        <svg {...common}>
          <path d="M10 5.5H6.5A2 2 0 004.5 7.5v10a2 2 0 002 2h10a2 2 0 002-2V14M13.5 4.5H19.5V10.5M19 5l-8.5 8.5" />
        </svg>
      );
    case "back":
      return (
        <svg {...common}>
          <path d="M14 6l-6 6 6 6" />
        </svg>
      );
    default:
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="8.5" />
        </svg>
      );
  }
}
