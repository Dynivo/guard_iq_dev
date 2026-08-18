# Content Intelligence Platform

This tool helps turn relevant technology, cybersecurity, compliance, and business news into client-ready social content.

Installation and deployment are documented separately in the [Mac installation guide](INSTALLATION_GUIDE.md).

The client can create or manage the two AI provider accounts here:

- [Google AI Studio](https://aistudio.google.com/welcome)
- [OpenAI Platform](https://platform.openai.com/login)

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
- [Delivery review](DELIVERY_REVIEW.md) — final checks, security boundary, and password handover.
- [Security](SECURITY.md) — supported deployment, controls, limitations, and recovery.

If an operation fails or appears stuck, check **Jobs** in the application. A diagnostics export is available from **Settings** for the development team.
