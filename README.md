# ios-filedrop

`ios-filedrop` sends a file from Linux to a folder you can open from the iOS
Files app. It is meant for small everyday transfers such as PDFs, documents,
or images that you downloaded on Linux and want on an iPad or iPhone.

The default setup uses [rclone](https://rclone.org/) with iCloud Drive and
uploads into an iCloud Drive folder named `FromLinux`.

## Why this exists

Apple does not provide a native iCloud Drive client for Linux. `ios-filedrop`
keeps the day-to-day command simple while delegating the iCloud connection to
rclone:

```bash
ios-filedrop ~/Downloads/example.pdf
```

The file will appear in iCloud Drive under:

```text
FromLinux/example.pdf
```

If a file with that name already exists, `ios-filedrop` avoids overwriting it
by using a readable suffix such as `example-1.pdf`.

## Requirements

- Linux
- Python 3.11 or newer
- [uv](https://docs.astral.sh/uv/)
- [rclone](https://rclone.org/install/), built with the `iclouddrive` backend
- An Apple ID with iCloud Drive enabled

Check your rclone build with:

```bash
rclone help backends | grep iclouddrive
```

## Credential and config location

By default, rclone stores config in `~/.config/rclone/rclone.conf`.
`ios-filedrop` deliberately does **not** use that path.

Instead, it sets `RCLONE_CONFIG` to:

```text
~/.local/state/ios-filedrop/rclone.conf
```

This keeps Apple credentials/session data out of Git-managed dotfiles under
`~/.config`. rclone's iCloud backend stores an obscured password plus session
tokens/cookies; obscured is not the same as encrypted, so keep this file
private.

`ios-filedrop` creates the containing directory with mode `0700` and permissions
the config file as `0600` when it exists.

## Installation

### From a local checkout

```bash
git clone https://github.com/feoh/ios-filedrop.git
cd ios-filedrop
uv sync
uv run ios-filedrop --help
```

### As a uv tool

From a local checkout:

```bash
uv tool install .
ios-filedrop --help
```

Or, once published/available from GitHub:

```bash
uv tool install git+https://github.com/feoh/ios-filedrop.git
```

## One-time setup

Run:

```bash
ios-filedrop setup
```

or from a checkout:

```bash
uv run ios-filedrop setup
```

This starts interactive `rclone config` using the private config file described
above.

Recommended rclone choices:

- Remote name: `icloud`
- Backend/type: `iclouddrive`
- Service: `drive`

The remote name matters. The upload command defaults to `icloud`; if you choose
a different remote name, pass it later with `--remote your-name`.

Follow rclone's prompts for your Apple ID, password, and any two-factor/session
steps. If device-push two-factor authentication fails, re-run setup and enter
`sms` at rclone's 2FA prompt to request a text-message code.

After setup, verify it:

```bash
ios-filedrop check
```

## Usage

Upload a file to the default `FromLinux` folder:

```bash
ios-filedrop ~/Downloads/paper.pdf
```

Upload to a nested folder:

```bash
ios-filedrop ~/Downloads/paper.pdf --folder 'FromLinux/Papers'
```

Rename during upload:

```bash
ios-filedrop ~/Downloads/paper.pdf --name reading-for-class.pdf
```

Preview the rclone commands without contacting iCloud or uploading:

```bash
ios-filedrop ~/Downloads/paper.pdf --dry-run
```

Use a different rclone remote or config path:

```bash
ios-filedrop ~/Downloads/paper.pdf \
  --remote mydrive \
  --config-path /secure/path/rclone.conf
```

## Collision behavior

`ios-filedrop` will not overwrite a destination file.

If `paper.pdf` already exists in the target folder, the upload will use:

```text
paper-1.pdf
```

If that exists too, it tries `paper-2.pdf`, and so on.

## Troubleshooting

### `rclone is not installed or is not on PATH`

Install rclone using your distro package manager or the upstream install
instructions, then run `ios-filedrop setup` again.

### `Remote 'icloud' was not found`

Run `ios-filedrop setup` and create an rclone remote named exactly `icloud`, or
pass the remote you configured:

```bash
ios-filedrop check --remote your-remote-name
```

### iCloud asks you to sign in again

Apple sessions can expire. Re-run:

```bash
ios-filedrop setup
```

and update the existing `icloud` remote.

### iCloud two-factor authentication fails

rclone may print a long Apple JSON error if device-push or SMS two-factor
authentication fails, even when Apple's response says the code was valid.

If `ios-filedrop check` reports a missing iCloud trust token, try rclone's
reconnect flow with the isolated config file:

```bash
RCLONE_CONFIG=~/.local/state/ios-filedrop/rclone.conf \
  rclone config reconnect icloud:
```

If reconnect still fails during 2FA, the failure is in rclone's iCloud Drive
authentication flow. In that case, the practical workaround is to use another
rclone backend that is visible in the iOS Files app, such as Dropbox, OneDrive,
Google Drive, or WebDAV, and pass that remote with `--remote`.

## License

MIT
