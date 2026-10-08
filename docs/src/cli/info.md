# info and version

Show what is installed. `version` prints one line; `info` prints package
metadata for the whole suite, in the style of `pip show`.

Both commands read local metadata only. They need no network, no manifest and
no signing key.

## `version`

=== "macOS / Linux"
    ```bash
    opencomplai version
    opencomplai version --output json
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai version
    opencomplai version --output json
    ```

```text
opencomplai <version>
```

```json
{"name": "opencomplai", "version": "<version>"}
```

The same line is printed by the top-level `opencomplai --version` flag.

## `info`

=== "macOS / Linux"
    ```bash
    opencomplai info
    opencomplai info --output json
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai info
    opencomplai info --output json
    ```

Human output lists the name, version, summary, home page, author, license,
install location and the `Requires` and `Required-by` lists of `opencomplai`,
followed by a table of the suite packages.

| Package | Role |
|---|---|
| `opencomplai` | SDK (umbrella) |
| `opencomplai-cli` | command-line interface |
| `opencomplai-core` | risk assessment engine |

The table shows each package's version and whether it is installed. A package
that is not installed shows `no`. Home page, author and license are filled in
even when a package was not installed through pip.

## Options

| Option | Default | Description |
|---|---|---|
| `--output` / `-o` | `human` | `human` or `json`. Applies to both commands. |

## JSON shape

`version --output json` is `{"name": ..., "version": ...}`.

`info --output json` is one object with the fields of `opencomplai` and a
`suite` array:

| Field | Meaning |
|---|---|
| `name`, `version` | Distribution name and installed version. |
| `summary`, `home_page`, `author`, `author_email`, `license` | Package metadata. |
| `location` | Install directory; empty when not installed. |
| `requires`, `required_by` | Lists of distribution names. |
| `installed` | `true` when the distribution is found. |
| `suite` | One object per suite package above, with the same fields. |

## Exit codes

Both commands exit `0`.
