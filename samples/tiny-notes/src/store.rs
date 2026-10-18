//! Persists notes as JSON lines (one note per line) with hand-written encoding.

use crate::note::Note;
use std::fs;
use std::io::Write;
use std::path::PathBuf;

pub struct Store {
    path: PathBuf,
}

impl Store {
    /// Uses `$NOTES_FILE` if set, otherwise `~/.notes.jsonl`.
    pub fn from_env() -> Store {
        let path = match std::env::var("NOTES_FILE") {
            Ok(p) if !p.is_empty() => PathBuf::from(p),
            _ => PathBuf::from(std::env::var("HOME").unwrap_or_else(|_| ".".into())).join(".notes.jsonl"),
        };
        Store { path }
    }

    /// Reads every note. A missing file means "no notes yet".
    pub fn load(&self) -> Result<Vec<Note>, String> {
        let data = match fs::read_to_string(&self.path) {
            Ok(d) => d,
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok(Vec::new()),
            Err(e) => return Err(format!("cannot read {}: {}", self.path.display(), e)),
        };
        data.lines().filter(|l| !l.trim().is_empty()).map(decode).collect()
    }

    /// Rewrites the whole file with the given notes.
    pub fn save(&self, notes: &[Note]) -> Result<(), String> {
        let mut f = fs::File::create(&self.path).map_err(|e| e.to_string())?;
        for n in notes {
            writeln!(f, "{}", encode(n)).map_err(|e| e.to_string())?;
        }
        Ok(())
    }

    /// Adds a note with the next free id and returns that id.
    pub fn add(&self, text: &str, tags: Vec<String>) -> Result<u64, String> {
        let mut notes = self.load()?;
        let id = notes.iter().map(|n| n.id).max().unwrap_or(0) + 1;
        notes.push(Note::new(id, text, tags)?);
        self.save(&notes)?;
        Ok(id)
    }

    pub fn mark_done(&self, id: u64) -> Result<(), String> {
        let mut notes = self.load()?;
        let note = notes.iter_mut().find(|n| n.id == id).ok_or(format!("no note with id {}", id))?;
        note.done = true;
        self.save(&notes)
    }
}

/// Quotes a string for JSON: `"` and `\` are backslash-escaped, control chars become `\uXXXX`.
fn escape(s: &str) -> String {
    let mut out = String::with_capacity(s.len() + 2);
    out.push('"');
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            c if (c as u32) < 0x20 => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out.push('"');
    out
}

pub fn encode(n: &Note) -> String {
    let tags: Vec<String> = n.tags.iter().map(|t| escape(t)).collect();
    format!(
        "{{\"id\":{},\"text\":{},\"tags\":[{}],\"done\":{},\"created\":{}}}",
        n.id, escape(&n.text), tags.join(","), n.done, n.created
    )
}

/// Decodes one line written by `encode`. Not a general JSON parser.
pub fn decode(line: &str) -> Result<Note, String> {
    let mut p = Parser { s: line.trim(), pos: 0 };
    let mut note = Note { id: 0, text: String::new(), tags: vec![], done: false, created: 0 };
    p.expect('{')?;
    loop {
        let key = p.string()?;
        p.expect(':')?;
        match key.as_str() {
            "id" => note.id = p.number()?,
            "created" => note.created = p.number()?,
            "text" => note.text = p.string()?,
            "done" => note.done = p.boolean()?,
            "tags" => {
                p.expect('[')?;
                while p.peek() != Some(']') {
                    note.tags.push(p.string()?);
                    if p.peek() == Some(',') { p.next(); }
                }
                p.expect(']')?;
            }
            other => return Err(format!("unknown field {:?}", other)),
        }
        match p.next() {
            Some(',') => continue,
            Some('}') => return Ok(note),
            _ => return Err("malformed note line".into()),
        }
    }
}

/// A cursor over one line; `pos` is a byte offset into `s`.
struct Parser<'a> {
    s: &'a str,
    pos: usize,
}

impl Parser<'_> {
    fn rest(&self) -> &str { &self.s[self.pos..] }
    fn peek(&self) -> Option<char> { self.rest().chars().next() }

    fn next(&mut self) -> Option<char> {
        let c = self.peek()?;
        self.pos += c.len_utf8();
        Some(c)
    }

    fn expect(&mut self, want: char) -> Result<(), String> {
        match self.next() {
            Some(c) if c == want => Ok(()),
            got => Err(format!("expected {:?}, got {:?}", want, got)),
        }
    }

    fn string(&mut self) -> Result<String, String> {
        self.expect('"')?;
        let mut out = String::new();
        loop {
            match self.next().ok_or("unterminated string")? {
                '"' => return Ok(out),
                '\\' => match self.next().ok_or("bad escape")? {
                    'u' => {
                        let hex = self.rest().get(..4).ok_or("short \\u escape")?;
                        let code = u32::from_str_radix(hex, 16).map_err(|e| e.to_string())?;
                        out.push(char::from_u32(code).ok_or("bad \\u escape")?);
                        self.pos += 4;
                    }
                    c => out.push(c), // covers \" and \\
                },
                c => out.push(c),
            }
        }
    }

    fn number(&mut self) -> Result<u64, String> {
        let len = self.rest().bytes().take_while(u8::is_ascii_digit).count();
        let n = self.rest()[..len].parse().map_err(|_| format!("bad number at byte {}", self.pos))?;
        self.pos += len;
        Ok(n)
    }

    fn boolean(&mut self) -> Result<bool, String> {
        for (word, val) in [("true", true), ("false", false)] {
            if self.rest().starts_with(word) {
                self.pos += word.len();
                return Ok(val);
            }
        }
        Err("expected true or false".into())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn round_trips_tricky_text() {
        let mut n = Note::new(7, "say \"hi\"\\ then\nnewline\tand é \u{1}", vec!["a,b".into()]).unwrap();
        n.done = true;
        assert_eq!(decode(&encode(&n)).unwrap(), n);
    }

    #[test]
    fn add_list_and_done_on_disk() {
        let path = std::env::temp_dir().join(format!("tiny-notes-test-{}.jsonl", std::process::id()));
        let _ = fs::remove_file(&path);
        let store = Store { path: path.clone() };
        assert_eq!(store.add("first", vec![]).unwrap(), 1);
        assert_eq!(store.add("second", vec!["work".into()]).unwrap(), 2);
        store.mark_done(1).unwrap();
        let notes = store.load().unwrap();
        assert_eq!(notes.len(), 2);
        assert!(notes[0].done && !notes[1].done);
        assert!(store.mark_done(99).is_err());
        let _ = fs::remove_file(&path);
    }
}
