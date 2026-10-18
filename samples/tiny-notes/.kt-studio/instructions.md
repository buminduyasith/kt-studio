# KT Studio: project instructions for tiny-notes

## Services

| Service | What it is for | Talks to | Login |
| --- | --- | --- | --- |
| tiny-notes CLI | Adds, lists and searches notes kept in one JSON-lines file | The notes file (`NOTES_FILE`) | No screens |

## Addresses

None: a command-line tool with no web app.

## Before the run

- tiny-notes is a command-line tool with no web app. There is no Part A (screens); videos start with
  a "Try it" chapter of terminal scenes.
- Build it locally with `cargo build` (output goes to `target/`, which git ignores).

## Screens and recording

- Run the CLI only with `NOTES_FILE` pointing at a scratch file (for example under `/tmp`), never at
  the real `~/.notes.jsonl` in the home folder.
- Use made-up demo notes only.

## Review

- Review the storyboard locally: open `storyboard.html` and comment in the chat. No artifact.
