# Governance

This page says who decides what in the Opencomplai project, how a contributor takes on more responsibility, and what you can expect from us.

## Roles

| Role | What they can do | How it is reached |
|---|---|---|
| **Contributor** | Open issues, send pull requests, review, answer Discussions | Anyone |
| **Triager** | Label, assign and close issues and pull requests. Cannot merge | Offered after three merged changes, or equivalent help: careful bug reports, reviews, documentation work |
| **Reviewer** | Approve pull requests in the areas they know | Discussed after about eight merged changes, plus a conversation about the areas and the time they can give |
| **Maintainer** | Merge, cut releases, set direction | Currently [@OpenComplaiCTO](https://github.com/OpenComplaiCTO) |

We are actively looking for triagers and reviewers. If you would like to take on a role, say so in [Discussions](https://github.com/Opencomplai/opencomplai/discussions); you do not need to wait to be asked.

## How decisions are made

- **Small changes** are decided in the pull request or the issue.
- **Larger changes** (a new framework, a change to scan output, exit codes or the JSON contract, a new dependency) start with an issue or an Ideas discussion before any code is written. A maintainer decides and writes the outcome down in that issue, and in the changelog or the docs when users are affected.
- We try to explain a "no". A pull request that is declined gets a reason.

## Claiming work

- Comment on an issue to claim it. A maintainer assigns it to you on the first reply.
- If there has been no activity for 7 days, the issue is released again, with a friendly note. You can claim it again later.
- One person per issue at a time; ask in the issue if you would like to share it.
- Issues labelled `mentor-available` come with a maintainer who will answer questions while you work on them.

## What to expect from us

- A first reply within 48 hours on working days (see [SUPPORT.md](SUPPORT.md)).
- A decision within 7 days on whether a pull request will be applied, needs changes, or is declined, with the reason.
- Releases about every two weeks, when something has landed. Your change ships in the next one, and the pull request gets a comment saying which.

## Credit

Every change that ships is credited in [CHANGELOG.md](CHANGELOG.md) ("Thanks to @handle (#n)"). For code, the release commit also lists the contributor as a co-author, so GitHub shows them in the contributors graph. People who file precise bug reports or help others are credited in the release notes too.

## Changing this page

Open a pull request. Maintainers approve changes to this page.
