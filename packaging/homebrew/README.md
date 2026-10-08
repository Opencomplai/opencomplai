# Homebrew formula

`opencomplai.rb` is the Homebrew formula for the `opencomplai` CLI. In a tap it
lives at `Formula/opencomplai.rb`.

**Status: the tap repository does not exist yet and nothing is published.** The
formula carries a placeholder `sha256` and no dependency `resource` blocks, so
`brew install` will fail until the release steps below are done. The tap name
`Opencomplai/homebrew-tap` is a founder choice and unverified, as is the PyPI
sdist URL until the release is on PyPI.

## Lint

Offline (no brew needed): `packages/cli/tests/test_homebrew_formula.py`
checks the structure: first line `# frozen_string_literal: true`, class,
`include Language::Python::Virtualenv`, `homepage`, `url`, a 64-hex `sha256`,
`license`, `depends_on "python@3.N"`, `virtualenv_install_with_resources`, a
`test do` block running `opencomplai --version`, two-space indent, no tabs, no
trailing whitespace, one final newline, and a `desc` under 80 characters with no
leading article, no trailing period and not starting with the formula name. It
also checks the licence, version and Python floor against the package metadata.

With Homebrew installed (founder step; the offline test only guards the common rules):

```bash
brew style packaging/homebrew/opencomplai.rb
brew audit --strict --new Opencomplai/tap/opencomplai
```

## Tap steps

1. Create the GitHub repository `Opencomplai/homebrew-tap`.
2. Copy `opencomplai.rb` to `Formula/opencomplai.rb` in that repository.
3. After the PyPI release, compute the sdist hash and put it in `sha256`:
   `curl -L <url> | shasum -a 256`
4. Generate the dependency resources:
   `brew update-python-resources Formula/opencomplai.rb`
5. Build and test:
   `brew install --build-from-source Opencomplai/tap/opencomplai`, then
   `brew test Opencomplai/tap/opencomplai`
6. Commit and push the tap.

Users then run `brew install Opencomplai/tap/opencomplai` (the same as
`brew tap Opencomplai/tap` followed by `brew install opencomplai`).

## Per release

- Bump the version in `url`.
- Replace `sha256` with the new sdist hash.
- Re-run `brew update-python-resources`.
- Re-run the build and test commands from step 5.
