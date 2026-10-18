//! `notes` — a tiny command-line notes tool. Parses arguments by hand and
//! dispatches to the four commands: add, list, done, search.

mod note;
mod store;

use note::Note;
use store::Store;

const USAGE: &str = "usage: notes add <text> [--tag t] | list [--tag t] | done <id> | search <word>";

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if let Err(msg) = run(&args, &Store::from_env()) {
        eprintln!("error: {}", msg);
        std::process::exit(1);
    }
}

fn run(args: &[String], store: &Store) -> Result<(), String> {
    let (cmd, rest) = args.split_first().ok_or(USAGE)?;
    let (words, tags) = split_tags(rest)?;
    match cmd.as_str() {
        "add" => {
            let id = store.add(&words.join(" "), tags)?;
            println!("added note {}", id);
        }
        "list" => {
            let tag = tags.first();
            store.load()?.iter().filter(|n| tag.map_or(true, |t| n.has_tag(t))).for_each(print_note);
        }
        "done" => {
            let id = words.first().ok_or(USAGE)?;
            let id: u64 = id.parse().map_err(|_| format!("not a note id: {}", id))?;
            store.mark_done(id)?;
            println!("note {} done", id);
        }
        "search" => {
            let word = words.first().ok_or(USAGE)?;
            store.load()?.iter().filter(|n| n.matches(word)).for_each(print_note);
        }
        _ => return Err(USAGE.into()),
    }
    Ok(())
}

/// Pulls every `--tag <t>` pair out of the arguments; the rest are plain words.
fn split_tags(args: &[String]) -> Result<(Vec<String>, Vec<String>), String> {
    let (mut words, mut tags) = (Vec::new(), Vec::new());
    let mut it = args.iter();
    while let Some(a) = it.next() {
        if a == "--tag" {
            tags.push(it.next().ok_or("--tag needs a value")?.clone());
        } else {
            words.push(a.clone());
        }
    }
    Ok((words, tags))
}

fn print_note(n: &Note) {
    let mark = if n.done { "x" } else { " " };
    let tags = if n.tags.is_empty() { String::new() } else { format!("  #{}", n.tags.join(" #")) };
    println!("[{}] {:>3}  {}{}", mark, n.id, n.text, tags);
}
