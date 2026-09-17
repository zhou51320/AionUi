// Copyright 2025 AionUi (aionui.com)
// SPDX-License-Identifier: Apache-2.0

use std::collections::HashMap;
use std::fs::{self, File};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::sync::RwLock;
use std::time::{SystemTime, UNIX_EPOCH};

use aion_types::message::ContentBlock;
use hex;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use tracing::{debug, warn};

/// Default threshold above which tool results or text blocks are compressed to cache.
pub const DEFAULT_COMPRESSION_THRESHOLD: usize = 2048;

/// Stored entry in the lossless JSON KV cache.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CacheEntry {
    pub hash: String,
    pub original_content: String,
    pub preview: String,
    pub size: usize,
    #[serde(default = "default_ref_count")]
    pub ref_count: u32,
    pub created_at: u64,
    #[serde(default)]
    pub last_accessed_at: u64,
}

fn default_ref_count() -> u32 {
    1
}

/// Statistics for the context compression cache.
#[derive(Debug, Clone, Serialize, Deserialize, Default, PartialEq, Eq)]
pub struct CacheStats {
    pub block_count: usize,
    pub original_total_size: usize,
    pub compressed_total_size: usize,
    pub saved_size: usize,
}

/// Summary item for listing cached blocks.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct CacheBlockSummary {
    pub hash: String,
    pub preview: String,
    pub size: usize,
    pub ref_count: u32,
    pub created_at: u64,
}

/// A lightweight, Windows 7 compatible JSON KV cache for lossless context compression.
/// Avoids external C SQLite runtime dependencies to ensure 100% compatibility across all systems.
#[derive(Debug)]
pub struct ContextCacheStore {
    cache_file: PathBuf,
    entries: RwLock<HashMap<String, CacheEntry>>,
}

impl ContextCacheStore {
    /// Initialize cache store at the given path (e.g. `.../aionrs-sessions/aion_cache.json`).
    pub fn new<P: AsRef<Path>>(cache_file: P) -> Self {
        let cache_file = cache_file.as_ref().to_path_buf();
        let mut entries = HashMap::new();

        if cache_file.exists() {
            match fs::read_to_string(&cache_file) {
                Ok(content) => match serde_json::from_str::<HashMap<String, CacheEntry>>(&content) {
                    Ok(loaded) => {
                        debug!(path = %cache_file.display(), count = loaded.len(), "Loaded context compression cache");
                        entries = loaded;
                    }
                    Err(err) => {
                        warn!(path = %cache_file.display(), error = %err, "Failed to parse context cache JSON, initializing empty");
                    }
                },
                Err(err) => {
                    warn!(path = %cache_file.display(), error = %err, "Failed to read context cache file, initializing empty");
                }
            }
        }

        Self {
            cache_file,
            entries: RwLock::new(entries),
        }
    }

    /// Computes short SHA-256 hash (first 16 hex chars) of content.
    pub fn compute_hash(content: &str) -> String {
        let mut hasher = Sha256::new();
        hasher.update(content.as_bytes());
        let full_hex = hex::encode(hasher.finalize());
        full_hex[..16].to_string()
    }

    /// Creates a human-readable preview of content.
    pub fn make_preview(content: &str) -> String {
        let lines: Vec<&str> = content.lines().collect();
        if lines.len() <= 10 {
            if content.len() > 600 {
                format!("{}...", &content[..600])
            } else {
                content.to_string()
            }
        } else {
            let sample = lines[..10].join("\n");
            format!("{}\n... [{} more lines truncated in preview]", sample, lines.len() - 10)
        }
    }

    /// Stores content in the cache and returns (hash, compressed_marker).
    /// If content with the same hash already exists, ref_count is incremented idempotently.
    pub fn store(&self, content: &str) -> (String, String) {
        let hash = Self::compute_hash(content);
        let preview = Self::make_preview(content);
        let size = content.len();
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_secs())
            .unwrap_or(0);

