# Human review of the AI-generated cases: Create issue

`create_issue.report.md` is produced by `ai/evaluate.py`. This file records what a tester concluded after
reading that report and **running** the AI's new cases against Gitea 1.22.6.

## Headline
- The AI covered 17 of 18 hand-written cases (94%). It missed **TC-ISSUE-18** (open a non-existent issue
  number): the story's criteria only talk about creating issues, so the gap is in the input, not the model.
- 11 AI cases had no manual equivalent. After running them, 9 are worth keeping and **one found a real
  bug the manual suite missed (BUG-007)**.
- The evaluator flagged no duplicates at its 0.75 threshold, but review found one (AI-25).

## New cases, executed and judged

| AI case | Result when run | Verdict |
|---|---|---|
| AI-2 Title only, no description | 201, issue created | Keep: valid positive case, manual suite assumed a description |
| AI-7 Title of one character | 201 | Keep: automated already (`test_title_round_trips_exactly[1-char]`) but missing from the manual suite |
| AI-9 Numbering independent per repo | Each repo starts at #1 | Keep |
| AI-11 No access to private repo | 404 | Keep: important security case |
| AI-15 SQL metacharacters in title | Stored literally | Partly duplicate: TC-ISSUE-07 combines HTML and SQL in one case; the one-to-one matcher can only pair one of them |
| AI-16 Markdown + `<img onerror>` in body | Markdown rendered, `onerror` stripped | Keep: XSS check on the body, manual suite only checked the title |
| **AI-19 Whitespace-only comment** | **201, blank comment stored** | **Bug found: BUG-007** |
| AI-22 Close an already closed issue | 201, counters unchanged | Keep |
| AI-23 Invalid state on update | 412 | Keep: already automated (`test_invalid_state_on_edit_rejected`) but missing from the manual suite |
| AI-25 Filter by open state only | Same as AI-24 | **Duplicate of AI-24** (subset). Lexical similarity 0.57, below threshold |
| AI-27 Page beyond the last page | 200, empty list | Keep |

## What this says about the generator
- Strong at systematic techniques (boundaries, negative variants, security classes); it applied the
  "whitespace is not empty" idea to comments, which the human tester did not.
- Its output is only as complete as the story: anything not in the acceptance criteria (reading an issue
  by number) is not generated.
- The first draft of the story said "a user with write access"; the AI wrote AI-11 from it, and running it
  showed Gitea lets any signed-in user open issues on public repos. The story was corrected. Generated
  cases are a useful way to find ambiguous requirements.

## What this says about the evaluator
- Lexical matching is explainable and needs no API key, but it misses paraphrased duplicates (AI-25) and
  cannot split one manual case that covers two behaviours (TC-ISSUE-07). Next step: let Claude judge only
  the borderline pairs (score 0.4 to 0.75) and keep the lexical score as the first filter.
