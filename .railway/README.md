# Railway

`.railway/railway.ts` is the project definition: api, web, the hourly worker,
the CV bucket, and one Postgres database. The API and the worker both receive
that database's `DATABASE_URL`. Railway does not read this file during a deploy.
After the project exists, `railway config plan` then `railway config apply`
creates the services. Later git pushes build those services.

This directory does not create or deploy the project by itself.
The variable names to set by hand are listed in `docs/railway.md`. No values
belong in this file.
