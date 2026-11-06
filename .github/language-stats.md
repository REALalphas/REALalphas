Language statistics update daily at 06:00 UTC and through the Languages workflow's Run workflow button.

In the profile repository, open Settings → Secrets and variables → Actions and add a repository secret named `METRICS_TOKEN`.

Use a fine-grained personal access token belonging to REALalphas. Select all repositories to include, both public and private, and grant repository Contents: Read-only (Metadata: Read-only is included automatically). New repositories must be added to the token's selection unless it covers all repositories.

Run the Languages workflow after adding the secret. Until then, the checked-in card contains the last generated public-only snapshot. Missing or expired credentials fail the update and preserve the previous card.

The card publishes aggregate language shares by code bytes. Repository names and individual repository statistics are not written to the card. Forks, Bash/Shell, Batch/Batchfile, and Docker/Dockerfile are excluded before calculating percentages.

The workflow uses its separate built-in GitHub token to commit the card. Repository Actions settings must allow write permissions, and branch rules must permit the bot to push.
