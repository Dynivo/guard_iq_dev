# Backend

The backend provides the API and processing services used by the Content Intelligence Platform.

## News ingestion and screening

- Pulls articles from enabled sources, normalises their data, and prevents duplicates.
- Stores ingested articles without sending them to an AI model.
- Screens up to 100 unscored articles when **Screen next 100** is requested.
- Marks claimed articles as screening to prevent duplicate processing and limits concurrent model calls.
- Does not automatically start another batch after the current 100 finish.
- Handles **Rescore relevant articles** separately, selecting up to 100 of the least recently scored relevant articles.
- Sends article content—not only the title—to the model.
- Evaluates relevance for UK regulated firms with 5–70 people. Global stories are accepted when their lesson transfers to that audience.
- Saves the final screening outcome as relevant or rejected.

## Feedback and generation

- Stores relevance corrections and incorporates them into later screening decisions.
- Generates drafts using the source material, saved client profile, brand information, and learned preferences.
- Validates generated drafts before saving them and reports validation failures explicitly.
- Generates separate blue and white image styles using the saved Guard IQ logo and brand settings.
- Starts image generation with draft generation when the automatic-image option is enabled.

## Data and operations

- PostgreSQL stores organisations, users, the client profile, brand settings, articles, decisions, feedback, drafts, planning data, and job history.
- Generated media is stored in the configured local media directory.
- AI provider credentials remain on the server and are never returned to the browser.
- Shared monthly limits for Gemini and OpenAI/GPT are stored in PostgreSQL and enforced before paid calls, regardless of which model is selected within that provider.
- Ingestion, screening, draft generation, and image generation are recorded as jobs so their progress and errors can be monitored.
- Local recovery scripts reset a forgotten admin password and back up PostgreSQL plus generated media.
