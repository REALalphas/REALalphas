Language statistics update daily at 06:00 UTC and through the Languages workflow's Run workflow button.

In the profile repository, open Settings → Secrets and variables → Actions and add a repository secret named `METRICS_TOKEN`.

Use a fine-grained personal access token belonging to REALalphas. Select all repositories to include, both public and private, and grant repository Contents: Read-only (Metadata: Read-only is included automatically). New repositories must be added to the token's selection unless it covers all repositories.

Run the Languages workflow after adding the secret. Until then, the checked-in card contains the last generated public-only snapshot. Missing or expired credentials fail the update and preserve the previous card.

The card publishes aggregate language shares by code bytes. Repository names and individual repository statistics are not written to the card. Forks are excluded. Makefile, CMake, Docker/Dockerfile, Bash/Shell, Batch/Batchfile, PowerShell, Just and DTrace are included in Other along with languages outside the top eight. All included bytes count toward the percentages.

The workflow uses its separate built-in GitHub token to commit the card. Repository Actions settings must allow write permissions, and branch rules must permit the bot to push.

Tiles follow descending language share in reading order, with Other last. The grid has four columns. Tile spans repeat as wide, square, square, square; wide tiles span two columns and every tile is one cell tall. Values omit the percent sign, which appears in the heading.
