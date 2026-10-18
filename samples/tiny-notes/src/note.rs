//! The `Note` type and the rules every note must follow.

use std::time::{SystemTime, UNIX_EPOCH};

/// A note's text may be at most this many characters (not bytes).
pub const MAX_TEXT_CHARS: usize = 280;
/// A note may carry at most this many tags.
pub const MAX_TAGS: usize = 5;

#[derive(Debug, Clone, PartialEq)]
pub struct Note {
    pub id: u64,
    pub text: String,
    pub tags: Vec<String>,
    pub done: bool,
    /// Creation time as unix seconds.
    pub created: u64,
}

impl Note {
    /// Builds a new, not-yet-done note, enforcing the text and tag limits.
    pub fn new(id: u64, text: &str, tags: Vec<String>) -> Result<Note, String> {
        validate(text, &tags)?;
        Ok(Note { id, text: text.to_string(), tags, done: false, created: now_secs() })
    }

    pub fn has_tag(&self, tag: &str) -> bool {
        self.tags.iter().any(|t| t == tag)
    }

    /// Case-insensitive substring match on the note text.
    pub fn matches(&self, word: &str) -> bool {
        self.text.to_lowercase().contains(&word.to_lowercase())
    }
}

pub fn validate(text: &str, tags: &[String]) -> Result<(), String> {
    let len = text.chars().count();
    if text.trim().is_empty() {
        return Err("note text cannot be empty".into());
    }
    if len > MAX_TEXT_CHARS {
        return Err(format!("note text is {} characters; the limit is {}", len, MAX_TEXT_CHARS));
    }
    if tags.len() > MAX_TAGS {
        return Err(format!("{} tags given; the limit is {}", tags.len(), MAX_TAGS));
    }
    Ok(())
}

fn now_secs() -> u64 {
    SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_secs()).unwrap_or(0)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn enforces_text_and_tag_limits() {
        assert!(Note::new(1, &"x".repeat(MAX_TEXT_CHARS), vec![]).is_ok());
        assert!(Note::new(1, &"é".repeat(MAX_TEXT_CHARS + 1), vec![]).is_err()); // counts chars, not bytes
        assert!(Note::new(1, "   ", vec![]).is_err());
        let tags: Vec<String> = (0..=MAX_TAGS).map(|i| format!("t{}", i)).collect();
        assert!(Note::new(1, "hello", tags).is_err());
    }

    #[test]
    fn search_is_case_insensitive() {
        let n = Note::new(1, "Buy MILK", vec!["home".into()]).unwrap();
        assert!(n.matches("milk"));
        assert!(n.has_tag("home"));
        assert!(!n.done);
    }
}
