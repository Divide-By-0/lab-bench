---
name: fork-only-pull-requests
description: Enforce that pull requests for this repository are opened only in the matching Divide-By-0 GitHub repository or fork, never against an upstream owner. Use whenever creating, reopening, retargeting, editing, or publishing a pull request, or choosing GitHub remotes, heads, and bases for PR work.
---

# Fork-only pull requests

Treat `Divide-By-0` as the only permitted pull-request destination owner.
`origin` is not proof of ownership: it may point at an upstream repository.

## Before changing a pull request

1. Resolve the repository root and repository name.
2. Inspect every Git remote and its resolved GitHub owner.
3. Resolve the permitted target as `Divide-By-0/<repository-name>` and verify
   that it exists and is accessible with `gh repo view`.
4. If that target cannot be verified, stop without creating or changing a
   pull request. Never fall back to an upstream repository.
5. Push the head branch to the permitted repository. Preserve the repository's
   existing instructions for base branch, PR template, draft status, tests,
   and review state.
6. Pass the destination explicitly to GitHub CLI, for example:

   ```bash
   gh pr create --repo Divide-By-0/REPOSITORY --base BASE --head BRANCH
   ```

   Never rely on GitHub CLI's inferred repository.

## Verify the result

Read the pull request back immediately after creation or mutation:

```bash
gh pr view PR_URL \
  --json url,state,isDraft,headRepositoryOwner,headRefName,baseRefName
```

Require all of the following:

- The URL path starts with `https://github.com/Divide-By-0/`.
- `headRepositoryOwner.login` is `Divide-By-0`.
- The base and head branches are the intended branches.
- The draft or ready state follows the repository's own instructions.

If any check fails, stop and correct the target before doing more PR work.

## Accidental upstream pull requests

If an upstream pull request was created accidentally, close it immediately.
Do not reopen it or add substantive comments. Preserve the work on a new
branch in the `Divide-By-0` repository before rewriting or deleting the old
head branch. GitHub does not provide contributors a way to erase the immutable
pull-request record, so never claim that closing, force-pushing, or deleting a
branch deleted the pull request itself.
