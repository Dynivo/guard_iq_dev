# Content Intelligence Platform

This tool helps turn relevant technology, cybersecurity, compliance, and business news into client-ready social content.

It was built for **Guard IQ**, the IT support company. Guard IQ is the client brand, not the name of the tool.

Installation and deployment are documented separately.

## What the tool does

- Collects articles from configured news sources.
- Screens articles for relevance to Guard IQ's target audience.
- Turns suitable articles and ideas into social-media drafts.
- Generates branded images for those drafts.
- Supports review, approval, and content planning before manual publishing.

## Content process

1. Pull news or capture an idea.
2. Screen the next batch of articles when required.
3. Review the results and correct inaccurate decisions.
4. Generate and edit a draft.
5. Approve the draft and its images.
6. Assign a publication date and publish the finished content manually.

## Project documentation

- [Backend](ai-content-platform-backend/README.md) — data, screening, generation, storage, and job processing.
- [Frontend](ai-content-platform-frontend/README.md) — pages, controls, and the client-facing workflow.

If an operation fails or appears stuck, check **Jobs** in the application. A diagnostics export is available from **Settings** for the development team.
