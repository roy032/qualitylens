# User story: Create an issue

As a signed-in project member, I want to report a problem by creating an issue in a repository,
so that the team can track and fix it.

## Acceptance criteria
1. A signed-in user can create an issue with a title and an optional description in any public repository, and in private repositories they have access to.
2. The title is required, cannot be blank or whitespace only, and is at most 255 characters.
3. Each new issue gets the next number in that repository (1, 2, 3 ...) and starts in the Open state.
4. Anonymous users cannot create issues (API returns 401). Creating an issue in a repository that does not exist returns 404.
5. The title and description are stored exactly as entered, including Unicode; HTML is shown as text, never executed.
6. Users can comment on an issue; empty comments are rejected.
7. An issue can be closed and reopened. Closing sets a closed timestamp and updates the repository's open-issue count.
8. The issue list can be filtered by state (open, closed, all) and is paginated (limit, page, X-Total-Count header).

## Interfaces
- UI: /{owner}/{repo}/issues/new
- API: POST /api/v1/repos/{owner}/{repo}/issues  body: {"title": string, "body": string}
       PATCH /api/v1/repos/{owner}/{repo}/issues/{index}  body: {"state": "open"|"closed"}
       GET /api/v1/repos/{owner}/{repo}/issues?state=&limit=&page=
