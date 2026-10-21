# Accessibility audit: Gitea 1.22.6

Nine screens scanned with [axe-core](https://github.com/dequelabs/axe-core) 4.12 against **WCAG 2.1 level A
and AA**, plus two manual-style checks (keyboard-only sign-in, labelled form fields). Run it with
`make a11y`; the full axe output for every page is attached to the Allure report under *Accessibility*.

## How the tests treat existing problems

Gitea already fails some rules. Failing the build on those would make the check useless (always red), and
ignoring them would hide them. So [`tests/a11y/baseline.json`](../tests/a11y/baseline.json) lists, per page,
the rules that fail today:

- a rule **not** in the baseline fails the test: a new accessibility regression;
- a baseline rule that still fails is reported in Allure but does not block;
- a baseline rule that stops failing raises a warning, so the baseline gets tightened.

## Findings

| Rule (WCAG) | Impact | Pages | What a user experiences |
|---|---|---|---|
| `color-contrast` (1.4.3) | Serious | all 9 | Grey secondary text, footer links and the blue primary button text are below the 4.5:1 contrast ratio, hard to read with low vision or on a bright screen. |
| `aria-required-children` (1.3.1) | Critical | all 9 | The header menus use `role="menu"` without menu items inside, so screen readers announce an empty or broken menu. |
| `label` (1.3.1, 4.1.2) | Critical | new repository, repository home, issue | Search boxes inside dropdowns (owner, template, licence, labels) and the clone-URL box have no label; a screen reader says only "edit text". |
| `aria-input-field-name` (4.1.2) | Serious | new repository | The owner, template and gitignore dropdowns are announced as unnamed combo boxes. |
| `button-name` (4.1.2) | Critical | repository home, new issue, issue | Icon-only buttons (clone menu, monospace toggle, deadline and dependency controls) have no accessible name. |
| `aria-allowed-attr` (4.1.2) | Critical | new issue, issue | The Markdown monospace toggle uses an ARIA attribute its role does not support. |
| `link-name` (2.4.4, 4.1.2) | Serious | repository home | The heading anchor link in the README has no text. |

What works: the sign-in and sign-up forms have proper labels, the password field is masked, and sign-in
is fully operable from the keyboard (Tab order username → password, Enter submits).

These are upstream Gitea issues (Fomantic UI dropdowns and the colour theme), so they are documented here
rather than filed as BUG-0xx reports. The two worth raising upstream first are the unlabelled form controls
on the new-repository page and the icon-only buttons, since they block screen-reader users from completing
core tasks.
