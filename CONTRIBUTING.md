# Contributing

How changes to bitebox-food-ordering are made, named and released. The rules follow three published standards: [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/),
[Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html) and [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/).

## Set up once

```bash
git config core.hooksPath .githooks     # checks every commit message as you write it (needs Python 3)
```

## Commit messages

```
<type>(<scope>): <description>        at most 72 characters, no full stop

<body: what and why>

<footer: Refs: #12, or BREAKING CHANGE: what breaks and what to do instead>
```

| Type | Use it for | Changes the version |
| --- | --- | --- |
| `feat` | something people can now do | minor |
| `fix` | a bug fixed | patch |
| `perf` | the same thing, faster | patch |
| `docs` | documentation only | none |
| `refactor` | code reshaped, behaviour the same | none |
| `test` | tests only | none |
| `build` | dependencies and packaging | none |
| `ci` | workflows and automation | none |
| `chore` | everything else (releases, housekeeping) | none |
| `style` | formatting only | none |

A `!` after the type, or a `BREAKING CHANGE:` footer, marks a breaking change. The scope names the part of the project, for example `form`, `nav`, `chatbot`, `api`.
One logical change per commit.

Examples:

```
feat(blog): add a listing page and a detail page
fix(form): show the error under the field
docs: describe how to run the project
```

Commits before version 0.1.0 were written before this convention and are not rewritten: published history is never changed.

## Branches and pull requests

Trunk-based: `main` is always releasable, and work happens on short-lived branches merged back within days.

- Name branches `<type>/<short-description>`: `feat/blog`, `fix/form-error`.
- Open a pull request into `main`; the build must pass. Merge with **squash** and make the pull request title a Conventional Commit.
- Delete the branch after merging. Never force-push `main`.

## Versions

`MAJOR.MINOR.PATCH`, as in Semantic Versioning. The number is in `package.json`, and the git tag is the same number with a `v` in front.

**What a version promises** is everything a visitor or user can see and do. The code underneath can change in any version.

| Change | Before 1.0.0 | From 1.0.0 |
| --- | --- | --- |
| Removes or changes something people rely on | minor | **major** |
| Adds something people can do | minor | minor |
| Fixes a bug | patch | patch |

Major version 0 is initial development: anything may change in a minor version. 1.0.0 is cut when the project is ready to be relied on.
A pre-release carries a suffix, for example `1.0.0-rc.1`. A released version is never edited: a mistake is fixed in the next version.

## The changelog

[CHANGELOG.md](CHANGELOG.md) is written for people, not copied from `git log`. A change that people would notice adds a line under `## [Unreleased]` in the same pull request,
under **Added**, **Changed**, **Deprecated**, **Removed**, **Fixed** or **Security**.

## Releasing

From a clean `main` with a passing build:

```bash
python scripts/release.py 0.2.0 --dry-run    # look at the notes first
python scripts/release.py 0.2.0              # moves Unreleased under 0.2.0 with today's date, sets the version in package.json, commits and tags
git push && git push origin v0.2.0           # the tag starts the release workflow
```

The release workflow builds the tagged commit again, checks that the tag matches `package.json`, and publishes a GitHub Release whose text is the changelog section.
Push one release tag at a time: GitHub starts no workflow when more than three tags arrive together. If a run did not start, open Actions, then Release, then Run workflow, and enter the tag.
To roll back, deploy the previous tag. To withdraw a release, publish a new patch version; do not delete or move tags.
