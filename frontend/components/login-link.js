"use client";

import { beginLogin, loginHref } from "../lib/auth-link";

/** Anchor that always hard-navigates into `/api/auth/login` (OAuth redirect). */
export function LoginLink({ intent, returnTo, className, children, ...rest }) {
  const href = loginHref({ intent, returnTo });
  return (
    <a
      {...rest}
      className={className}
      href={href}
      onClick={(event) => {
        if (event.defaultPrevented) return;
        if (event.button !== 0) return;
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        beginLogin({ intent, returnTo });
      }}
    >
      {children}
    </a>
  );
}
