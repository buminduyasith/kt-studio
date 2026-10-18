# tiny-notes

A tiny command-line notes tool in Rust. Standard library only — no external crates.

## Usage

```sh
cargo build --release
notes add "buy milk" --tag home
notes list                # all notes
notes list --tag home     # only notes tagged "home"
notes done 1              # mark note 1 as done
notes search milk         # case-insensitive text search
```

## Storage

Notes live in a JSON-lines file, one note per line: `$NOTES_FILE` if set,
otherwise `~/.notes.jsonl`. The JSON is written and read by hand in
`src/store.rs` (no serde).

## Rules

- A note's text is at most **280 characters**.
- A note has at most **5 tags**.

## Layout

| File           | What it does                                   |
|----------------|------------------------------------------------|
| `src/main.rs`  | Hand-rolled argument parsing and the commands  |
| `src/note.rs`  | `Note` struct and the text/tag limits          |
| `src/store.rs` | Loading/saving the JSON-lines file             |

Run the tests with `cargo test`.