        {
            if let Ok(mut map) = self.entries.write() {
                if let Some(existing) = map.get_mut(&hash) {
                    existing.ref_count += 1;
                    existing.last_accessed_at = now;
                } else {
                    let entry = CacheEntry {
                        hash: hash.clone(),
                        original_content: content.to_string(),
                        preview: preview.clone(),
                        size,
                        ref_count: 1,
                        created_at: now,
                        last_accessed_at: now,
                    };
                    map.insert(hash.clone(), entry);
                }
            }
        }

        self.persist();

        let marker = format!(
            "[Content compressed into local cache (hash: {hash}, size: {size} bytes)]\nPreview:\n{preview}\n[Original content preserved losslessly in aion_cache.json; reference hash: {hash} to retrieve]"
        );

        (hash, marker)
    }

    /// Retrieves original content by hash if present.
    pub fn retrieve(&self, hash: &str) -> Option<String> {
        self.entries
            .read()
            .ok()
            .and_then(|map| map.get(hash).map(|e| e.original_content.clone()))
    }

    /// Returns cache statistics: block count, original size, compressed size, and saved size.
    pub fn stats(&self) -> CacheStats {
        let map = match self.entries.read() {
            Ok(guard) => guard,
            Err(_) => return CacheStats::default(),
        };

        let block_count = map.len();
        let mut original_total_size = 0;
        let mut compressed_total_size = 0;

        for entry in map.values() {
            original_total_size += entry.size * (entry.ref_count as usize);
            // Marker overhead is ~160 chars + preview length
            let marker_size = entry.preview.len() + 160;
            compressed_total_size += marker_size * (entry.ref_count as usize);
        }

        let saved_size = original_total_size.saturating_sub(compressed_total_size);

        CacheStats {
            block_count,
            original_total_size,
            compressed_total_size,
            saved_size,
        }
    }

    /// Lists summaries of all cached blocks sorted by creation time descending.
    pub fn list_blocks(&self) -> Vec<CacheBlockSummary> {
        let map = match self.entries.read() {
            Ok(guard) => guard,
            Err(_) => return Vec::new(),
        };

        let mut list: Vec<CacheBlockSummary> = map
            .values()
            .map(|e| CacheBlockSummary {
                hash: e.hash.clone(),
                preview: e.preview.clone(),
                size: e.size,
                ref_count: e.ref_count,
                created_at: e.created_at,
            })
            .collect();
        list.sort_by(|a, b| b.created_at.cmp(&a.created_at));
        list
    }

    /// Compresses large ToolResult content blocks in-place into the lossless cache.
    pub fn compress_content_blocks(&self, blocks: &mut [ContentBlock], threshold: usize) -> usize {
        let mut compressed_count = 0;
        for block in blocks.iter_mut() {
            if let ContentBlock::ToolResult { content, .. } = block {
                if content.len() > threshold {
                    let (_, marker) = self.store(content);
                    *content = marker;
                    compressed_count += 1;
                }
            }
        }
        compressed_count
    }

    /// Checks whether estimated tokens exceed 85% of the model context limit.
    pub fn should_compress_at_85_percent(current_tokens: usize, context_limit: usize) -> bool {
        if context_limit == 0 {
            return false;
        }
        current_tokens >= (context_limit * 85) / 100
    }

    /// Dynamic compression that applies context window awareness.
    /// When current tokens reach 85% of context window limit, triggers aggressive compression (> 1024 chars).
    /// Under 85%, compresses blocks larger than 8192 chars to save headroom.
    pub fn compress_content_blocks_dynamic(
        &self,
        blocks: &mut [ContentBlock],
        current_tokens: usize,
        context_limit: Option<usize>,
    ) -> usize {
        let threshold = match context_limit {
            Some(limit) if limit > 0 => {
                if Self::should_compress_at_85_percent(current_tokens, limit) {
                    1024
                } else {
                    8192
                }
            }
            _ => DEFAULT_COMPRESSION_THRESHOLD,
        };

        self.compress_content_blocks(blocks, threshold)
    }

    /// Flushes cache to disk.
    fn persist(&self) {
        let entries_snapshot = match self.entries.read() {
            Ok(guard) => guard.clone(),
            Err(_) => return,
        };

        if let Some(parent) = self.cache_file.parent() {
            let _ = fs::create_dir_all(parent);
        }

        match serde_json::to_string_pretty(&entries_snapshot) {
            Ok(json_str) => {
                if let Ok(mut file) = File::create(&self.cache_file) {
                    let _ = file.write_all(json_str.as_bytes());
                }
            }
            Err(err) => {
                warn!(path = %self.cache_file.display(), error = %err, "Failed to serialize context cache");
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn test_context_cache_store_and_retrieve() {
        let dir = tempdir().unwrap();
        let cache_file = dir.path().join("aion_cache.json");
        let store = ContextCacheStore::new(&cache_file);

        let long_output = "Line 1\nLine 2\n".repeat(150);
        let (hash, marker) = store.store(&long_output);

        assert!(!hash.is_empty());
        assert!(marker.contains(&hash));
        assert!(marker.contains("Content compressed into local cache"));

        // Retrieve original
        let retrieved = store.retrieve(&hash);
        assert_eq!(retrieved, Some(long_output.clone()));

        // Test loading from persisted file
        let reloaded = ContextCacheStore::new(&cache_file);
        assert_eq!(reloaded.retrieve(&hash), Some(long_output));
    }

    #[test]
    fn test_compress_content_blocks() {
        let dir = tempdir().unwrap();
        let cache_file = dir.path().join("aion_cache.json");
        let store = ContextCacheStore::new(&cache_file);

        let small = "small content";
        let large = "a".repeat(3000);

        let mut blocks = vec![
            ContentBlock::ToolResult {
                tool_use_id: "tool_1".into(),
                content: small.into(),
                is_error: false,
            },
            ContentBlock::ToolResult {
                tool_use_id: "tool_2".into(),
                content: large.clone(),
                is_error: false,
            },
        ];

        let compressed_count = store.compress_content_blocks(&mut blocks, 2000);
        assert_eq!(compressed_count, 1);

        // First block was not compressed
        if let ContentBlock::ToolResult { content, .. } = &blocks[0] {
            assert_eq!(content, small);
        } else {
            panic!("Expected ToolResult");
        }

        // Second block was compressed
        if let ContentBlock::ToolResult { content, .. } = &blocks[1] {
            assert!(content.contains("Content compressed into local cache"));
            assert!(content.contains("size: 3000 bytes"));
        } else {
            panic!("Expected ToolResult");
        }
    }

    #[test]
    fn test_duplicate_hash_idempotent_ref_count() {
        let dir = tempdir().unwrap();
        let cache_file = dir.path().join("aion_cache.json");
        let store = ContextCacheStore::new(&cache_file);

        let content = "Repeated content block for test";
        let (hash1, _) = store.store(content);
        let (hash2, _) = store.store(content);

        assert_eq!(hash1, hash2);

        let blocks = store.list_blocks();
        assert_eq!(blocks.len(), 1);
        assert_eq!(blocks[0].ref_count, 2);
    }

    #[test]
    fn test_stats_calculation() {
        let dir = tempdir().unwrap();
        let cache_file = dir.path().join("aion_cache.json");
        let store = ContextCacheStore::new(&cache_file);

        let long_content = "X".repeat(5000);
        store.store(&long_content);

        let stats = store.stats();
        assert_eq!(stats.block_count, 1);
        assert_eq!(stats.original_total_size, 5000);
        assert!(stats.saved_size > 4000);
    }

    #[test]
    fn test_85_percent_threshold_trigger() {
        assert!(!ContextCacheStore::should_compress_at_85_percent(80_000, 100_000));
        assert!(ContextCacheStore::should_compress_at_85_percent(85_000, 100_000));
        assert!(ContextCacheStore::should_compress_at_85_percent(90_000, 100_000));
        assert!(!ContextCacheStore::should_compress_at_85_percent(90_000, 0));
    }
}


