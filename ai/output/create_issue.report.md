# AI vs manual test cases: Issues

AI output: `create_issue.ai.json`. Manual suite: `test-cases/manual_test_cases.csv` (feature = Issues).

| Metric | Value |
|---|---|
| AI cases | 28 |
| Manual cases | 18 |
| Valid (matched a manual case) | 17 |
| New (no manual match, review) | 11 |
| Duplicate | 0 |
| Missed (manual case not generated) | 1 |
| Coverage of manual suite | 94% |

## Valid: AI case matched to manual case

| AI | Manual | Score | AI title | Manual title |
|---|---|---|---|---|
| AI-28 | TC-ISSUE-16 | 1.00 | Invalid state filter value | Invalid state filter |
| AI-12 | TC-ISSUE-09 | 0.94 | Create issue in non-existent repository | Create issue in a repository that does not exist |
| AI-24 | TC-ISSUE-15 | 0.93 | Filter issue list by state | Filter issue list by state |
| AI-17 | TC-ISSUE-11 | 0.93 | Add a comment to an issue | Add a comment |
| AI-21 | TC-ISSUE-14 | 0.93 | Reopen a closed issue | Reopen a closed issue |
| AI-13 | TC-ISSUE-06 | 0.88 | Unicode and emoji title stored exactly | Title with Unicode and emoji |
| AI-4 | TC-ISSUE-03 | 0.84 | Reject whitespace-only title | Create issue with whitespace-only title |
| AI-1 | TC-ISSUE-01 | 0.84 | Create issue with valid title and description | Create issue with title and description |
| AI-3 | TC-ISSUE-02 | 0.81 | Reject empty title | Create issue with empty title |
| AI-20 | TC-ISSUE-13 | 0.80 | Close an open issue | Close an issue |
| AI-18 | TC-ISSUE-12 | 0.79 | Reject empty comment | Empty comment is rejected |
| AI-8 | TC-ISSUE-10 | 0.77 | Issue numbers are sequential per repository | Issue numbers increase per repository |
| AI-10 | TC-ISSUE-08 | 0.72 | Anonymous user cannot create issue | Create issue without being logged in |
| AI-5 | TC-ISSUE-04 | 0.70 | Title at maximum length 255 | Title of exactly 255 characters |
| AI-14 | TC-ISSUE-07 | 0.63 | HTML in title is rendered as text | Title with HTML/script and SQL characters |
| AI-26 | TC-ISSUE-17 | 0.61 | Pagination with limit and page | Pagination of issue list |
| AI-6 | TC-ISSUE-05 | 0.59 | Title one over maximum (256) | Title of 256 characters |

## New: no manual equivalent (review: real gap or noise?)

| AI | Type | Title |
|---|---|---|
| AI-2 | Positive | Create issue with title only |
| AI-7 | Boundary | Title of one character |
| AI-9 | Positive | Numbering is independent between repositories |
| AI-11 | Security | User without write access cannot create issue in private repo |
| AI-15 | Security | SQL metacharacters in title |
| AI-16 | Positive | Markdown in description renders safely |
| AI-19 | Negative | Reject whitespace-only comment |
| AI-22 | Negative | Closing an already closed issue |
| AI-23 | Negative | Invalid state value on update |
| AI-25 | Positive | Filter by open state returns only open issues |
| AI-27 | Boundary | Page beyond last page |

## Duplicate AI cases

| AI | Duplicates | Score | Title |
|---|---|---|---|

## Missed: manual cases the AI did not produce

| Manual | Type | Title |
|---|---|---|
| TC-ISSUE-18 | Negative | Open a non-existent issue number |
